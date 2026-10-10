from __future__ import annotations
import hashlib, json, os, threading, uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .tool_runtime import ToolContext, ToolRegistry, ToolResult, _digest
from .governance_source import verify_governance_source
from runtime.go_kernel import Authority, Execution, GateResult, Kernel, now_utc

STATES=("ACCEPTED","VALIDATED","AUTHORIZATION_PENDING","APPROVED","STARTED","COMPLETED","FAILED","DENIED","CANCELLED")
TERMINAL={"COMPLETED","FAILED","DENIED","CANCELLED"}
TRANSITIONS={
 "ACCEPTED":{"VALIDATED","DENIED"},
 "VALIDATED":{"AUTHORIZATION_PENDING","DENIED"},
 "AUTHORIZATION_PENDING":{"APPROVED","DENIED"},
 "APPROVED":{"STARTED","CANCELLED"},
 "STARTED":{"COMPLETED","FAILED","CANCELLED"},
 "COMPLETED":set(),"FAILED":set(),"DENIED":set(),"CANCELLED":set(),
}

def _now(): return datetime.now(timezone.utc).isoformat()

class ToolGovernanceError(Exception):
    def __init__(self, code, message=None): self.code=code; super().__init__(message or code)

@dataclass(frozen=True)
class ToolCallKey:
    task_id:str
    tool_name:str
    arguments_digest:str
    execution_scope:str
    def value(self): return _digest(self.__dict__)

def validate_schema(schema:dict[str,Any], value:Any, path="$")->None:
    if not isinstance(schema,dict) or schema.get("type")!="object": raise ToolGovernanceError("SCHEMA_INVALID")
    if not isinstance(value,dict): raise ToolGovernanceError("TOOL_ARGUMENTS_INVALID",f"{path} must be object")
    required=schema.get("required",[])
    for key in required:
        if key not in value: raise ToolGovernanceError("TOOL_ARGUMENTS_INVALID",f"{path}.{key} is required")
    props=schema.get("properties",{})
    if schema.get("additionalProperties") is False:
        extra=set(value)-set(props)
        if extra: raise ToolGovernanceError("TOOL_ARGUMENTS_INVALID",f"unexpected properties: {sorted(extra)}")
    for key,sub in props.items():
        if key not in value: continue
        actual=value[key]; typ=sub.get("type")
        ok={"string":isinstance(actual,str),"object":isinstance(actual,dict),"array":isinstance(actual,list),"boolean":isinstance(actual,bool),"integer":isinstance(actual,int) and not isinstance(actual,bool),"number":isinstance(actual,(int,float)) and not isinstance(actual,bool),"null":actual is None}.get(typ,False)
        if typ and not ok: raise ToolGovernanceError("TOOL_ARGUMENTS_INVALID",f"{path}.{key} must be {typ}")

class ToolEventLedger:
    def __init__(self,path:Path):
        self.path=path; self.lock=threading.RLock(); self.path.parent.mkdir(parents=True,exist_ok=True)
    def _read(self):
        if not self.path.exists(): return []
        rows=[]
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try: rows.append(json.loads(line))
            except Exception: continue
        return rows
    def events(self,call_id):
        with self.lock: return [x for x in self._read() if x.get("call_id")==call_id]
    def find(self,call_id):
        ev=self.events(call_id); return ev[-1] if ev else None
    def append(self,event):
        with self.lock:
            with self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(event,ensure_ascii=False,sort_keys=True)+"\n")

