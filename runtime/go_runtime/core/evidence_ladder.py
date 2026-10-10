"""DOMAIN-05 - Evidence Ladder E0-E7.

A status claim may never exceed the evidence level actually achieved.
Self-declaration alone can never reach a tested/integrated/verified claim.
"""
from __future__ import annotations

from typing import Any, Mapping

LADDER_RULE_ID = "HG-EVL-01"

LEVELS = {
    0: "E0_CLAIM", 1: "E1_DESIGN", 2: "E2_SELF_REPORT", 3: "E3_ARTIFACT_EXISTS",
    4: "E4_TESTED_LOCALLY", 5: "E5_INTEGRATED", 6: "E6_DEPLOYED",
    7: "E7_INDEPENDENTLY_VERIFIED",
}
MAX_LEVEL = 7

# minimum evidence level required to legitimately assert each status
STATUS_MIN_LEVEL = {
    "CLAIM": 0, "DESIGN": 1, "SELF_REPORT": 2, "ARTIFACT_EXISTS": 3,
    "TESTED": 4, "IMPLEMENTED": 5, "DEPLOYED": 6, "VERIFIED": 7, "PRODUCTION": 7,
}
# proof that must accompany each level before it can be claimed
LEVEL_REQUIRED_PROOF = {
    4: ("command", "exit_code"),
    5: ("integration_commit",),
    6: ("deployment_id", "target_environment"),
    7: ("independent_verifier", "verification_evidence"),
}


class EvidenceLadderError(ValueError):
    """An evidence-ladder rule was violated."""


def validate_level(level: int) -> int:
    if not isinstance(level, int) or level < 0 or level > MAX_LEVEL:
        raise EvidenceLadderError(f"{LADDER_RULE_ID}:INVALID_LEVEL:{level}")
    return level


def _missing(keys, record: Mapping[str, Any]) -> list[str]:
    """Absent = key absent, None, empty string, or empty container.

    A falsy-but-valid value such as exit_code 0 or False MUST count as present.
    """
    out = []
    for k in keys:
        if k not in record:
            out.append(k); continue
        v = record[k]
        if v is None or v == "":
            out.append(k); continue
        if isinstance(v, (dict, list, tuple, set)) and len(v) == 0:
            out.append(k); continue
    return out


def require_proof(level: int, proof: Mapping[str, Any] | None) -> None:
    validate_level(level)
    proof = proof or {}
    missing = _missing(LEVEL_REQUIRED_PROOF.get(level, ()), proof)
    if missing:
        raise EvidenceLadderError(f"{LADDER_RULE_ID}:LEVEL_{LEVELS[level]}_PROOF_MISSING:{','.join(missing)}")


def assert_claim_supported(status: str, level: int, proof: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Fail closed if a status claim exceeds the achieved evidence level."""
    if status not in STATUS_MIN_LEVEL:
        raise EvidenceLadderError(f"{LADDER_RULE_ID}:UNKNOWN_STATUS:{status}")
    validate_level(level)
    need = STATUS_MIN_LEVEL[status]
    if level < need:
        raise EvidenceLadderError(
            f"{LADDER_RULE_ID}:CLAIM_EXCEEDS_EVIDENCE:{status}_requires_{LEVELS[need]}_got_{LEVELS[level]}")
    require_proof(level, proof)
    return {"rule_id": LADDER_RULE_ID, "status": status, "level": LEVELS[level], "supported": True}


def assert_monotonic(previous_level: int, new_level: int, *, downgrade_reason: str = "") -> int:
    validate_level(previous_level); validate_level(new_level)
    if new_level < previous_level and not downgrade_reason:
        raise EvidenceLadderError(
            f"{LADDER_RULE_ID}:SILENT_DOWNGRADE:{LEVELS[previous_level]}->{LEVELS[new_level]}")
    return new_level
