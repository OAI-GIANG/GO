from __future__ import annotations
import json
import os
import secrets
import socket
import sys
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .engine.task_contract import TaskContract, TaskContractError
from .engine.durable_execution import DurableExecution, DurableExecutionError
from .vps2_execution_bridge import VPS2ExecutionBridge, BridgeRequest, OperationTemplate
from .cognitive import CognitiveService
from .tool_runtime import default_tool_registry
from .tool_governance import ToolGovernance, ToolGovernanceError
from runtime import go_kernel
from runtime.go_kernel import GateResult

VERSION = "0.1.1"
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "runtime" / "data" / "go_runtime.sqlite3"

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def env_bool(name: str, default: bool = False) -> bool:
    value=os.getenv(name); return default if value is None else value.lower() in {"1","true","yes","on"}

class RuntimeConfig:
    def __init__(self) -> None:
        self.host=os.getenv("GO_HOST","127.0.0.1"); self.port=int(os.getenv("GO_PORT","8787"))
        self.api_token=os.getenv("GO_API_TOKEN",""); self.allow_anonymous=env_bool("GO_ALLOW_ANONYMOUS",False)
        self.data_path=Path(os.getenv("GO_DATA",str(DEFAULT_DATA))).resolve(); self.commit=os.getenv("GO_COMMIT","unknown")
        self.tree=os.getenv("GO_TREE_SHA","unknown"); self.environment=os.getenv("GO_ENV","local")
    def validate(self) -> None:
        if self.port<0 or self.port>65535: raise ValueError("GO_PORT must be 0..65535")
        if not self.allow_anonymous and not self.api_token: raise ValueError("GO_API_TOKEN is required unless anonymous mode is explicitly enabled")

