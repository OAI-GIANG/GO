"""Durable execution primitives for the LOVE async task path.

Submission is the durable execution input; this module is the sole execution adapter;
Store remains the persistence owner; Runtime remains the executor;
Evidence/Replay remain integrity owners.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from .task_contract import Submission
from ..checkpoint import (
    AcceptanceCriterion,AcceptanceSnapshot,Blocker,Checkpoint,CheckpointIdentity,CheckpointSchema,
    ContractBinding,EvidenceManifest,EvidenceReference,NextAction,RepositoryWitness,ResumeState,sha256_canonical
)


TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT", "ABORTED_BY_KILL"}
RECOVERABLE_STATES = {"QUEUED", "RUNNING", "RECOVERING", "RECOVERY_PENDING"}
IDEMPOTENCY_SCOPES = {
    "SEMANTIC_REQUEST", "TASK_SUBMISSION", "EXECUTION_ATTEMPT", "STATE_TRANSITION",
    "EVIDENCE_APPEND", "MEMORY_WRITE", "SIDE_EFFECT",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_fingerprint(message: str, delay_s: int) -> str:
    raw = f"{message}\n{delay_s}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DurableExecutionError(ValueError):
    pass


class DurableExecution:
    """Sole execution-state adapter over the canonical Store."""

    def __init__(self, store: Any, worker_id: str | None = None, lease_seconds: int = 30):
        self.store = store
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        self.lease_seconds = max(5, int(lease_seconds))

    def backup(self, destination: Any) -> dict:
        destination = __import__("pathlib").Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        names = ["tasks.json", "memory.json", "learning.json", "metrics.json", "experiments.json", "capabilities.json", "evolution_runs.json", "provider_performance.json", "discoveries.json", "observations.json", "publications.json"]
        manifest = {"backup_id": f"BKP-{uuid.uuid4().hex}", "created_at": now_iso(), "files": {}}
        for name in names:
            source = self.store.root / name
            if not source.exists():
                continue
            target = destination / name
            shutil.copy2(source, target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest["files"][name] = {"sha256": digest, "size": target.stat().st_size}
        manifest_path = destination / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        return manifest

    @staticmethod
    def verify_backup(backup_root: Any) -> dict:
        root = __import__("pathlib").Path(backup_root)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for name, meta in manifest.get("files", {}).items():
            path = root / name
            if not path.is_file():
                raise DurableExecutionError(f"backup_missing:{name}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
                raise DurableExecutionError(f"backup_hash_mismatch:{name}")
        return manifest

    @staticmethod
    def restore_backup(backup_root: Any, target_root: Any) -> dict:
        manifest = DurableExecution.verify_backup(backup_root)
        target_root = __import__("pathlib").Path(target_root)
        target_root.mkdir(parents=True, exist_ok=True)
        for name in manifest.get("files", {}):
            shutil.copy2(__import__("pathlib").Path(backup_root) / name, target_root / name)
        return manifest

    def enqueue_submission(self, submission: Submission) -> tuple[dict, bool]:
        """Accept only a canonical Submission; execution state remains owned here."""
        if not isinstance(submission, Submission):
            raise DurableExecutionError("submission_required")
        submission.validate()
        return self.enqueue(
            task_id=submission.submission_id,
            goal=submission.goal,
            delay_s=submission.delay_s,
            idempotency_key=submission.idempotency_key,
            idempotency_scope=submission.idempotency_scope,
            execution_mode=submission.execution_mode,
            metadata=dict(submission.metadata),
        )

    def enqueue(self, *, task_id: str, goal: str, delay_s: int = 0,
                idempotency_key: str, idempotency_scope: str = "TASK_SUBMISSION",
                execution_mode: str = "ASYNC", metadata: dict | None = None) -> tuple[dict, bool]:
        if execution_mode not in {"SYNC", "ASYNC"}:
            raise DurableExecutionError("invalid_execution_mode")
        if idempotency_scope not in IDEMPOTENCY_SCOPES:
            raise DurableExecutionError("invalid_idempotency_scope")
        if not idempotency_key:
            raise DurableExecutionError("idempotency_key_required")
        fingerprint = request_fingerprint(goal, delay_s)
        with self.store.lock:
            rows = self.store.tasks()
            for row in rows:
                if row.get("idempotency_key") == idempotency_key and row.get("idempotency_scope") == idempotency_scope:
                    if row.get("request_fingerprint") != fingerprint:
                        raise DurableExecutionError("idempotency_conflict")
                    return row, True
            now = now_iso()
            task = {
                "id": task_id,
                "goal": goal,
                "state": "QUEUED",
                "async": execution_mode == "ASYNC",
                "execution_mode": execution_mode,
                "queue_eligibility": "DISPATCHABLE",
                "attempt_no": 0,
                "attempt": 0,
                "run_id": None,
                "attempt_id": None,
                "parent_run_id": None,
                "worker_id": None,
                "lease_id": None,
                "lease_until": None,
                "fence_token": 0,
                "revision": 1,
                "idempotency_key": idempotency_key,
                "idempotency_scope": idempotency_scope,
                "request_fingerprint": fingerprint,
                "recovery_count": 0,
                "delay_s": delay_s,
                "created_at": now,
                "updated_at": now,
                "last_heartbeat_at": None,
                "timeout_deadline": None,
                "recovery_reason": None,
                "evidence_refs": [],
                "provenance": {},
                "metadata": dict(metadata or {}),
            }
            self.store.upsert_task(task)
            return task, False

    @contextmanager
    def _claim_lock(self):
        lock_dir = self.store.root / ".durable_claim.lock"
        deadline = time.monotonic() + 10
        while True:
            try:
                lock_dir.mkdir()
                (lock_dir / "owner").write_text(self.worker_id, encoding="utf-8")
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise DurableExecutionError("claim_lock_timeout")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                (lock_dir / "owner").unlink(missing_ok=True)
                lock_dir.rmdir()
            except FileNotFoundError:
                pass

    def claim(self, task_id: str) -> dict | None:
        with self._claim_lock(), self.store.lock:
            task = self.store.task_by_id(task_id)
            if task is None or task.get("execution_mode", "ASYNC" if task.get("async") else None) not in {"SYNC", "ASYNC"}:
                return None
            if task.get("state") not in {"QUEUED", "RECOVERY_PENDING", "RECOVERING"}:
                return None
            if task.get("queue_eligibility") not in {"DISPATCHABLE", "RECOVERY"}:
                return None
            lease_until = task.get("lease_until")
            if lease_until and lease_until > now_iso():
                return None
            task["attempt_no"] = int(task.get("attempt_no", task.get("attempt", 0))) + 1
            task["attempt"] = task["attempt_no"]
            task["attempt_id"] = f"ATT-{uuid.uuid4().hex}"
            task["run_id"] = f"RUN-{uuid.uuid4().hex}"
            task["worker_id"] = self.worker_id
            task["lease_id"] = f"LEASE-{uuid.uuid4().hex}"
            task["fence_token"] = int(task.get("fence_token", 0)) + 1
            task["revision"] = int(task.get("revision", 0)) + 1
            task["lease_until"] = (datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)).isoformat()
            task["last_heartbeat_at"] = now_iso()
            task["state"] = "RUNNING"
            task["queue_eligibility"] = "CLAIMED"
            task["updated_at"] = now_iso()
            self.store.upsert_task(task)
            return dict(task)

    def heartbeat(self, task_id: str, fence_token: int) -> bool:
        with self.store.lock:
            task = self.store.task_by_id(task_id)
            if not task or task.get("worker_id") != self.worker_id or int(task.get("fence_token", -1)) != int(fence_token):
                return False
            if task.get("state") != "RUNNING" or (task.get("lease_until") and task["lease_until"] <= now_iso()):
                return False
            task["last_heartbeat_at"] = now_iso()
            task["lease_until"] = (datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)).isoformat()
            task["revision"] = int(task.get("revision", 0)) + 1
            task["updated_at"] = now_iso()
            self.store.upsert_task(task)
            return True

    def finalize(self, task_id: str, fence_token: int, state: str, *, report: dict | None = None,
                 error: dict | None = None, outcome: str | None = None) -> dict:
        if state not in TERMINAL_STATES:
            raise DurableExecutionError("invalid_terminal_state")
        with self.store.lock:
            task = self.store.task_by_id(task_id)
            if not task:
                raise DurableExecutionError("task_not_found")
            if int(task.get("fence_token", -1)) != int(fence_token) or task.get("worker_id") != self.worker_id:
                raise DurableExecutionError("stale_fence_token")
            if task.get("state") in TERMINAL_STATES:
                return task
            if outcome is None:
                if state == "COMPLETED":
                    outcome = str((report or {}).get("epistemics", {}).get("task_outcome", "UNKNOWN"))
                elif state in {"FAILED", "CANCELLED", "TIMED_OUT", "ABORTED_BY_KILL"}:
                    outcome = "FAILURE"
                else:
                    outcome = "UNKNOWN"
            if outcome not in {"SUCCESS", "FAILURE", "UNKNOWN"}:
                raise DurableExecutionError("invalid_task_outcome")
            task["state"] = state
            task["task_outcome"] = outcome
            task["queue_eligibility"] = "TERMINAL"
            task["lease_until"] = None
            task["updated_at"] = now_iso()
            task["revision"] = int(task.get("revision", 0)) + 1
            if report is not None:
                task["report"] = report
            if error is not None:
                task["error"] = error
            self.store.upsert_task(task)
            return self.store.task_by_id(task_id) or dict(task)

    def emit_replay(self, task_id: str, event_type: str, payload: dict[str,Any], now: str|None=None)->dict[str,Any]:
        now=now or now_iso(); records=self.store.list_replay(task_id); seq=len(records)+1; prev=records[-1]["record_digest"] if records else "GENESIS"
        r={"replay_id":f"RPL-{uuid.uuid4().hex}","task_id":task_id,"sequence":seq,"event_type":event_type,"payload":payload,"previous_digest":prev,"occurred_at":now}
        r["record_digest"]=sha256_canonical(r); self.store.save_replay(r,now); return r

    def verify_replay(self, task_id: str)->bool:
        prev="GENESIS"
        for i,r in enumerate(self.store.list_replay(task_id),1):
            if int(r.get("sequence",0))!=i or r.get("previous_digest")!=prev: return False
            rp={"replay_id":r.get("replay_id"),"task_id":r.get("task_id"),"sequence":int(r.get("sequence")),"event_type":r.get("event_type"),"payload":r.get("payload",{}),"previous_digest":r.get("previous_digest"),"occurred_at":r.get("occurred_at")}
            if sha256_canonical(rp)!=r.get("record_digest"): return False
            prev=r.get("record_digest")
        return True

    def create_checkpoint(self, task_id: str, *, repository: dict[str,Any], contract: Any, phase: str,
                          acceptance: dict[str,Any], evidence: list[dict[str,Any]], blockers: list[dict[str,Any]],
                          next_action: dict[str,Any], resume: dict[str,Any]|None=None, source_runtime: str="go_runtime",
                          created_at: str|None=None)->dict[str,Any]:
        task=self.store.task_by_id(task_id)
        if task is None: raise DurableExecutionError("task_not_found")
        created_at=created_at or now_iso()
        latest=self.store.get_latest_checkpoint(task_id); rev=(latest or {}).get("identity",{}).get("checkpoint_revision",0)+1
        cid=f"CHK-{uuid.uuid4().hex}"
        ch=getattr(contract,"contract_hash",None) or (contract.get("contract_hash") if isinstance(contract,dict) else None) or (task.get("metadata") or {}).get("_contract_hash")
        if not ch: raise DurableExecutionError("contract_hash_required")
        cn=getattr(contract,"contract_name","LOVE_TASK_CONTRACT"); cv=getattr(contract,"contract_version","1.0")
        refs=tuple(EvidenceReference(str(e["evidence_id"]),str(e.get("evidence_digest") or e.get("integrity") or ""),str(e.get("verification_status","UNVERIFIED"))) for e in evidence)
        refs_payload=sorted([{"evidence_id":r.evidence_id,"evidence_digest":r.evidence_digest,"verification_status":r.verification_status} for r in refs],key=lambda x:x["evidence_id"])
        manifest=EvidenceManifest(refs,sha256_canonical(refs_payload))
        ac=AcceptanceSnapshot(tuple(AcceptanceCriterion(str(c["id"]),str(c["statement"]),str(c.get("status","UNTESTED"))) for c in acceptance.get("criteria",[])),str(acceptance.get("aggregate_status","UNTESTED")))
        bl=tuple(Blocker(str(b["blocker_id"]),str(b["code"]),str(b["description"]),bool(b.get("blocking",True)),str(b.get("unblock_condition",""))) for b in blockers)
        na=NextAction(str(next_action["action_id"]),str(next_action["action_type"]),str(next_action["instruction"]),tuple(next_action.get("prerequisites",())),bool(next_action.get("deterministic",True)))
        rs=ResumeState(bool((resume or {}).get("eligible",False)),str((resume or {}).get("reason_code","")),tuple((resume or {}).get("required_context_refs",())),bool((resume or {}).get("model_context_required",False)))
        rw=RepositoryWitness(remote=repository.get("remote",""),branch=repository.get("branch",""),canonical_head=repository.get("canonical_head",""),observed_head=repository.get("observed_head",""),observed_tree=repository.get("observed_tree",""),local_dirty=repository.get("local_dirty"),provenance_status=repository.get("provenance_status","UNVERIFIED"),witness_mode=repository.get("witness_mode","REMOTE_RUNTIME"))
        cp=Checkpoint(CheckpointIdentity(cid,task_id,rev),CheckpointSchema(),created_at,source_runtime,rw,ContractBinding(cn,cv,ch,"VALID"),
                      str(task.get("goal","")),str(task.get("operation","")),str(task.get("execution_mode","")),str(task.get("state","")),
                      int(task.get("revision",0)),int(task.get("attempt_no",0)),task.get("run_id"),task.get("attempt_id"),phase,ac,manifest,bl,na,rs)
        h=cp.computed_hash(); records=self.store.list_replay(task_id); seq=len(records)+1; prev=records[-1]["record_digest"] if records else "GENESIS"
        replay={"replay_id":f"RPL-{uuid.uuid4().hex}","task_id":task_id,"sequence":seq,"event_type":"CHECKPOINT_CREATED","payload":{"checkpoint_id":cid,"checkpoint_revision":rev,"checkpoint_hash":h},"previous_digest":prev,"occurred_at":created_at}
        replay["record_digest"]=sha256_canonical(replay)
        cp=Checkpoint(**{**cp.__dict__,"replay_sequence":seq,"replay_digest":replay["record_digest"],"canonical_payload_hash":h}).validated()
        self.store.save_checkpoint_with_replay(cp.to_dict(),replay,created_at); return cp.to_dict()

    def load_checkpoint(self, task_id: str, checkpoint_id: str|None=None)->dict[str,Any]|None:
        cp=self.store.get_checkpoint(checkpoint_id) if checkpoint_id else self.store.get_latest_checkpoint(task_id)
        return cp if cp and cp["identity"]["task_id"]==task_id else None

    def evaluate_resume(self, task_id: str, checkpoint_id: str|None=None, *, repository_witness: dict[str,Any]|None=None):
        from runtime.go_kernel import Kernel
        from runtime.go_runtime.core.contracts import ResumeDecision
        cp=self.load_checkpoint(task_id,checkpoint_id)
        if cp is None: return ResumeDecision("BLOCKED","CHECKPOINT_INTEGRITY_INVALID",checkpoint_id or "",task_id,0)
        task=self.store.task_by_id(task_id); repo=repository_witness or (task.get("provenance") if task else {})
        return Kernel().evaluate_resume(cp,task,repo,self.store.list_evidence(task_id),self.store.list_replay(task_id))

    def resume(self, task_id: str, checkpoint_id: str|None=None, *, repository_witness: dict[str,Any]|None=None)->dict[str,Any]:
        d=self.evaluate_resume(task_id,checkpoint_id,repository_witness=repository_witness)
        if d.decision!="ALLOW": raise DurableExecutionError(f"resume_blocked:{d.reason_code}")
        task=self.store.task_by_id(task_id)
        if task is None: raise DurableExecutionError("task_not_found")
        if task.get("state") in {"FAILED","RECOVERY_PENDING"}: return self.request_recovery(task_id,reason="checkpoint_resume")
        if task.get("state") in {"QUEUED","RECOVERING"}: return task
        raise DurableExecutionError("resume_requires_recovery_fence")

    def request_recovery(self, task_id: str, *, reason: str = "manual_recovery") -> dict:
        """Move one failed/orphaned task into the canonical recovery path."""
        with self.store.lock:
            task = self.store.task_by_id(task_id)
            if task is None:
                raise DurableExecutionError("task_not_found")
            if not task.get("async"):
                raise DurableExecutionError("not_async_task")
            if task.get("state") not in {"FAILED", "RECOVERY_PENDING"}:
                raise DurableExecutionError("task_not_recoverable")
            recovery_count = int(task.get("recovery_count", 0))
            if recovery_count >= 1:
                raise DurableExecutionError("recovery_limit_reached")
            task["state"] = "RECOVERING"
            task["queue_eligibility"] = "RECOVERY"
            task["recovery_count"] = recovery_count + 1
            task["recovery_reason"] = reason
            task["revision"] = int(task.get("revision", 0)) + 1
            task["updated_at"] = now_iso()
            self.store.upsert_task(task)
            return dict(task)

    def recover_orphans(self) -> list[dict]:
        recovered = []
        with self.store.lock:
            for task in self.store.tasks():
                if not task.get("async"):
                    continue
                if task.get("state") not in {"QUEUED", "RUNNING", "RECOVERING"}:
                    continue
                if task.get("state") == "RUNNING":
                    task["parent_run_id"] = task.get("run_id")
                    task["recovery_reason"] = "server_restart_or_worker_loss"
                    # Orphan detection is not a retry attempt; recovery budget
                    # is consumed only when request_recovery() is accepted.
                    task["worker_id"] = None
                    task["lease_id"] = None
                    task["lease_until"] = None
                    task["queue_eligibility"] = "RECOVERY"
                    task["state"] = "RECOVERY_PENDING"
                    task["revision"] = int(task.get("revision", 0)) + 1
                    task["updated_at"] = now_iso()
                    self.store.upsert_task(task)
                    recovered.append(dict(task))
                elif task.get("state") in {"QUEUED", "RECOVERING"}:
                    task["queue_eligibility"] = "DISPATCHABLE"
                    task["updated_at"] = now_iso()
                    self.store.upsert_task(task)
        return recovered
