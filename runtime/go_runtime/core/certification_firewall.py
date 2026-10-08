"""HG V2 Certification Firewall.

An executable gate that lives OUTSIDE the runtime self-assertion path. The runtime
cannot declare itself CERTIFIED. The firewall rejects certification if any critical
dimension is missing, self-issued, stale, or unbound.
"""
from __future__ import annotations

from typing import Any


def evaluate(checks: dict[str, bool], *, blockers: list[str] | None = None) -> dict[str, Any]:
    """checks: named CRITICAL conditions that must all be TRUE to be READY."""
    failed = sorted(k for k, v in checks.items() if v is not True)
    extra = list(blockers or [])
    ready = not failed and not extra
    return {
        "schema": "HG_CERTIFICATION_FIREWALL_V1",
        "result": "CERTIFICATION_READY" if ready else "CERTIFICATION_BLOCKED",
        "passed": sorted(k for k, v in checks.items() if v is True),
        "failed": failed,
        "external_blockers": extra,
        "self_assertion_permitted": False,
    }


def required_checks(
    *,
    authority_root_count: int,
    runtime_self_authority: int,
    runtime_self_verification: int,
    runtime_self_certification: int,
    producer_self_verification: int,
    credential_is_authority: bool,
    completed_implies_success: bool,
    success_implies_truth: bool,
    unknown_is_first_class: bool,
    stale_proof_accepted: bool,
    provenance_bound: bool,
    external_unknown_reconciliation: bool,
    memory_self_certification: bool,
    duplicate_semantic_owner: int,
    orphan_semantic: int,
    critical_injection_blocked: bool,
    ivv_status: str,
    intelligence_ground_truth: bool,
    threat_tests_present: bool,
    assurance_case_complete: bool,
) -> dict[str, Any]:
    checks = {
        "authority_root_count_eq_1": authority_root_count == 1,
        "runtime_self_authority_eq_0": runtime_self_authority == 0,
        "runtime_self_verification_eq_0": runtime_self_verification == 0,
        "runtime_self_certification_eq_0": runtime_self_certification == 0,
        "producer_self_verification_eq_0": producer_self_verification == 0,
        "credential_is_not_authority": credential_is_authority is False,
        "completed_does_not_imply_success": completed_implies_success is False,
        "success_does_not_imply_truth": success_implies_truth is False,
        "unknown_is_first_class": unknown_is_first_class is True,
        "stale_proof_not_accepted": stale_proof_accepted is False,
        "provenance_bound": provenance_bound is True,
        "external_unknown_reconciliation": external_unknown_reconciliation is True,
        "memory_self_certification_eq_0": memory_self_certification is False,
        "duplicate_semantic_owner_eq_0": duplicate_semantic_owner == 0,
        "orphan_semantic_eq_0": orphan_semantic == 0,
        "critical_injection_blocked": critical_injection_blocked is True,
        "independent_verification": ivv_status == "INDEPENDENTLY_VERIFIED",
        "intelligence_ground_truth": intelligence_ground_truth is True,
        "threat_tests_present": threat_tests_present is True,
        "assurance_case_complete": assurance_case_complete is True,
    }
    external = []
    if ivv_status != "INDEPENDENTLY_VERIFIED":
        external.append("IVV_BLOCKED")
    if not intelligence_ground_truth:
        external.append("GROUND_TRUTH_BLOCKED")
    return evaluate(checks, blockers=external)