class GOApplication:
    """GO runtime. TaskContract owns intent; Submission owns submitted work; DurableExecution owns execution state."""
    def __init__(self, config: RuntimeConfig):
        config.validate(); self.config=config
        from .store import RuntimeStore
        self.store=RuntimeStore(config.data_path)
        self.durable=DurableExecution(self.store)
        self.cognitive=CognitiveService(self.store,config.commit,config.tree,config.environment)
        self.kernel=go_kernel.Kernel()
        self.tools=default_tool_registry()
        self.durable.recover_orphans()
        self.store.set_meta("version",VERSION); self.store.set_meta("commit",config.commit); self.store.set_meta("tree",config.tree); self.store.set_meta("started_at",utc_now())

    def authenticate(self, token: str|None)->bool:
        if self.config.allow_anonymous: return True
        return bool(token and self.config.api_token and secrets.compare_digest(token,self.config.api_token))


    def _vps2_bridge(self) -> VPS2ExecutionBridge:
        target = os.getenv("HG_VPS2_TARGET_ID", "").strip()
        allowlist = os.getenv("HG_VPS2_ALLOWLIST_VERSION", "").strip()
        policy = os.getenv("HG_VPS2_POLICY_VERSION", "").strip()
        if not target or not allowlist or not policy:
            raise RuntimeError("VPS2_V3_NOT_CONFIGURED")
        return VPS2ExecutionBridge(
            target_id=target,
            allowlist_version=allowlist,
            policy_version=policy,
            registry_version="VPS2-REGISTRY-V3",
            templates={
                "vps2.health": OperationTemplate("vps2.health", "/backend/health", True, ()),
                "vps2.memory.list": OperationTemplate("vps2.memory.list", "/backend/memory/list", True, ()),
            },
        )

    def execute_vps2(self, body: dict[str, Any]) -> dict[str, Any]:
        bridge = self._vps2_bridge()

        def required_string(name: str) -> str:
            value = body.get(name)
            return value.strip() if isinstance(value, str) else ""

        variables = body.get("variables")
        if variables is None:
            variables = {}

        req = BridgeRequest(
            request_id=required_string("request_id"),
            target_id=required_string("target_id"),
            operation_id=required_string("operation_id"),
            allowlist_version=required_string("allowlist_version"),
            policy_version=required_string("policy_version"),
            variables=variables,
        )
        import urllib.request
        import urllib.error
        def executor(template, variables):
            base = os.getenv("HG_EDGE_URL", "").strip().rstrip("/")
            from .tool_runtime import CredentialBroker
            token = CredentialBroker().get("HG_EDGE_TOKEN")
            if not base:
                raise RuntimeError("VPS2_EDGE_URL_NOT_CONFIGURED")
            url = base + template.action
            request = urllib.request.Request(
                url,
                headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
                method="GET",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    raw = response.read().decode("utf-8")
                    return {"http_status": response.status, "body": json.loads(raw)}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"VPS2_HTTP_{exc.code}:{raw[:500]}") from exc
        result = bridge.execute(req, executor)
        result["vps2_target_id"] = req.target_id or os.getenv("HG_VPS2_TARGET_ID", "")
        return result

    def _operations(self)->list[str]:
        tools=getattr(self,"tools",None)
        names=set(getattr(tools,"_tools",{}) or {})
        return sorted({"echo","ask"}|names)

    def status(self)->dict[str,Any]:
        return {"name":"GO","version":VERSION,"status":"RUNNING","host":socket.gethostname(),"commit":self.config.commit,"tree":self.config.tree,"environment":self.config.environment,"data_path":str(self.config.data_path),"started_at":self.store.get_meta("started_at"),"operations":self._operations(),"integration":"GO_NATIVE_ENGINE"}

    def execute(self, task_id:str, operation:str, payload:dict[str,Any])->dict[str,Any]:
        request=__import__("runtime.go_runtime.core.contracts",fromlist=["CognitiveRequest"]).CognitiveRequest(task_id,operation,payload,self.config.commit,self.config.tree,self.config.environment)
        advice=self.cognitive.advise(request); self.cognitive.authorize(task_id,operation)
        context=self.cognitive.reasoning_context(advice)
        model_payload=dict(payload)
        if context: model_payload["go_context"]=context
        output=self.cognitive.invoke_model(task_id,operation,model_payload)
        evidence=self.cognitive.emit_evidence(task_id,"MODEL_EXECUTION","model execution completed")
        from . import ivv, epistemics
        verification = ivv.verify_evidence(
            claim=str(evidence.get("claim") or ""), evidence=evidence, producer_id="go_runtime.runtime",
            producer_authority_domain="runtime", producer_failure_domain="runtime",
            verifier=ivv.get_trusted_verifier(),
        )
        evidence_obj = go_kernel.Evidence(
            str(evidence["evidence_id"]), "go_runtime.runtime", "MODEL_EXECUTION", str(evidence["source"]),
            evidence["captured_at"], str(evidence.get("provenance") or ""), str(evidence["integrity"]),
            "UNVERIFIED", str(evidence.get("claim") or ""),
        )
        promotion_status, promoted = self.kernel.verify_and_promote_evidence(
            evidence_obj, task_id, "MODEL_EXECUTION", verification_result=verification
        )
        if promotion_status is go_kernel.GateResult.ALLOW and promoted is not None:
            evidence["verification_status"] = promoted.verification_status
            evidence["truth_status"] = verification.truth_status
            self.store.save_evidence(evidence, evidence["captured_at"])
        else:
            evidence["verification_status"] = "UNVERIFIED"
            evidence["truth_status"] = "UNVERIFIED"
            self.store.save_evidence(evidence, evidence["captured_at"])
        replay=self.cognitive.emit_replay(task_id,"MODEL_EXECUTION",{"operation":operation,"output":output,"evidence_id":evidence["evidence_id"]})
        memory=self.cognitive.observe_memory(task_id,payload,evidence["evidence_id"])
        result={**output,"task_id":task_id,"cognitive":{"advice":advice.recommendation,"memory_ids":list(advice.memory_ids),"evidence_ids":list(advice.evidence_ids),"context_used":bool(context),"go_context":context},"evidence_id":evidence["evidence_id"],"replay_id":replay["replay_id"],
                "epistemics":epistemics.envelope(execution_state="COMPLETED", truth_status=verification.truth_status, verification_status=verification.verification_status)}
        if memory: result.update({"memory_id":memory["memory_id"],"memory_key":memory["normalized_key"],"memory_scope":memory["scope"]})
        learning_artifact=self.cognitive.build_learning_artifact(task_id,result)
        result["learning_artifact_id"]=learning_artifact["artifact_id"]
        return result

    TOOL_OPS = {"github.read_repo", "github.read_branch", "github.read_file", "github.read_releases"}

    def execute_tool(self, task_id: str, operation: str, payload: dict[str, Any], approval: str = "not_required") -> dict[str, Any]:
        governance = ToolGovernance(self.tools)
        result = governance.execute(task_id, operation, dict(payload), approval)
        report = {"operation": operation, "tool": result.tool_name, "ok": result.ok, "call_id": result.call_id,
                  "output": result.output, "witness": result.witness, "tool_contract": "TOOL-GOVERNANCE-V1"}
        self.store.add_event(task_id, "TOOL_EXECUTED",
                             {"call_id": result.call_id, "tool": result.tool_name,
                              "status": result.witness.get("status"), "witness_digest": result.witness.get("witness_digest")},
                             utc_now())
        return report

    def run_objective(self, task_id: str, payload: dict[str, Any], approval: str = "not_required") -> dict[str, Any]:
        """OBJECTIVE -> discovery -> bounded selection -> governed execution -> failure policy."""
        from .engine import objective_router as orx
        objective = str(payload.get("objective") or payload.get("text") or "").strip()
        if not objective:
            raise ValueError("objective is required")
        catalogue = orx.discover(self.tools)
        attempt: dict[str, int] = {}

        def execute(operation: str, step_payload: dict[str, Any], step_approval: str) -> tuple[bool, dict[str, Any], dict[str, Any]]:
            appr = step_approval if step_approval and step_approval != "not_required" else approval
            attempt[operation] = attempt.get(operation, 0) + 1
            step_task = f"{task_id}:{operation}:{attempt[operation]}"
            if operation in {"echo", "ask"}:
                out = self.execute(step_task, operation, step_payload)
                return True, out, {"status": "COMPLETED", "tool_name": operation, "task_id": step_task}
            report = self.execute_tool(step_task, operation, step_payload, approval=appr)
            return bool(report.get("ok")), dict(report.get("output") or {}), dict(report.get("witness") or {})

        trace = orx.orchestrate(objective, catalogue=catalogue, execute=execute)
        self.store.add_event(task_id, "OBJECTIVE_ROUTED",
                             {"objective": objective, "status": trace.get("status"), "final": trace.get("final"),
                              "selection": trace.get("selection"), "replans": trace.get("replans")}, utc_now())
        return trace

    def submit(self, body:dict[str,Any])->dict[str,Any]:
        task_id=str(body.get("task_id") or f"TASK-{uuid.uuid4().hex}")
        operation=str(body.get("operation") or "").strip().lower(); payload=body.get("payload")
        idem=str(body.get("idempotency_key") or task_id)
        if not operation: raise ValueError("operation is required")
        if not isinstance(payload,dict): raise ValueError("payload must be an object")
        if len(idem)>200: raise ValueError("idempotency_key too long")
        contract=TaskContract(goal=operation,metadata={"operation":operation,"payload":payload}).validate()
        submission=contract.submit(submission_id=task_id,idempotency_key=idem,execution_mode="SYNC")
        task,reused=self.durable.enqueue_submission(submission)
        if reused and task.get("state") in {"COMPLETED","FAILED","CANCELLED","TIMED_OUT","ABORTED_BY_KILL"}: return task
        self.store.add_event(task_id,"SUBMISSION_ACCEPTED",submission.to_dict(),utc_now())
        claimed=self.durable.claim(task_id)
        if claimed is None: return self.store.get_task(task_id) or {}
        metadata=claimed.get("metadata") or {}
        operation=str(metadata.get("operation") or operation); payload=dict(metadata.get("payload") or payload)
        try:
            tool_names=set(self.tools._tools)
            approval=str(body.get("approval") or "not_required")
            if operation=="objective.run":
                result=self.run_objective(task_id,payload,approval=approval)
            elif operation in tool_names:
                result=self.execute_tool(task_id,operation,payload,approval=approval)
            elif operation in {"echo","ask"}:
                result=self.execute(task_id,operation,payload)
            else:
                raise ValueError("unsupported operation; allowed operations: echo, ask, objective.run, "+", ".join(sorted(tool_names)))
            final=self.durable.finalize(task_id,int(claimed["fence_token"]),"COMPLETED",report=result)
            self.store.add_event(task_id,"EXECUTION_COMPLETED",result,utc_now())
            return final
        except Exception as exc:
            final=self.durable.finalize(task_id,int(claimed["fence_token"]),"FAILED",error={"type":type(exc).__name__,"message":str(exc)})
            self.store.add_event(task_id,"EXECUTION_FAILED",{"error":str(exc)},utc_now())
            return final

