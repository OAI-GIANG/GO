"""HARDENED PROPOSAL - fixes GOV-GAP-02 (binding integrity). SCRATCH ONLY, not canonical."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PINNED_SOURCE_SHA256 = "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af"
BINDING_PINNED_SHA256 = "538c0b4054d17f4ff6aa6beb6eecfb3e37c09c1986aec236a458b14ad8e66b17"
SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"
SOURCE_REL_PATH = "control/MASTER_GOVERNANCE_RULESET_V1.md"
RULESET_NAME = "MASTER GOVERNANCE RULESET V1"
BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"
G1_HEADING = "### G1 — TOÀN QUYỀN TỰ CHỦ THỰC THI"
PILLARS = (
    "Tính chính xác của nguồn và độ tin cậy",
    "Toàn quyền tự chủ thực thi và hoàn thành mục tiêu",
    "Học hỏi, cải tiến và sáng tạo",
)
BINDING_REQUIRED_FIELDS = frozenset({
    "record_type", "ruleset", "source_path", "source_sha256", "approval_status",
    "approval_scope", "source_internal_metadata_conflict", "runtime_status",
    "created_by", "note",
})
BINDING_ALLOWED_FIELDS = BINDING_REQUIRED_FIELDS
EXPECTED_RECORD_TYPE = "OWNER_APPROVAL_BINDING"
EXPECTED_APPROVAL_STATUS = "OWNER_CONFIRMED_APPROVED_IN_CURRENT_CONVERSATION"


class GovernanceSourceError(RuntimeError):
    """The canonical V1 source or its authority binding cannot be verified."""


def load_governance_text(root_dir: str | Path | None = None) -> str:
    root = Path(root_dir).resolve() if root_dir is not None else Path(__file__).resolve().parents[3]
    verify_governance_source(root)
    return (root / "control" / SOURCE_NAME).read_text(encoding="utf-8")


def verify_governance_source(root_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(root_dir).resolve() if root_dir is not None else Path(__file__).resolve().parents[3]
    control = root / "control"
    source = control / SOURCE_NAME
    binding_path = control / BINDING_NAME
    if not source.is_file():
        raise GovernanceSourceError("V1_CANONICAL_SOURCE_MISSING")
    raw = source.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != PINNED_SOURCE_SHA256:
        raise GovernanceSourceError("V1_CANONICAL_SOURCE_HASH_MISMATCH")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernanceSourceError("V1_CANONICAL_SOURCE_NOT_UTF8") from exc
    if text.count(G1_HEADING) != 1:
        raise GovernanceSourceError("V1_G1_HEADING_MISSING_OR_DUPLICATED")
    positions = [text.find(pillar) for pillar in PILLARS]
    if any(pos < 0 for pos in positions) or positions != sorted(positions):
        raise GovernanceSourceError("V1_REQUIRED_PILLAR_ORDER_INVALID")
    if not binding_path.is_file():
        raise GovernanceSourceError("V1_APPROVAL_BINDING_MISSING")

    binding_raw = binding_path.read_bytes()
    # LAYER 1 - whole-binding integrity pin (NEW; fixes GOV-GAP-02)
    binding_actual = hashlib.sha256(binding_raw).hexdigest()
    if binding_actual != BINDING_PINNED_SHA256:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_INTEGRITY_MISMATCH")

    try:
        binding = json.loads(binding_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_UNREADABLE") from exc
    if not isinstance(binding, dict):
        raise GovernanceSourceError("V1_APPROVAL_BINDING_NOT_AN_OBJECT")

    # LAYER 2 - strict schema (NEW)
    keys = set(binding)
    missing = BINDING_REQUIRED_FIELDS - keys
    if missing:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_MISSING_FIELD:" + ",".join(sorted(missing)))
    unexpected = keys - BINDING_ALLOWED_FIELDS
    if unexpected:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_UNEXPECTED_FIELD:" + ",".join(sorted(unexpected)))

    # LAYER 3 - authority binding to exact source, ruleset and owner direction (STRENGTHENED)
    if binding.get("record_type") != EXPECTED_RECORD_TYPE:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_RECORD_TYPE_MISMATCH")
    if binding.get("ruleset") != RULESET_NAME:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_RULESET_MISMATCH")
    if binding.get("source_path") != SOURCE_REL_PATH:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_SOURCE_PATH_MISMATCH")
    if binding.get("source_sha256") != PINNED_SOURCE_SHA256:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_HASH_MISMATCH")
    if binding.get("approval_status") != EXPECTED_APPROVAL_STATUS:
        raise GovernanceSourceError("V1_OWNER_DIRECTION_NOT_BOUND")

    return {
        "status": "VERIFIED",
        "ruleset": RULESET_NAME,
        "source": str(source.relative_to(root)).replace("\\", "/"),
        "source_sha256": actual,
        "g1_count": 1,
        "pillars_in_required_order": True,
        "approval_binding": str(binding_path.relative_to(root)).replace("\\", "/"),
        "approval_binding_sha256": binding_actual,
        "source_internal_metadata_conflict": "DISCLOSED_IN_BINDING",
        "legacy_policy_fallback": False,
        "verification_scope": "SOURCE_INTEGRITY_AND_AUTHORITY_BINDING_ONLY",
        # a self-declared runtime status is NOT runtime evidence
        "runtime_status_claim": {
            "value": binding.get("runtime_status"),
            "is_evidence": False,
            "note": "Self-declared field. Never satisfies runtime enforcement or deployment acceptance.",
        },
    }
