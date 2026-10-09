from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

PINNED_SOURCE_SHA256 = "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af"
SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"
BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"
PILLARS = (
    "Tính chính xác của nguồn và độ tin cậy",
    "Toàn quyền tự chủ thực thi và hoàn thành mục tiêu",
    "Học hỏi, cải tiến và sáng tạo",
)
G1_HEADING = "### G1 — TOÀN QUYỀN TỰ CHỦ THỰC THI"


class GovernanceLoadError(RuntimeError):
    pass


def verify_policy(base_dir: Path | None = None) -> dict[str, Any]:
    """Load only the pinned V1 source colocated with this runtime; fail closed."""
    base = Path(base_dir) if base_dir else Path(__file__).resolve().parent
    source = base / SOURCE_NAME
    binding_path = base / BINDING_NAME
    if not source.is_file():
        raise GovernanceLoadError(f"canonical source missing: {source.name}")
    raw = source.read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != PINNED_SOURCE_SHA256:
        raise GovernanceLoadError("canonical V1 SHA-256 mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernanceLoadError("canonical V1 is not UTF-8") from exc
    if text.count(G1_HEADING) != 1:
        raise GovernanceLoadError("G1 heading missing or duplicated")
    positions = [text.find(pillar) for pillar in PILLARS]
    if any(pos < 0 for pos in positions) or positions != sorted(positions):
        raise GovernanceLoadError("three-pillar order missing or changed")
    if not binding_path.is_file():
        raise GovernanceLoadError("owner approval binding missing")
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceLoadError("owner approval binding unreadable") from exc
    if binding.get("source_sha256") != PINNED_SOURCE_SHA256:
        raise GovernanceLoadError("approval binding does not match pinned V1")
    if binding.get("approval_status") != "OWNER_CONFIRMED_APPROVED_IN_CURRENT_CONVERSATION":
        raise GovernanceLoadError("owner approval is not recorded")
    return {
        "status": "VERIFIED",
        "ruleset": "MASTER GOVERNANCE RULESET V1",
        "source": source.name,
        "source_sha256": actual_hash,
        "g1_count": text.count(G1_HEADING),
        "pillars_in_required_order": True,
        "approval_binding": binding_path.name,
        "source_internal_metadata_conflict": "DISCLOSED_IN_BINDING",
        "legacy_policy_fallback": False,
        "execution_status": "EXECUTION_NOT_RUN",
    }


def authorize_action(
    *,
    action: str,
    target: str,
    delegated_scope: str,
    capability_available: bool,
    authorization_evidence: str,
) -> dict[str, Any]:
    """Fail-closed gate. An ALLOW result is not execution evidence."""
    missing = []
    if not action.strip():
        missing.append("action")
    if not target.strip():
        missing.append("target")
    if not delegated_scope.strip():
        missing.append("delegated_scope")
    if not capability_available:
        missing.append("capability")
    if not authorization_evidence.strip():
        missing.append("authorization_evidence")
    return {
        "decision": "DENY" if missing else "ALLOW_TO_PROCEED_TO_EXECUTOR",
        "missing": missing,
        "execution_performed": False,
        "note": "ALLOW_TO_PROCEED_TO_EXECUTOR is not proof that an action was executed.",
    }


def execute_governed_action(
    *,
    action: str,
    target: str,
    delegated_scope: str,
    capability_available: bool,
    authorization_evidence: str,
    executor: Callable[[], Any],
    policy_base: Path | None = None,
) -> dict[str, Any]:
    """Verify V1, gate authority, execute only the supplied executor, and hash evidence."""
    policy = verify_policy(policy_base)
    gate = authorize_action(
        action=action,
        target=target,
        delegated_scope=delegated_scope,
        capability_available=capability_available,
        authorization_evidence=authorization_evidence,
    )
    if gate["decision"] != "ALLOW_TO_PROCEED_TO_EXECUTOR":
        return {
            "status": "DENIED",
            "execution_performed": False,
            "missing": gate["missing"],
            "source_sha256": policy["source_sha256"],
        }
    try:
        result = executor()
        record = {
            "status": "EXECUTED",
            "action": action,
            "target": target,
            "result": str(result),
            "source_sha256": policy["source_sha256"],
        }
    except Exception as exc:
        record = {
            "status": "EXECUTION_FAILED",
            "action": action,
            "target": target,
            "error_type": type(exc).__name__,
            "source_sha256": policy["source_sha256"],
        }
    record["evidence_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    record["execution_performed"] = record["status"] in ("EXECUTED", "EXECUTION_FAILED")
    return record


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "status"
    try:
        state = verify_policy()
    except GovernanceLoadError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    if command in ("status", "--self-test"):
        state["self_test"] = "PASS" if command == "--self-test" else "NOT_REQUESTED"
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps({"status": "BLOCKED", "reason": "unsupported command"}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
