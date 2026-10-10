"""DOMAIN-03 - MTC-1.0 task lifecycle as a fail-closed state machine.

A task may not skip gates, close without satisfied acceptance criteria, enter
APPROVED without an authority record, or leave a terminal state.
"""
from __future__ import annotations

from typing import Any, Mapping

LIFECYCLE_RULE_ID = "HG-MTC-01"

STATES = ("DRAFT", "CONTRACTED", "FORENSIC_BASELINE", "APPROVED", "IMPLEMENTING",
          "VERIFYING", "CLOSED", "BLOCKED", "FAILED", "ABORTED")
TERMINAL_STATES = frozenset({"CLOSED", "FAILED", "ABORTED"})
BLOCKING_STATES = frozenset({"BLOCKED"})

ALLOWED_TRANSITIONS = {
    "DRAFT": {"CONTRACTED", "ABORTED"},
    "CONTRACTED": {"FORENSIC_BASELINE", "BLOCKED", "ABORTED"},
    "FORENSIC_BASELINE": {"APPROVED", "BLOCKED", "ABORTED"},
    "APPROVED": {"IMPLEMENTING", "BLOCKED", "ABORTED"},
    "IMPLEMENTING": {"VERIFYING", "BLOCKED", "FAILED", "ABORTED"},
    "VERIFYING": {"CLOSED", "IMPLEMENTING", "FAILED", "BLOCKED"},
    "BLOCKED": {"CONTRACTED", "FORENSIC_BASELINE", "APPROVED", "IMPLEMENTING",
                "VERIFYING", "ABORTED", "FAILED"},
    "CLOSED": set(), "FAILED": set(), "ABORTED": set(),
}

GATE_REQUIREMENTS = {
    "APPROVED": ("authority_record",),
    "VERIFYING": ("test_evidence",),
    "CLOSED": ("authority_record", "test_evidence", "acceptance_criteria", "closure_evidence"),
    "BLOCKED": ("blocker_record",),
    "FAILED": ("failure_evidence",),
}


class LifecycleError(ValueError):
    """A lifecycle rule was violated."""


def validate_transition(current: str, target: str) -> None:
    if current not in ALLOWED_TRANSITIONS:
        raise LifecycleError(f"{LIFECYCLE_RULE_ID}:UNKNOWN_STATE:{current}")
    if target not in STATES:
        raise LifecycleError(f"{LIFECYCLE_RULE_ID}:UNKNOWN_STATE:{target}")
    if current in TERMINAL_STATES:
        raise LifecycleError(f"{LIFECYCLE_RULE_ID}:TERMINAL_STATE_IMMUTABLE:{current}")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise LifecycleError(f"{LIFECYCLE_RULE_ID}:ILLEGAL_TRANSITION:{current}->{target}")


def _present(record: Mapping[str, Any], key: str) -> bool:
    """Absent = key absent, None, empty string, or empty container."""
    if key not in record:
        return False
    v = record[key]
    if v is None or v == "":
        return False
    if isinstance(v, (dict, list, tuple, set)) and len(v) == 0:
        return False
    return True


def enter(current: str, target: str, record: Mapping[str, Any] | None = None) -> str:
    """Validate a transition and its gate evidence; return the new state name."""
    validate_transition(current, target)
    record = record or {}
    missing = [k for k in GATE_REQUIREMENTS.get(target, ()) if not _present(record, k)]
    if missing:
        raise LifecycleError(f"{LIFECYCLE_RULE_ID}:GATE_{target}_UNSATISFIED:{','.join(missing)}")
    if target == "CLOSED":
        criteria = record.get("acceptance_criteria") or {}
        unmet = [k for k, v in criteria.items() if v is not True]
        if unmet:
            raise LifecycleError(f"{LIFECYCLE_RULE_ID}:GATE_CLOSED_UNSATISFIED:{','.join(sorted(unmet))}")
    return target
