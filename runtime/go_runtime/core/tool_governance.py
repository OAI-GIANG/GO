from __future__ import annotations
import hashlib, json, os, threading, uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .tool_runtime import ToolContext, ToolRegistry, ToolResult, _digest
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

READONLY_CAPABILITY_PROFILE = (
    "go.status",
    "github.read_repo",
    "github.read_branch",
    "github.read_file",
    "github.read_releases",
    "vps1.edge.health",
    "vps2.health",
)


def capability_profile() -> tuple[str, tuple[str, ...]]:
    """Return the server-side capability profile; caller input cannot widen it.

    The profile is policy configuration owned by the GO runtime, not a tool or
    execution subsystem.  HG_SESSION subjects fail closed when no profile is
    configured.  Test/legacy callers may explicitly select a profile by
    environment, never by request payload.
    """
    name = os.getenv("HG_TOOL_CAPABILITY_PROFILE", "").strip()
    if name == "HG_READONLY_V1":
        return name, READONLY_CAPABILITY_PROFILE
    if name == "HG_FULL_V1":
        return name, ("*",)
    return name, ()


class ToolGovernance:
    def __init__(self,registry:ToolRegistry, ledger_path:Path|None=None):
        self.registry=registry; self.kernel=Kernel(); self.ledger=ToolEventLedger(ledger_path or Path(os.getenv("HG_TOOL_EVENT_LEDGER","./data/tool-events.jsonl")))
    def _emit(self,call_id,task_id,tool_name,state,**extra):
        event={"event_id":"TE-"+uuid.uuid4().hex,"call_id":call_id,"task_id":task_id,"tool_name":tool_name,"state":state,"occurred_at":_now(),"contract_version":"TOOL-GOVERNANCE-V1",**extra}
        self.ledger.append(event); return event
    def _transition(self,call_id,task_id,tool_name,current,new,**extra):
        if new not in TRANSITIONS.get(current,set()): raise ToolGovernanceError("INVALID_TOOL_STATE_TRANSITION",f"{current}->{new}")
        return self._emit(call_id,task_id,tool_name,new,previous_state=current,**extra)
    def _authority(self,task_id,tool_name):
        provenance=os.getenv("HG_TOOL_AUTHORITY_PROVENANCE","").strip()
        expected=os.getenv("HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED","").strip()
        subject=os.getenv("HG_TOOL_AUTHORITY_SUBJECT","").strip()
        if not task_id or not provenance or not expected or provenance != expected: return None
        if not subject.startswith("HG_SESSION_"): return None
        now=now_utc()
        return Authority("AUTH-TOOL-"+hashlib.sha256((subject+tool_name).encode()).hexdigest()[:16],subject,frozenset({f"tool:{tool_name}"}),frozenset({"execute"}),"HG_KERNEL",now,now+timedelta(minutes=5),frozenset({task_id}),"ACTIVE",provenance)
    def _capability_check(self, tool_name: str) -> tuple[bool, str, str]:
        subject = os.getenv("HG_TOOL_AUTHORITY_SUBJECT", "").strip()
        profile, allowed = capability_profile()
        # Canonical HG session authority is fail-closed unless a server-side
        # profile has explicitly delegated the requested capability.
        if subject.startswith("HG_SESSION_"):
            if not profile:
                return False, "CAPABILITY_PROFILE_MISSING", profile
            if "*" not in allowed and tool_name not in allowed:
                return False, "CAPABILITY_NOT_GRANTED", profile
        return True, "AUTHORIZED", profile

    def capability_allowed(self, tool_name: str) -> bool:
        return self._capability_check(tool_name)[0]

    def capability_profile_info(self) -> dict[str, Any]:
        name, allowed = capability_profile()
        return {"name": name or None, "allowed": list(allowed), "digest": _digest({"name": name, "allowed": list(allowed)})}

    def execute(self,task_id:str,name:str,arguments:dict[str,Any],approval="not_required",call_id=None)->ToolResult:
        adapter=self.registry._tools.get(name)
        if adapter is None: raise ToolGovernanceError("TOOL_NOT_FOUND")
        spec=adapter.spec(); cid=call_id or "CALL-"+uuid.uuid4().hex
        arg_digest=_digest(arguments); key=ToolCallKey(task_id,name,arg_digest,f"tool:{name}").value()
        prior=self.ledger.find(cid)
        if prior:
            if prior.get("arguments_digest")!=arg_digest or prior.get("tool_name")!=name: raise ToolGovernanceError("CALL_ID_REUSE_CONFLICT")
            if prior.get("state") in TERMINAL and "output" in prior:
                return ToolResult(cid,name,prior["state"]=="COMPLETED",prior["output"],prior.get("witness",{}))
        duplicate=None
        for e in self.ledger._read():
            if e.get("idempotency_key")==key and e.get("state") in TERMINAL: duplicate=e; break
        if duplicate and duplicate.get("call_id")!=cid:
            return ToolResult(cid,name,duplicate.get("state")=="COMPLETED",duplicate.get("output",{"error":"DUPLICATE_IDEMPOTENCY_KEY"}),duplicate.get("witness",{}))
        allowed, reason, profile = self._capability_check(name)
        if not allowed:
            self._emit(cid,task_id,name,"DENIED",reason=reason,capability_profile=profile,arguments_digest=arg_digest)
            return ToolResult(cid,name,False,{"error":reason,"capability_profile":profile or None},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","error_type":reason,"capability_profile":profile or None,"contract_version":"TOOL-GOVERNANCE-V1"})
        self._emit(cid,task_id,name,"ACCEPTED",arguments_digest=arg_digest,idempotency_key=key,capability_profile=profile)
        try: validate_schema(spec.input_schema,arguments)
        except ToolGovernanceError as exc:
            self._emit(cid,task_id,name,"DENIED",reason=exc.code,arguments_digest=arg_digest)
            return ToolResult(cid,name,False,{"error":exc.code,"message":str(exc)},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"error_type":exc.code,"contract_version":"TOOL-GOVERNANCE-V1"})
        self._transition(cid,task_id,name,"ACCEPTED","VALIDATED",arguments_digest=arg_digest,idempotency_key=key)
        self._transition(cid,task_id,name,"VALIDATED","AUTHORIZATION_PENDING",arguments_digest=arg_digest)
        auth=self._authority(task_id,name)
        if auth is None:
            self._emit(cid,task_id,name,"DENIED",reason="AUTHORITY_PROVENANCE_MISSING",arguments_digest=arg_digest)
            return ToolResult(cid,name,False,{"error":"AUTHORITY_PROVENANCE_MISSING"},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        gate,authorization=self.kernel.authorize(auth,auth.subject,"execute",f"tool:{name}",task_id)
        if gate is not GateResult.ALLOW or authorization is None:
            self._emit(cid,task_id,name,"DENIED",reason="KERNEL_DENY",arguments_digest=arg_digest); return ToolResult(cid,name,False,{"error":"KERNEL_DENY"},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        if spec.destructive and approval!="approved":
            self._emit(cid,task_id,name,"DENIED",reason="APPROVAL_REQUIRED",arguments_digest=arg_digest); return ToolResult(cid,name,False,{"error":"APPROVAL_REQUIRED"},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        self._transition(cid,task_id,name,"AUTHORIZATION_PENDING","APPROVED",approval=approval,arguments_digest=arg_digest)
        self._transition(cid,task_id,name,"APPROVED","STARTED",arguments_digest=arg_digest)
        execution=Execution(cid,"execute",auth.subject,f"tool:{name}",1,authorization,True,cid)
        if self.kernel.execute_external(execution) is not GateResult.ALLOW:
            self._emit(cid,task_id,name,"DENIED",reason="KERNEL_EXECUTION_GATE",arguments_digest=arg_digest)
            return ToolResult(cid,name,False,{"error":"KERNEL_EXECUTION_GATE"},{"call_id":cid,"tool_name":name,"task_id":task_id,"status":"DENIED","arguments_digest":arg_digest,"contract_version":"TOOL-GOVERNANCE-V1"})
        try:
            result=self.registry.dispatch(name,arguments,ToolContext(task_id,approval),cid)
            state="COMPLETED" if result.ok else "FAILED"
            witness=dict(result.witness); witness.update({"scope":f"tool:{name}","subject":auth.subject,"witness_digest":_digest({"call_id":cid,"tool_name":name,"status":state,"output_digest":witness.get("output_digest")})})
            self._emit(cid,task_id,name,state,arguments_digest=arg_digest,output=result.output,witness=witness,idempotency_key=key)
            return ToolResult(cid,name,result.ok,result.output,witness)
        except Exception as exc:
            witness={"call_id":cid,"tool_name":name,"task_id":task_id,"status":"FAILED","arguments_digest":arg_digest,"error_type":type(exc).__name__,"contract_version":"TOOL-GOVERNANCE-V1"}
            self._emit(cid,task_id,name,"FAILED",arguments_digest=arg_digest,error_type=type(exc).__name__,witness=witness,idempotency_key=key)
            return ToolResult(cid,name,False,{"error":type(exc).__name__,"message":str(exc)},witness)
    def replay(self,call_id):
        events=self.ledger.events(call_id)
        if not events: raise ToolGovernanceError("REPLAY_NOT_FOUND")
        return {"replay_only":True,"call_id":call_id,"events":events,"adapter_invoked":False,"authorization_reexecuted":False,"credentials_retrieved":False}
