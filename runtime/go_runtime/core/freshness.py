"""HG V2 freshness policy (GI-08).

Critical evidence must be bound to a source commit/tree and a timestamp; evidence
that is not bound, or whose bound source no longer matches, is STALE/UNBOUND and
cannot serve as current proof.
"""
from __future__ import annotations

from typing import Any


def status(
    evidence_provenance: dict[str, Any] | None,
    *,
    source_commit: str,
    source_tree: str,
    issued_ts: float | None,
    now_ts: float,
    max_age_s: float = 86400.0,
) -> str:
    if not evidence_provenance:
        return "UNBOUND"
    ec = str(evidence_provenance.get("source_commit", ""))
    et = str(evidence_provenance.get("source_tree", ""))
    if not ec or not et:
        return "UNBOUND"
    if ec != source_commit or et != source_tree:
        return "STALE"
    if issued_ts is None:
        return "UNBOUND"
    if now_ts - issued_ts > max_age_s:
        return "STALE"
    return "CURRENT"


def is_current(result: str) -> bool:
    return result == "CURRENT"
