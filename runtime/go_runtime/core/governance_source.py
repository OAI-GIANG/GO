from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PINNED_SOURCE_SHA256 = "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af"
SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"
BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"
G1_HEADING = "### G1 — TOÀN QUYỀN TỰ CHỦ THỰC THI"
PILLARS = (
    "Tính chính xác của nguồn và độ tin cậy",
    "Toàn quyền tự chủ thực thi và hoàn thành mục tiêu",
    "Học hỏi, cải tiến và sáng tạo",
)


class GovernanceSourceError(RuntimeError):
    """The canonical V1 source or its authority binding cannot be verified."""


def load_governance_text(root_dir: str | Path | None = None) -> str:
    """Return exact UTF-8 V1 text only after the source and authority binding verify."""
    root = Path(root_dir).resolve() if root_dir is not None else Path(__file__).resolve().parents[3]
    verify_governance_source(root)
    return (root / "control" / SOURCE_NAME).read_text(encoding="utf-8")


def verify_governance_source(root_dir: str | Path | None = None) -> dict[str, Any]:
    """Verify the immutable V1 source and its explicit owner-direction binding.

    This establishes source integrity and authority-record consistency only. It does
    not claim that every semantic rule has been independently proven at runtime.
    """
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
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_UNREADABLE") from exc
    if binding.get("source_sha256") != PINNED_SOURCE_SHA256:
        raise GovernanceSourceError("V1_APPROVAL_BINDING_HASH_MISMATCH")
    if binding.get("approval_status") != "OWNER_CONFIRMED_APPROVED_IN_CURRENT_CONVERSATION":
        raise GovernanceSourceError("V1_OWNER_DIRECTION_NOT_BOUND")
    return {
        "status": "VERIFIED",
        "ruleset": "MASTER GOVERNANCE RULESET V1",
        "source": str(source.relative_to(root)).replace("\\", "/"),
        "source_sha256": actual,
        "g1_count": 1,
        "pillars_in_required_order": True,
        "approval_binding": str(binding_path.relative_to(root)).replace("\\", "/"),
        "source_internal_metadata_conflict": "DISCLOSED_IN_BINDING",
        "legacy_policy_fallback": False,
        "verification_scope": "SOURCE_INTEGRITY_AND_AUTHORITY_BINDING_ONLY",
    }
