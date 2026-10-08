"""HG V2 Independent Verification & Validation (IV&V) — no self-verification.

GI-05 PRODUCER != INDEPENDENT_VERIFIER.
A producer may emit SELF_OBSERVED evidence; it may NOT promote it to VERIFIED.
Promotion requires a verifier from a DIFFERENT trust/authority/failure domain.

If no independent verifier is configured, verification stays UNVERIFIED and the
IV&V status is BLOCKED — never fabricated.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from . import epistemics


class IVVError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True)
class VerificationResult:
    verification_status: str
    truth_status: str
    verifier_id: str
    method: str
    reason: str
    digest: str


class IndependentVerifier(Protocol):
    verifier_id: str
    authority_domain: str   # must differ from producer authority domain
    failure_domain: str     # must differ from producer failure domain

    def verify(self, *, claim: str, evidence: dict[str, Any], producer_id: str) -> VerificationResult: ...


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def assert_independent(*, producer_id: str, producer_authority_domain: str, producer_failure_domain: str, verifier: IndependentVerifier) -> None:
    """Independence is more than a different class name (mandate §15)."""
    if verifier.verifier_id == producer_id:
        raise IVVError("PRODUCER_EQUALS_VERIFIER")
    if verifier.authority_domain == producer_authority_domain:
        raise IVVError("VERIFIER_SHARES_AUTHORITY_DOMAIN")
    if verifier.failure_domain == producer_failure_domain:
        raise IVVError("VERIFIER_SHARES_FAILURE_DOMAIN")


def verify_evidence(
    *,
    claim: str,
    evidence: dict[str, Any],
    producer_id: str,
    producer_authority_domain: str,
    producer_failure_domain: str,
    verifier: IndependentVerifier | None,
) -> VerificationResult:
    """UNVERIFIED -> INDEPENDENT EVALUATION -> VERIFICATION RESULT (never self-mark)."""
    if verifier is None:
        return VerificationResult(
            verification_status=epistemics.VerificationStatus.UNVERIFIED.value,
            truth_status=epistemics.TruthStatus.UNVERIFIED.value,
            verifier_id="", method="none", reason="NO_INDEPENDENT_VERIFIER",
            digest=_digest({"claim": claim, "evidence": evidence}),
        )
    try:
        assert_independent(
            producer_id=producer_id, producer_authority_domain=producer_authority_domain,
            producer_failure_domain=producer_failure_domain, verifier=verifier,
        )
    except IVVError as exc:
        return VerificationResult(
            verification_status=epistemics.VerificationStatus.VERIFICATION_FAILED.value,
            truth_status=epistemics.TruthStatus.UNVERIFIED.value,
            verifier_id=getattr(verifier, "verifier_id", ""), method="independence_check",
            reason=exc.code, digest=_digest({"claim": claim}),
        )
    return verifier.verify(claim=claim, evidence=evidence, producer_id=producer_id)


def promotion_gate(result: VerificationResult) -> dict[str, Any]:
    """Assurance admission. Only INDEPENDENTLY_VERIFIED admits promotion to VERIFIED."""
    admitted = result.verification_status == epistemics.VerificationStatus.INDEPENDENTLY_VERIFIED.value
    return {
        "promotable": admitted,
        "truth_status": epistemics.TruthStatus.VERIFIED.value if admitted else epistemics.TruthStatus.UNVERIFIED.value,
        "verification_status": result.verification_status,
    }