class Handler(BaseHTTPRequestHandler):
    server_version="GO/1.0"
    @property
    def app(self)->GOApplication: return self.server.app # type: ignore[attr-defined]
    def _json(self,status:int,payload:dict[str,Any])->None:
        encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode("utf-8"); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(encoded))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(encoded)
    def _authorized(self)->bool:
        auth=self.headers.get("Authorization",""); return self.app.authenticate(auth[7:] if auth.startswith("Bearer ") else None)
    def _body(self)->dict[str,Any]:
        length=int(self.headers.get("Content-Length","0"))
        if length<=0 or length>256*1024: raise ValueError("request body must be 1..262144 bytes")
        value=json.loads(self.rfile.read(length).decode("utf-8"));
        if not isinstance(value,dict): raise ValueError("JSON body must be an object")
        return value
    def do_GET(self)->None:
        if self.path=="/healthz": self._json(HTTPStatus.OK,{"status":"ok","version":VERSION}); return
        if not self._authorized(): self._json(HTTPStatus.UNAUTHORIZED,{"error":"unauthorized"}); return
        if self.path=="/v1/status": self._json(HTTPStatus.OK,self.app.status()); return
        if self.path.startswith("/v1/tasks/"):
            task=self.app.store.get_task(self.path.rsplit("/",1)[-1]); self._json(HTTPStatus.NOT_FOUND if task is None else HTTPStatus.OK,{"error":"task not found"} if task is None else task); return
        self._json(HTTPStatus.NOT_FOUND,{"error":"not found"})
    def do_POST(self)->None:
        if self.path=="/v1/vps2/execute":
            if not self._authorized():
                self._json(HTTPStatus.UNAUTHORIZED, {"error":"unauthorized"}); return
            try:
                result=self.app.execute_vps2(self._body())
            except Exception as exc:
                self._json(HTTPStatus.BAD_GATEWAY, {"error":type(exc).__name__, "message":str(exc)}); return
            self._json(HTTPStatus.OK, result); return
        if self.path=="/v1/phone/requests":
            from . import phone_bridge
            auth=self.headers.get("Authorization",""); token=auth[7:] if auth.startswith("Bearer ") else None
            try: body=self._body()
            except (ValueError,json.JSONDecodeError) as exc: self._json(HTTPStatus.BAD_REQUEST,{"error":str(exc)}); return
            resp=phone_bridge.handle(self.app, body, token)
            code=(resp.get("error") or {}).get("code")
            status=HTTPStatus.OK if resp.get("status")=="SUBMITTED" else HTTPStatus.UNAUTHORIZED if code=="AUTHENTICATION_FAILED" else HTTPStatus.BAD_REQUEST
            self._json(status, resp); return
        if not self._authorized(): self._json(HTTPStatus.UNAUTHORIZED,{"error":"unauthorized"}); return
        if self.path!="/v1/tasks": self._json(HTTPStatus.NOT_FOUND,{"error":"not found"}); return
        try: task=self.app.submit(self._body())
        except (ValueError,json.JSONDecodeError,TaskContractError,DurableExecutionError) as exc: self._json(HTTPStatus.BAD_REQUEST,{"error":str(exc)}); return
        status=HTTPStatus.OK if task.get("state")=="COMPLETED" else HTTPStatus.UNPROCESSABLE_ENTITY; self._json(status,task)
    def log_message(self,format:str,*args:Any)->None: sys.stderr.write("GO "+(format%args))

def create_server(config:RuntimeConfig|None=None)->ThreadingHTTPServer:
    config=config or RuntimeConfig(); app=GOApplication(config); server=ThreadingHTTPServer((config.host,config.port),Handler); server.app=app  # type: ignore[attr-defined]
    return server

def main()->int:
    config=RuntimeConfig(); server=create_server(config); print(f"GO {VERSION} listening on http://{config.host}:{config.port}")
    try: server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0

if __name__=="__main__": raise SystemExit(main())
