"""HG V2 canonical epistemic state model (single semantic owner).

Separates states that were previously collapsed:
  EXECUTION_STATE, TASK_OUTCOME, TRUTH_STATUS, VERIFICATION_STATUS, ASSURANCE_STATUS.

Global invariants enforced:
  GI-01 COMPLETED != TASK_SUCCESS
  GI-02 TASK_SUCCESS != TRUTH_VERIFIED
  GI-03 EVIDENCE_INTEGRITY != TRUTHFULNESS
  GI-07 UNKNOWN = FIRST_CLASS_STATE  (never auto-promoted to SUCCESS)

Producer-observed execution can only ever yield VERIFICATION_STATUS=SELF_OBSERVED,
never INDEPENDENTLY_VERIFIED. Only an independent verifier (see ivv.py) may move
truth to VERIFIED.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class ExecutionState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    ABORTED = "ABORTED_BY_KILL"
    UNKNOWN = "UNKNOWN"


class TaskOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


class TruthStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    SELF_OBSERVED = "SELF_OBSERVED"          # producer observation only (not independent)
    INDEPENDENTLY_VERIFIED = "INDEPENDENTLY_VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNVERIFIED = "UNVERIFIED"


class AssuranceStatus(str, Enum):
    UNASSESSED = "UNASSESSED"
    ASSESSED = "ASSESSED"
    BLOCKED = "BLOCKED"


_TERMINAL_FAILURE = {
    ExecutionState.FAILED.value,
    ExecutionState.CANCELLED.value,
    ExecutionState.TIMED_OUT.value,
    ExecutionState.ABORTED.value,
}


def derive_task_outcome(
    execution_state: str,
    truth_status: str = TruthStatus.UNVERIFIED.value,
    verification_status: str = VerificationStatus.SELF_OBSERVED.value,
) -> str:
    """COMPLETED alone NEVER yields SUCCESS.

    SUCCESS requires: execution COMPLETED **and** truth VERIFIED **and**
    verification INDEPENDENTLY_VERIFIED. Otherwise UNKNOWN (or FAILURE).
    """
    if execution_state in _TERMINAL_FAILURE:
        return TaskOutcome.FAILURE.value
    if execution_state == ExecutionState.COMPLETED.value:
        if (
            verification_status == VerificationStatus.INDEPENDENTLY_VERIFIED.value
            and truth_status == TruthStatus.VERIFIED.value
        ):
            return TaskOutcome.SUCCESS.value
        return TaskOutcome.UNKNOWN.value
    return TaskOutcome.UNKNOWN.value


def envelope(
    *,
    execution_state: str,
    truth_status: str = TruthStatus.UNVERIFIED.value,
    verification_status: str = VerificationStatus.SELF_OBSERVED.value,
    assurance_status: str = AssuranceStatus.UNASSESSED.value,
) -> dict[str, Any]:
    """Canonical, non-collapsed epistemic envelope for any result."""
    return {
        "execution_state": ExecutionState(execution_state).value,
        "task_outcome": derive_task_outcome(execution_state, truth_status, verification_status),
        "truth_status": TruthStatus(truth_status).value,
        "verification_status": VerificationStatus(verification_status).value,
        "assurance_status": AssuranceStatus(assurance_status).value,
    }


def integrity_is_not_truth(*, integrity_ok: bool) -> dict[str, Any]:
    """GI-03: a valid digest proves only that the artifact matches the digest model,
    never that its claim is true."""
    return {
        "integrity_ok": bool(integrity_ok),
        "truth_status": TruthStatus.UNVERIFIED.value,
        "note": "integrity does not imply truth",
    }
