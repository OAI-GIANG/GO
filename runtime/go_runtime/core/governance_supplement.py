"""HG governance supplement - machine-enforceable rules (DRAFT, G2-gated).

Rules implemented here are MECHANICAL, not prose:

  HG-APR-01  approval binding integrity   -> delegates to verify_governance_source()
  HG-PATCH-01 patch acceptance gate       -> validate_patch_record()
  HG-CRED-01 credential/secret containment-> scan_for_secrets()
  HG-HUM-01  human approval for destructive/irreversible actions
                                          -> require_destructive_approval()

These rules do NOT resolve the authority dispute (AUTH-CONFLICT-01). They are
enforcement mechanisms that must be adopted by an authorised governance act.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .governance_source import GovernanceSourceError, verify_governance_source


class GovernanceRuleError(ValueError):
    """A supplement rule was violated."""


class PatchGateError(GovernanceRuleError):
    pass


class CredentialContainmentError(GovernanceRuleError):
    pass


class HumanApprovalError(GovernanceRuleError):
    pass


# --- HG-APR-01 -----------------------------------------------------------------
APPROVAL_RULE_ID = "HG-APR-01"


def verify_approval_authority(root: str | Path | None = None) -> dict[str, Any]:
    """Fail closed unless the canonical source AND its approval binding verify."""
    try:
        return verify_governance_source(root)
    except GovernanceSourceError as exc:
        raise GovernanceRuleError(f"{APPROVAL_RULE_ID}:{exc}") from exc


# --- HG-PATCH-01 ---------------------------------------------------------------
PATCH_RULE_ID = "HG-PATCH-01"
PATCH_REQUIRED_FIELDS = (
    "FINDING", "ROOT_CAUSE", "MINIMAL_PATCH", "POSITIVE_TEST",
    "NEGATIVE_TEST", "REGRESSION_TEST", "EVIDENCE", "CHECKPOINT",
)
# A claim is only admissible with the evidence that claim requires.
CLAIM_REQUIRED_EVIDENCE = {
    "DESIGN": (),
    "TESTED": ("TEST_EXECUTION",),
    "IMPLEMENTED": ("TEST_EXECUTION", "INTEGRATION_COMMIT"),
    "DEPLOYED": ("TEST_EXECUTION", "INTEGRATION_COMMIT", "DEPLOYMENT_ID"),
    "VERIFIED": ("TEST_EXECUTION", "INTEGRATION_COMMIT", "VERIFICATION_EVIDENCE"),
}
ALLOWED_CLAIMS = tuple(CLAIM_REQUIRED_EVIDENCE)


def validate_patch_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a patch record and its self-declared status claim."""
    missing = [f for f in PATCH_REQUIRED_FIELDS if not record.get(f)]
    if missing:
        raise PatchGateError(f"{PATCH_RULE_ID}:MISSING_FIELDS:{','.join(missing)}")
    claim = record.get("STATUS")
    if claim not in CLAIM_REQUIRED_EVIDENCE:
        raise PatchGateError(f"{PATCH_RULE_ID}:UNKNOWN_STATUS:{claim}")
    evidence = record.get("EVIDENCE")
    if not isinstance(evidence, Mapping):
        raise PatchGateError(f"{PATCH_RULE_ID}:EVIDENCE_NOT_A_STRUCTURED_RECORD")
    gaps = [k for k in CLAIM_REQUIRED_EVIDENCE[claim] if not evidence.get(k)]
    if gaps:
        raise PatchGateError(f"{PATCH_RULE_ID}:STATUS_{claim}_UNSUPPORTED:{','.join(gaps)}")
    return {"rule_id": PATCH_RULE_ID, "status": claim, "accepted": True}


# --- HG-CRED-01 ----------------------------------------------------------------
CRED_RULE_ID = "HG-CRED-01"
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bgho_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}={0,2}"),
)
_SCAN_SUFFIXES = (".py", ".md", ".json", ".yaml", ".yml", ".toml", ".sh", ".txt", ".csv")
_SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}


def scan_for_secrets(root: str | Path, *, extra_deny: Iterable[str] = ()) -> list[str]:
    """Return violations as 'relative/path:line'. Empty list means clean."""
    root = Path(root)
    patterns = list(_SECRET_PATTERNS) + [re.compile(p) for p in extra_deny]
    violations: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in _SCAN_SUFFIXES:
            continue
        if _SKIP_DIRS & set(p.parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(rx.search(line) for rx in patterns):
                violations.append(f"{p.relative_to(root).as_posix()}:{i}")
    return violations


def assert_no_secrets(root: str | Path, *, extra_deny: Iterable[str] = ()) -> dict[str, Any]:
    v = scan_for_secrets(root, extra_deny=extra_deny)
    if v:
        raise CredentialContainmentError(f"{CRED_RULE_ID}:SECRET_MATERIAL:{','.join(v[:5])}")
    return {"rule_id": CRED_RULE_ID, "violations": 0, "status": "CLEAN"}


# --- HG-HUM-01 -----------------------------------------------------------------
HUMAN_RULE_ID = "HG-HUM-01"
DESTRUCTIVE_REQUIRED_FIELDS = (
    "TARGET", "JUSTIFICATION", "BLAST_RADIUS", "BACKUP",
    "REVERSIBILITY", "APPROVAL_REQUIREMENT", "EXECUTION_PLAN", "VERIFICATION",
)
DESTRUCTIVE_CLASSES = frozenset({
    "DELETE_REPOSITORY", "DELETE_DATABASE", "DELETE_VOLUME", "DELETE_USER_DATA",
    "HISTORY_REWRITE", "FORCE_PUSH", "DELETE_TAG", "REVOKE_CREDENTIAL",
    "ROTATE_CREDENTIAL", "DELETE_EVIDENCE", "CHANGE_OWNERSHIP", "CHANGE_PROTECTION",
    "IRREVERSIBLE_MIGRATION", "DESTROY_ENVIRONMENT", "DELETE_CONFIG",
})


def require_destructive_approval(action_class: str, record: Mapping[str, Any]) -> dict[str, Any]:
    """Destructive/irreversible actions need a complete record AND explicit approval."""
    if action_class not in DESTRUCTIVE_CLASSES:
        return {"rule_id": HUMAN_RULE_ID, "action_class": action_class, "approval_required": False}
    missing = [f for f in DESTRUCTIVE_REQUIRED_FIELDS if not record.get(f)]
    if missing:
        raise HumanApprovalError(f"{HUMAN_RULE_ID}:INCOMPLETE_RECORD:{','.join(missing)}")
    if not record.get("approved_by"):
        raise HumanApprovalError(f"{HUMAN_RULE_ID}:NOT_APPROVED:{action_class}")
    if str(record.get("REVERSIBILITY", "")).upper() == "IRREVERSIBLE" and not record.get("approval_id"):
        raise HumanApprovalError(f"{HUMAN_RULE_ID}:IRREVERSIBLE_REQUIRES_EXPLICIT_APPROVAL_ID")
    return {"rule_id": HUMAN_RULE_ID, "action_class": action_class,
            "approval_required": True, "approved_by": record["approved_by"]}
