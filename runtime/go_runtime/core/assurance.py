"""HG V2 assurance profile + assurance case.

Assurance is multi-dimensional: a single `verified = true` boolean is forbidden.
An assurance case is a traceability layer (CLAIM -> RISK -> CONTROL -> TEST ->
EVIDENCE -> VERIFIER -> ASSURANCE); it is NOT an authority and cannot self-certify.
"""
from __future__ import annotations

from typing import Any

DIMENSIONS = (
    "EPISTEMIC", "AUTHORITY", "EXECUTION", "EVIDENCE", "IVV", "MEMORY",
    "PROVENANCE", "INTELLIGENCE", "SECURITY", "RECONCILIATION", "CERTIFICATION",
)

STATUS = ("UNVERIFIED", "PARTIAL", "VERIFIED", "INDEPENDENTLY_VERIFIED", "BLOCKED", "STALE", "CONTRADICTED")


def dimension(*, status: str, evidence: str, freshness: str, verifier: str, strength: str, limitations: str, blockers: list[str] | None = None) -> dict[str, Any]:
    if status not in STATUS:
        raise ValueError("invalid assurance dimension status: " + status)
    return {
        "status": status, "evidence": evidence, "freshness": freshness, "verifier": verifier,
        "strength": strength, "limitations": limitations, "blockers": list(blockers or []),
    }


def profile(entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = [d for d in DIMENSIONS if d not in entries]
    return {
        "schema": "HG_ASSURANCE_PROFILE_V1",
        "dimensions": {d: entries.get(d, dimension(status="UNVERIFIED", evidence="", freshness="", verifier="", strength="none", limitations="not assessed")) for d in DIMENSIONS},
        "complete": not missing,
        "missing": missing,
    }


def case_step(*, claim: str, risk: str, control: str, test: str, evidence: str, verifier: str, assurance: str) -> dict[str, Any]:
    if not all([claim, risk, control, test, evidence, verifier]):
        raise ValueError("assurance case step incomplete (CLAIM->RISK->CONTROL->TEST->EVIDENCE->VERIFIER)")
    return {"claim": claim, "risk": risk, "control": control, "test": test, "evidence": evidence, "verifier": verifier, "assurance": assurance}


def assurance_case(steps: list[dict[str, Any]], *, unresolved: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": "HG_ASSURANCE_CASE_V1",
        "steps": steps,
        "complete": not unresolved,
        "unresolved": list(unresolved or []),
    }
