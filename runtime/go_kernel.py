"""Minimal GO kernel implementation for semantic kernel V1."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import FrozenSet, Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class GateResult(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    BLOCKED = "BLOCKED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Authority:
    authority_id: str
    subject: str
    scope: FrozenSet[str]
    actions: FrozenSet[str]
    issuer: str
    valid_from: datetime
    valid_until: datetime
    contexts: FrozenSet[str] = frozenset()
    status: str = "ACTIVE"
    provenance: str = ""

    def permits(self, subject: str, action: str, scope: str, context: str, at: datetime) -> bool:
        return (
            self.status == "ACTIVE"
            and self.subject == subject
            and action in self.actions
            and scope in self.scope
            and context in self.contexts
            and self.valid_from <= at <= self.valid_until
            and bool(self.provenance)
        )


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    subject: str
    scope: str
    source: str
    captured_at: datetime
    provenance: str
    integrity: str
    verification_status: str
    claim: str = ""

    def canonical_payload(self) -> str:
        return "|".join((self.evidence_id, self.subject, self.scope, self.source,
                         self.captured_at.isoformat(), self.provenance))

    def expected_integrity(self) -> str:
        return sha256(self.canonical_payload().encode("utf-8")).hexdigest()

    def is_verified(self, subject: str, scope: str) -> bool:
        return (
            self.subject == subject
            and self.scope == scope
            and bool(self.source)
            and bool(self.provenance)
            and self.integrity == self.expected_integrity()
            and self.verification_status == "VERIFIED"
        )


@dataclass(frozen=True)
class State:
    entity_id: str
    value: str
    version: int
    lifecycle: str = "ACTIVE"


@dataclass(frozen=True)
class Advisory:
    advisory_id: str
    recommendation: str
    evidence_ids: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class Authorization:
    authority_id: str
    subject: str
    action: str
    scope: str
    context: str
    issued_at: datetime
    expires_at: datetime

    def fresh(self, at: datetime) -> bool:
        return self.issued_at <= at <= self.expires_at


@dataclass(frozen=True)
class Execution:
    execution_id: str
    action: str
    subject: str
    scope: str
    input_version: int
    authorization: Authorization
    idempotent: bool = False
    result_witness: str = ""


@dataclass(frozen=True)
class ChangeRequest:
    change_id: str
    requester: str
    target: str
    requested_scope: FrozenSet[str]
    authorized_scope: FrozenSet[str]
    authority_subject: str = ""
    self_modification: bool = False
    verification_required: bool = True
    recovery_ref: str = ""

    def bounded(self) -> bool:
        if not self.requested_scope.issubset(self.authorized_scope):
            return False
        if self.self_modification and self.authority_subject == self.target:
            return False
        if self.verification_required and not self.recovery_ref:
            return False
        return True


@dataclass
class Kernel:
    """Enforcement facade for GO semantic kernel V1."""
    trusted_evidence_sources: FrozenSet[str] = frozenset()
    consumed_executions: set[str] = field(default_factory=set)

    def authorize(
        self,
        authority: Authority,
        subject: str,
        action: str,
        scope: str,
        context: str,
        at: Optional[datetime] = None,
    ) -> tuple[GateResult, Optional[Authorization]]:
        at = at or now_utc()
        if not authority.permits(subject, action, scope, context, at):
            return GateResult.DENY, None
        return GateResult.ALLOW, Authorization(
            authority.authority_id, subject, action, scope, context, at, authority.valid_until
        )

    def verify_evidence(self, evidence: Evidence, subject: str, scope: str) -> GateResult:
        if evidence.source not in self.trusted_evidence_sources:
            return GateResult.BLOCKED
        if evidence.verification_status != "VERIFIED":
            return GateResult.BLOCKED
        return GateResult.ALLOW if evidence.is_verified(subject, scope) else GateResult.BLOCKED

    def evidence_admission_status(self, evidence: Evidence, subject: str, scope: str) -> GateResult:
        """Check evidence integrity/binding without treating admission as verification."""
        if evidence.source not in self.trusted_evidence_sources:
            return GateResult.BLOCKED
        if evidence.verification_status != "UNVERIFIED":
            return GateResult.BLOCKED
        if evidence.subject != subject or evidence.scope != scope:
            return GateResult.BLOCKED
        if not evidence.source or not evidence.provenance:
            return GateResult.BLOCKED
        if evidence.integrity != evidence.expected_integrity():
            return GateResult.BLOCKED
        return GateResult.ALLOW

    def verify_and_promote_evidence(self, evidence: Evidence, subject: str, scope: str, *, independent_verification: str | None = None) -> tuple[GateResult, Optional[Evidence]]:
        """V2: promotion to VERIFIED requires INDEPENDENT verification.

        A producer may NOT self-promote its own evidence (removed circular path).
        Without an independent verification result, nothing is promoted.
        """
        if independent_verification != "INDEPENDENTLY_VERIFIED":
            return GateResult.BLOCKED, None
        promoted = Evidence(
            evidence.evidence_id, evidence.subject, evidence.scope, evidence.source,
            evidence.captured_at, evidence.provenance, evidence.integrity, "VERIFIED", evidence.claim,
        )
        return GateResult.ALLOW, promoted

    def evaluate_evidence(self, evidence_items: list[Evidence], subject: str, scope: str) -> GateResult:
        verified = [e for e in evidence_items if self.verify_evidence(e, subject, scope) == GateResult.ALLOW]
        claims = {e.claim for e in verified if e.claim}
        if len(claims) > 1:
            return GateResult.CONFLICT
        return GateResult.ALLOW if verified else GateResult.UNKNOWN

    def evaluate_unknown(self) -> GateResult:
        return GateResult.UNKNOWN

    def advisory_to_authorization(self, advisory: Advisory) -> GateResult:
        return GateResult.DENY

    def evidence_to_authorization(self, evidence: Evidence) -> GateResult:
        return GateResult.DENY

    def transition(self, current: State, expected_version: int, new_value: str) -> tuple[GateResult, Optional[State]]:
        if current.lifecycle != "ACTIVE":
            return GateResult.BLOCKED, None
        if expected_version != current.version:
            return GateResult.CONFLICT, None
        if not new_value:
            return GateResult.DENY, None
        return GateResult.ALLOW, State(current.entity_id, new_value, current.version + 1, current.lifecycle)

    def execute_external(self, execution: Execution, at: Optional[datetime] = None) -> GateResult:
        at = at or now_utc()
        if not execution.authorization.fresh(at):
            return GateResult.DENY
        if execution.authorization.subject != execution.subject:
            return GateResult.DENY
        if execution.authorization.action != execution.action:
            return GateResult.DENY
        if execution.authorization.scope != execution.scope:
            return GateResult.DENY
        if not execution.result_witness:
            return GateResult.BLOCKED
        if execution.execution_id in self.consumed_executions and not execution.idempotent:
            return GateResult.DENY
        self.consumed_executions.add(execution.execution_id)
        return GateResult.ALLOW

    def change_allowed(self, change: ChangeRequest) -> GateResult:
        return GateResult.ALLOW if change.bounded() else GateResult.DENY

    def evaluate_resume(self, checkpoint: dict, task: dict|None, repository: dict|None, evidence_records: list[dict], replay_records: list[dict]):
        from runtime.go_runtime.core.checkpoint import sha256_canonical
        from runtime.go_runtime.core.contracts import ResumeDecision
        ident=checkpoint.get("identity",{}); cid=str(ident.get("checkpoint_id","")); tid=str(ident.get("task_id","")); rev=int(ident.get("checkpoint_revision",0) or 0)
        def block(code): return ResumeDecision("BLOCKED",code,cid,tid,rev)
        s=checkpoint.get("schema",{})
        if s.get("name")!="HG_MODEL_CONTEXT_INDEPENDENCE_CHECKPOINT" or s.get("version")!="1.0": return block("CHECKPOINT_SCHEMA_UNSUPPORTED")
        expected=checkpoint.get("canonical_payload_hash",""); payload=dict(checkpoint)
        for k in ("canonical_payload_hash","integrity_algorithm","replay_sequence","replay_digest"): payload.pop(k,None)
        if not expected or sha256_canonical(payload)!=expected: return block("CHECKPOINT_INTEGRITY_INVALID")
        if task is None or task.get("id",task.get("task_id"))!=tid: return block("TASK_IDENTITY_MISMATCH")
        if task.get("state") not in {"QUEUED","RUNNING","RECOVERING","RECOVERY_PENDING"}: return block("TASK_STATE_NOT_RECOVERABLE")
        c=checkpoint.get("contract",{}); current=(task.get("metadata") or {}).get("_contract_hash") or (task.get("metadata") or {}).get("contract_hash")
        if not current: return block("CONTRACT_IDENTITY_MISSING")
        if current!=c.get("contract_hash"): return block("CONTRACT_HASH_MISMATCH")
        if c.get("contract_version")!="1.0": return block("CONTRACT_VERSION_UNSUPPORTED")
        witness=checkpoint.get("repository",{}); current_repo=repository or {}
        if not current_repo: return block("PROVENANCE_INVALID")
        for f,code in (("canonical_head","CANONICAL_HEAD_MISMATCH"),("observed_head","OBSERVED_HEAD_MISMATCH"),("observed_tree","OBSERVED_TREE_MISMATCH")):
            if not witness.get(f) or current_repo.get(f)!=witness.get(f): return block(code)
        if witness.get("provenance_status") not in {"VERIFIED","VALID"}: return block("PROVENANCE_INVALID")
        if witness.get("witness_mode")=="GIT_CHECKOUT" and witness.get("local_dirty") is None: return block("PROVENANCE_INVALID")
        emap={str(e.get("evidence_id")):e for e in evidence_records}
        refs=checkpoint.get("evidence",{}).get("refs",[])
        for r in refs:
            e=emap.get(str(r.get("evidence_id")))
            if e is None: return block("EVIDENCE_REFERENCE_MISSING")
            if (e.get("integrity") or e.get("evidence_digest"))!=r.get("evidence_digest"): return block("EVIDENCE_DIGEST_MISMATCH")
            if e.get("verification_status")!="VERIFIED" or r.get("verification_status")!="VERIFIED": return block("EVIDENCE_VERIFICATION_INSUFFICIENT")
        manifest=checkpoint.get("evidence",{}); refs_payload=sorted([{"evidence_id":r.get("evidence_id"),"evidence_digest":r.get("evidence_digest"),"verification_status":r.get("verification_status")} for r in refs],key=lambda x:x["evidence_id"])
        if manifest.get("manifest_digest")!=sha256_canonical(refs_payload): return block("EVIDENCE_MANIFEST_MISMATCH")
        if any(bool(b.get("blocking")) for b in checkpoint.get("blockers",[])): return block("BLOCKER_ACTIVE")
        acceptance=checkpoint.get("acceptance",{})
        if acceptance.get("aggregate_status")!="PASS" or any(c.get("status")!="PASS" for c in acceptance.get("criteria",[])): return block("ACCEPTANCE_STATE_INVALID")
        na=checkpoint.get("next_action",{})
        if not na.get("instruction"): return block("NEXT_ACTION_MISSING")
        if na.get("deterministic") is not True: return block("NEXT_ACTION_NONDETERMINISTIC")
        seq=int(checkpoint.get("replay_sequence",0) or 0); digest=checkpoint.get("replay_digest","")
        if seq<1 or not digest: return block("REPLAY_INTEGRITY_INVALID")
        previous="GENESIS"
        ordered=sorted(replay_records,key=lambda r:int(r.get("sequence",0)))
        for i,r in enumerate(ordered,1):
            if int(r.get("sequence",0))!=i or r.get("previous_digest")!=previous: return block("REPLAY_INTEGRITY_INVALID")
            rp={"replay_id":r.get("replay_id"),"task_id":r.get("task_id"),"sequence":int(r.get("sequence")),"event_type":r.get("event_type"),"payload":r.get("payload",{}),"previous_digest":r.get("previous_digest"),"occurred_at":r.get("occurred_at")}
            if sha256_canonical(rp)!=r.get("record_digest"): return block("REPLAY_INTEGRITY_INVALID")
            previous=r.get("record_digest")
        if seq>len(ordered) or previous!=digest: return block("REPLAY_INTEGRITY_INVALID")
        matches=[r for r in ordered if r.get("event_type")=="CHECKPOINT_CREATED" and r.get("payload",{}).get("checkpoint_id")==cid]
        if not matches or matches[-1].get("payload",{}).get("checkpoint_hash")!=expected: return block("INTEGRITY_CONFLICT")
        if checkpoint.get("resume",{}).get("model_context_required") is True: return block("INTEGRITY_CONFLICT")
        return ResumeDecision("ALLOW","RESUME_ALLOWED",cid,tid,rev)

# Directive compliance is a policy composition over existing P1-P5 primitives.
# It intentionally uses a mapping rather than introducing a new semantic primitive.
def _directive_compliance(self, directive: dict, execution: Execution, evidence_items: list[Evidence], at: Optional[datetime] = None) -> tuple[GateResult, str]:
    at = at or now_utc()
    required = ("directive_id", "issuer", "responsible_actor", "action", "scope", "context", "authority_id", "issued_at", "due_at", "acceptance_criteria", "status", "provenance")
    if any(not directive.get(k) for k in required):
        return GateResult.UNKNOWN, "MISSING_DIRECTIVE_FIELD"
    if directive["status"] != "ACTIVE":
        return GateResult.DENY, "DIRECTIVE_INACTIVE"
    if execution.subject != directive["responsible_actor"]:
        return GateResult.DENY, "ACTOR_MISMATCH"
    if execution.action != directive["action"] or execution.scope != directive["scope"]:
        return GateResult.DENY, "SCOPE_OR_ACTION_DEVIATION"
    if execution.authorization.authority_id != directive["authority_id"]:
        return GateResult.DENY, "AUTHORITY_MISMATCH"
    if execution.authorization.context != directive["context"]:
        return GateResult.DENY, "CONTEXT_MISMATCH"
    if at > directive["due_at"]:
        return GateResult.DENY, "LATE_OR_EXPIRED"
    if not directive["acceptance_criteria"]:
        return GateResult.BLOCKED, "MISSING_ACCEPTANCE_CRITERIA"
    if not execution.result_witness:
        return GateResult.BLOCKED, "NON_EXECUTION_OR_MISSING_WITNESS"
    verified = self.evaluate_evidence(evidence_items, execution.subject, execution.scope)
    if verified is GateResult.CONFLICT:
        return GateResult.CONFLICT, "CONTRADICTORY_EVIDENCE"
    if verified is not GateResult.ALLOW:
        return GateResult.BLOCKED, "EVIDENCE_NOT_VERIFIED"
    return GateResult.ALLOW, "COMPLIANT"


Kernel.evaluate_directive_compliance = _directive_compliance

