"""HG_CORROBORATION_POLICY_V1 — independence is judged by domains.

Two evidence items from the SAME source/authority/failure/data/observer domain are
NOT independent corroboration (mandate §25). Same source x2 is rejected.
"""
from __future__ import annotations

from typing import Any

DOMAINS = ("source_domain", "authority_domain", "failure_domain", "data_domain", "observer_domain")


def _domains(item: dict[str, Any]) -> dict[str, str]:
    return {d: str(item.get(d, "")) for d in DOMAINS}


def independent_pair(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str]:
    da, db = _domains(a), _domains(b)
    if da["source_domain"] and da["source_domain"] == db["source_domain"]:
        return False, "SAME_SOURCE_DOMAIN"
    if da["authority_domain"] and da["authority_domain"] == db["authority_domain"]:
        return False, "SAME_AUTHORITY_DOMAIN"
    if da["failure_domain"] and da["failure_domain"] == db["failure_domain"]:
        return False, "SAME_FAILURE_DOMAIN"
    if da["observer_domain"] and da["observer_domain"] == db["observer_domain"]:
        return False, "SAME_OBSERVER_DOMAIN"
    return True, "INDEPENDENT"


def corroborate(claim: str, items: list[dict[str, Any]], *, min_independent: int = 2) -> dict[str, Any]:
    """A claim is corroborated only when >= min_independent mutually-independent items agree."""
    agreeing = [i for i in items if i.get("claim") == claim and i.get("truth_status") == "VERIFIED"]
    if len(agreeing) < 2:
        return {"claim": claim, "corroborated": False, "reason": "INSUFFICIENT_EVIDENCE", "independent_count": len(agreeing)}
    independent = 1
    anchor = agreeing[0]
    for other in agreeing[1:]:
        ok, _ = independent_pair(anchor, other)
        if ok:
            independent += 1
    return {
        "claim": claim, "corroborated": independent >= min_independent,
        "independent_count": independent, "policy": "HG_CORROBORATION_POLICY_V1",
        "reason": "OK" if independent >= min_independent else "NOT_INDEPENDENT",
    }