class ToolGovernance:
    def __init__(self,registry:ToolRegistry, ledger_path:Path|None=None):
        self.registry=registry; self.kernel=Kernel(); self.ledger=ToolEventLedger(ledger_path or Path(os.getenv("HG_TOOL_EVENT_LEDGER","./data/tool-events.jsonl")))
        self._governance_source_sha256 = None
    def _emit(self,call_id,task_id,tool_name,state,**extra):
        event={"event_id":"TE-"+uuid.uuid4().hex,"call_id":call_id,"task_id":task_id,"tool_name":tool_name,"state":state,"occurred_at":_now(),"contract_version":"TOOL-GOVERNANCE-V1","governance_source_sha256":self._governance_source_sha256,**extra}
        self.ledger.append(event); return event
    def _transition(self,call_id,task_id,tool_name,current,new,**extra):
        if new not in TRANSITIONS.get(current,set()): raise ToolGovernanceError("INVALID_TOOL_STATE_TRANSITION",f"{current}->{new}")
        return self._emit(call_id,task_id,tool_name,new,previous_state=current,**extra)
    def _authority(self,task_id,tool_name):
        """Consume an externally issued, signed token; never mint authority in this component."""
        from .authority import AuthorityRoot, AuthorityToken, AUTHORITY_ROOT_ID, AuthorityError
        token_path=os.getenv("HG_TOOL_AUTHORITY_TOKEN_FILE", "").strip()
        subject=os.getenv("HG_TOOL_AUTHORITY_SUBJECT", "").strip()
        if not task_id or not subject.startswith("HG_SESSION_") or not token_path:
            return None
        try:
            with open(token_path, "r", encoding="utf-8") as handle:
                raw=json.load(handle)
            token=AuthorityToken(
                token_id=str(raw["token_id"]), subject=str(raw["subject"]), scope=frozenset(str(x) for x in raw["scope"]),
                action=str(raw["action"]), audience=str(raw["audience"]), issued_at=float(raw["issued_at"]),
                expires_at=float(raw["expires_at"]), nonce=str(raw["nonce"]), parent=raw.get("parent"), sig=str(raw["sig"]),
            )
            root=AuthorityRoot.instance(); audience=f"tool:{tool_name}"
            required_scope={audience, f"task:{task_id}"}
            if token.subject != subject or token.action != "execute" or token.audience != audience:
                return None
            if not root.verify(token, action="execute", scope=required_scope, audience=audience):
                return None
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, AuthorityError):
            return None
        now=now_utc()
        return Authority(token.token_id,subject,frozenset({audience}),frozenset({"execute"}),AUTHORITY_ROOT_ID,now,now+timedelta(minutes=5),frozenset({task_id}),"ACTIVE","authority-token:"+token.token_id)

    def _result(self, call_id, name, ok, output, witness):
        bound = dict(witness)
        bound["governance_source_sha256"] = self._governance_source_sha256
        return ToolResult(call_id, name, ok, output, bound)
    def execute(self,task_id:str,name:str,arguments:dict[str,Any],approval="not_required",call_id=None)->ToolResult:
        policy_state = verify_governance_source()
        self._governance_source_sha256 = policy_state["source_sha256"]
        adapter=self.registry._tools.get(name)
        if adapter is None: raise ToolGovernanceError("TOOL_NOT_FOUND")
        spec=adapter.spec(); cid=call_id or "CALL-"+uuid.uuid4().hex
        arg_digest=_digest(arguments); key=ToolCallKey(task_id,name,arg_digest,f"tool:{name}").value()
        prior=self.ledger.find(cid)
        if prior and (prior.get("arguments_digest")!=arg_digest or prior.get("tool_name")!=name or prior.get("task_id")!=task_id):
            raise ToolGovernanceError("CALL_ID_REUSE_CONFLICT")
        try:
            validate_schema(spec.input_schema,arguments)
        except ToolGovernanceError as exc:
            return self._result(cid,name,False,{"error":exc.code,"message":str(exc)},
                {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"error_type":exc.code,"contract_version":"TOOL-GOVERNANCE-V1"})
        auth=self._authority(task_id,name)
        if auth is None:
            return self._result(cid,name,False,{"error":"AUTHORITY_PROVENANCE_MISSING"},
                {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        gate,authorization=self.kernel.authorize(auth,auth.subject,"execute",f"tool:{name}",task_id)
        if gate is not GateResult.ALLOW or authorization is None:
            return self._result(cid,name,False,{"error":"KERNEL_DENY"},
                {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        approval_claims = None
        if spec.destructive:
            from .approval import verify_approval
            valid, reason = verify_approval(approval, subject=auth.subject, tool_name=name,
                arguments_digest=arg_digest, policy_sha256=str(self._governance_source_sha256 or ""),
                scope=f"tool:{name}", target=name)
            if not valid:
                return self._result(cid,name,False,{"error":reason},
                    {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
            approval_claims = {"approval_id": approval.approval_id, "nonce": approval.nonce, "approver_id": approval.approver_id}
            if any(e.get("approval_nonce") == approval.nonce for e in self.ledger._read()):
                return self._result(cid,name,False,{"error":"APPROVAL_REPLAY_DETECTED"},
                    {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        # Cached results are never returned before current authorization. Destructive approvals are single-use.
        if prior and prior.get("state") in TERMINAL and "output" in prior:
            if spec.destructive:
                return self._result(cid,name,False,{"error":"APPROVAL_REPLAY_DETECTED"},
                    {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
            return self._result(cid,name,prior["state"]=="COMPLETED",prior["output"],prior.get("witness",{}))
        # A duplicate semantic request does not disclose a prior output or trigger a second side effect.
        if any(e.get("idempotency_key")==key and e.get("state") in TERMINAL for e in self.ledger._read()):
            return self._result(cid,name,False,{"error":"IDEMPOTENT_RESULT_REUSE_DENIED"},
                {"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        self._emit(cid,task_id,name,"ACCEPTED",arguments_digest=arg_digest,idempotency_key=key)
        self._transition(cid,task_id,name,"ACCEPTED","VALIDATED",arguments_digest=arg_digest,idempotency_key=key)
        self._transition(cid,task_id,name,"VALIDATED","AUTHORIZATION_PENDING",arguments_digest=arg_digest)
        self._transition(cid,task_id,name,"AUTHORIZATION_PENDING","APPROVED",approval=approval_claims or "not_required",arguments_digest=arg_digest,approval_nonce=(approval_claims or {}).get("nonce"))
        self._transition(cid,task_id,name,"APPROVED","STARTED",arguments_digest=arg_digest)
        execution=Execution(cid,"execute",auth.subject,f"tool:{name}",1,authorization,True,cid)
        if self.kernel.execute_external(execution) is not GateResult.ALLOW:
            self._emit(cid,task_id,name,"DENIED",reason="KERNEL_EXECUTION_GATE",arguments_digest=arg_digest)
            return self._result(cid,name,False,{"error":"KERNEL_EXECUTION_GATE"},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        try:
            result=self.registry.dispatch(name,arguments,ToolContext(task_id,approval_claims or "not_required"),cid)
            state="COMPLETED" if result.ok else "FAILED"
            witness=dict(result.witness); witness.update({"scope":f"tool:{name}","subject":auth.subject,"witness_digest":_digest({"call_id":cid,"tool_name":name,"status":state,"output_digest":witness.get("output_digest")})})
            self._emit(cid,task_id,name,state,arguments_digest=arg_digest,output=result.output,witness=witness,idempotency_key=key,approval_nonce=(approval_claims or {}).get("nonce"))
            return self._result(cid,name,result.ok,result.output,witness)
        except Exception as exc:
            witness={"call_id":cid,"tool_name":name,"task_id":task_id,"status":"FAILED","arguments_digest":arg_digest,"error_type":type(exc).__name__,"contract_version":"TOOL-GOVERNANCE-V1"}
            self._emit(cid,task_id,name,"FAILED",arguments_digest=arg_digest,error_type=type(exc).__name__,witness=witness,idempotency_key=key,approval_nonce=(approval_claims or {}).get("nonce"))
            return self._result(cid,name,False,{"error":type(exc).__name__,"message":str(exc)},witness)

    def replay(self,call_id):
        events=self.ledger.events(call_id)
        if not events: raise ToolGovernanceError("REPLAY_NOT_FOUND")
        return {"replay_only":True,"call_id":call_id,"events":events,"adapter_invoked":False,"authorization_reexecuted":False,"credentials_retrieved":False}
