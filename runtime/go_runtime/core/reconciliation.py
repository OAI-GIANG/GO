"""HG V2 external-execution reconciliation (single owner of external truth).

Invariant: a remote side effect is NEVER reported COMPLETED just because the
local call returned. If a request may have applied but the response is missing,
the state is UNKNOWN (never SUCCESS / never FAILED), and blind retry is refused.
"""
from __future__ import annotations


class ExternalState:
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    RECONCILED = "RECONCILED"


def classify(
    *,
    sent_ok: bool,
    authorized: bool,
    response_received: bool,
    response_ok: bool = False,
    side_effect_possible: bool = False,
) -> str:
    """Derive the external state. Lost response after a possible side effect => UNKNOWN."""
    if not authorized:
        return ExternalState.FAILED
    if not sent_ok:
        return ExternalState.FAILED
    if response_received:
        return ExternalState.COMPLETED if response_ok else ExternalState.FAILED
    # no response
    if side_effect_possible:
        return ExternalState.UNKNOWN
    return ExternalState.RECONCILIATION_PENDING


def may_retry(state: str) -> bool:
    """Blind retry only when NO side effect can have occurred."""
    return state in {ExternalState.FAILED, ExternalState.RECONCILIATION_PENDING}


def requires_reconciliation(state: str) -> bool:
    return state in {ExternalState.UNKNOWN, ExternalState.RECONCILIATION_PENDING}


def reconcile(*, observed: str, recovered_response_ok: bool | None) -> str:
    """Move UNKNOWN/PENDING to RECONCILED using out-of-band observation."""
    if observed not in {ExternalState.UNKNOWN, ExternalState.RECONCILIATION_PENDING}:
        return observed
    if recovered_response_ok is None:
        return ExternalState.RECONCILIATION_PENDING
    return ExternalState.COMPLETED if recovered_response_ok else ExternalState.FAILED
