"""HG V2 Certification Firewall.

The firewall is an external admission gate. It does not accept caller-supplied
booleans/statuses as certification truth. It consumes canonical evidence only.

P0-D invariant:
CanonicalEvidence -> integrity/provenance/IVV/truth validation -> firewall checks
-> CERTIFICATION_READY/BLOCKED.

Authority, provenance and evidence semantics remain owned by their existing
canonical modules.
"""
from __future__ import annotations

from typing import Any, Iterable

from .evidence import CanonicalEvidence, _digest


REQUIRED_CHECKS = (
    "authority_root_count_eq_1",
    "runtime_self_authority_eq_0",
    "runtime_self_verification_eq_0",
    "runtime_self_certification_eq_0",
    "producer_self_verification_eq_0",
    "credential_is_not_authority",
    "completed_does_not_imply_success",
    "success_does_not_imply_truth",
    "unknown_is_first_class",
    "stale_proof_not_accepted",
    "provenance_bound",
    "external_unknown_reconciliation",
    "memory_self_certification_eq_0",
    "duplicate_semantic_owner_eq_0",
    "orphan_semantic_eq_0",
    "critical_injection_blocked",
    "independent_verification",
    "intelligence_ground_truth",
    "threat_tests_present",
    "assurance_case_complete",
)


def _evaluate_checks(checks: dict[str, bool], *, blockers: list[str] | None = None) -> dict[str, Any]:
    failed = sorted(k for k, v in checks.items() if v is not True)
    extra = list(blockers or [])
    ready = not failed and not extra
    return {
        "schema": "HG_CERTIFICATION_FIREWALL_V2",
        "result": "CERTIFICATION_READY" if ready else "CERTIFICATION_BLOCKED",
        "passed": sorted(k for k, v in checks.items() if v is True),
        "failed": failed,
        "external_blockers": extra,
        "self_assertion_permitted": False,
    }


def _valid_canonical_evidence(item: CanonicalEvidence) -> bool:
    if not isinstance(item, CanonicalEvidence):
        return False
    if not item.evidence_id or not item.producer or not item.provenance:
        return False
    if item.verification_status != "INDEPENDENTLY_VERIFIED":
        return False
    if item.truth_status != "VERIFIED":
        return False
    payload = item._payload_without_digest()
    return item.evidence_digest == _digest(payload)


def evaluate_evidence_backed(
    evidence_items: Iterable[CanonicalEvidence],
    *,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate certification only from canonical, independently verified evidence.

    Each criterion must be represented by exactly one canonical evidence record
    whose observation contains:
        {"firewall_check": "<criterion>", "value": true|false}

    Missing, duplicate, unverified, unverifiable, or false criteria fail closed.
    """
    items = list(evidence_items)
    by_check: dict[str, list[CanonicalEvidence]] = {}
    invalid: list[str] = []

    for item in items:
        if not _valid_canonical_evidence(item):
            invalid.append(str(getattr(item, "evidence_id", "INVALID_EVIDENCE")))
            continue
        check = str((item.observation or {}).get("firewall_check") or "")
        if not check:
            invalid.append(item.evidence_id)
            continue
        by_check.setdefault(check, []).append(item)

    checks: dict[str, bool] = {}
    evidence_refs: dict[str, str] = {}

    for check in REQUIRED_CHECKS:
        matches = by_check.get(check, [])
        if len(matches) != 1:
            checks[check] = False
            continue
        item = matches[0]
        checks[check] = (item.observation or {}).get("value") is True
        evidence_refs[check] = item.evidence_id

    extra_checks = sorted(set(by_check) - set(REQUIRED_CHECKS))
    result = _evaluate_checks(checks, blockers=list(blockers or []) + (
        ["INVALID_CANONICAL_EVIDENCE"] if invalid else []
    ))

    result["evidence_refs"] = evidence_refs
    result["invalid_evidence_ids"] = sorted(set(invalid))
    result["unexpected_checks"] = extra_checks
    return result
