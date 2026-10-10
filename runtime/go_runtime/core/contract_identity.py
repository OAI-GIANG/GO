"""HG contract-identity migration (PLAN-04).

HG owns its own contract identifiers. Legacy LOVE-* identifiers remain readable
during a bounded compatibility window so persisted records keep replaying.

Write side : emit HG-* only.
Read side  : accept HG-* and legacy LOVE-* (window), normalise to HG-*.
Rollback   : the legacy mapping is data, not code paths; removing a window entry
             is a one-line revert once replay proves no legacy reads remain.
"""
from __future__ import annotations

CANONICAL_IDENTITY = "HG"
LEGACY_IDENTITY = "LOVE"
COMPAT_WINDOW_ID = "HG-ID-COMPAT-1"

LEGACY_TO_CANONICAL = {
    "LOVE-TASK-CONTRACT-1.0": "HG-TASK-CONTRACT-1.0",
    "LOVE_TASK_CONTRACT": "HG_TASK_CONTRACT",
    "LOVE-SUBMISSION-1.0": "HG-SUBMISSION-1.0",
    "LOVE-LEARNING-1.0": "HG-LEARNING-1.0",
    "LOVE-KNOWLEDGE-HINT-1.0": "HG-KNOWLEDGE-HINT-1.0",
}
CANONICAL_IDENTIFIERS = frozenset(LEGACY_TO_CANONICAL.values())
LEGACY_IDENTIFIERS = frozenset(LEGACY_TO_CANONICAL)


class ContractIdentityError(ValueError):
    """An identifier is not a known HG identifier nor an accepted legacy one."""


def to_canonical(identifier: str) -> str:
    return LEGACY_TO_CANONICAL.get(identifier, identifier)


def is_accepted(identifier: str) -> bool:
    return identifier in CANONICAL_IDENTIFIERS or identifier in LEGACY_IDENTIFIERS


def is_legacy(identifier: str) -> bool:
    return identifier in LEGACY_IDENTIFIERS


def require_accepted(identifier: str) -> str:
    if not is_accepted(identifier):
        raise ContractIdentityError(f"UNKNOWN_CONTRACT_IDENTITY:{identifier}")
    return to_canonical(identifier)


def normalize_identity_fields(payload: dict) -> dict:
    """Normalise identity-bearing fields; leave everything else byte-identical."""
    out = dict(payload)
    for key in ("schema_version", "contract_name", "_contract_name"):
        value = out.get(key)
        if isinstance(value, str):
            out[key] = require_accepted(value)
    return out
