"""HG V2 IV&V trust boundary — P0-C.

The promotion boundary is:
caller -> trusted verifier registry/handle -> anchored immutable
VerificationResult -> promotion gate.

Raw verifier objects and caller-constructed VerificationResult objects are not
trusted inputs. Existing authority.py/provenance.py remain semantic owners for
authority and provenance respectively.
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


_RESULT_SEAL = object()
_HANDLE_SEAL = object()
TRUST_ANCHOR_ID = "HG_IVV_TRUST_ANCHOR_V1"


class IndependentVerifier(Protocol):
    verifier_id: str
    authority_domain: str
    failure_domain: str

    def verify(self, *, claim: str, evidence: dict[str, Any], producer_id: str) -> "VerificationResult": ...


@dataclass(frozen=True)
class TrustedVerifierSpec:
    verifier_id: str
    authority_domain: str
    failure_domain: str
    implementation: str
    anchor_id: str = TRUST_ANCHOR_ID


@dataclass(frozen=True, init=False)
class TrustedVerifierHandle:
    verifier: IndependentVerifier
    spec: TrustedVerifierSpec

    def __init__(self, verifier: IndependentVerifier, spec: TrustedVerifierSpec, *, _seal: object | None = None) -> None:
        if _seal is not _HANDLE_SEAL:
            raise IVVError("TRUSTED_VERIFIER_HANDLE_CONSTRUCTION_FORBIDDEN")
        object.__setattr__(self, "verifier", verifier)
        object.__setattr__(self, "spec", spec)


@dataclass(frozen=True, init=False)
class VerificationResult:
    verification_status: str
    truth_status: str
    verifier_id: str
    method: str
    reason: str
    digest: str
    evidence_digest: str
    anchor_id: str
    freshness_status: str
    corroboration_status: str
    assurance_status: str

    def __init__(
        self,
        verification_status: str,
        truth_status: str,
        verifier_id: str,
        method: str,
        reason: str,
        digest: str,
        *,
        evidence_digest: str = "",
        anchor_id: str = "",
        freshness_status: str = "UNASSESSED",
        corroboration_status: str = "UNASSESSED",
        assurance_status: str = "UNASSESSED",
        _seal: object | None = None,
    ) -> None:
        if _seal is not _RESULT_SEAL:
            raise IVVError("VERIFICATION_RESULT_CONSTRUCTION_FORBIDDEN")
        object.__setattr__(self, "verification_status", verification_status)
        object.__setattr__(self, "truth_status", truth_status)
        object.__setattr__(self, "verifier_id", verifier_id)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "digest", digest)
        object.__setattr__(self, "evidence_digest", evidence_digest)
        object.__setattr__(self, "anchor_id", anchor_id)
        object.__setattr__(self, "freshness_status", freshness_status)
        object.__setattr__(self, "corroboration_status", corroboration_status)
        object.__setattr__(self, "assurance_status", assurance_status)


@dataclass(frozen=True)
class TrustedVerifierBinding:
    spec: TrustedVerifierSpec
    verifier: IndependentVerifier


# Canonical registry. Empty is secure and fail-closed until an independently
# provisioned verifier is actually registered by trusted bootstrap code.
TRUSTED_VERIFIER_REGISTRY: tuple[TrustedVerifierBinding, ...] = ()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _result_digest(
    *,
    verification_status: str,
    truth_status: str,
    verifier_id: str,
    method: str,
    reason: str,
    evidence_digest: str,
    freshness_status: str,
    corroboration_status: str,
    assurance_status: str,
) -> str:
    return _digest(
        {
            "anchor_id": TRUST_ANCHOR_ID,
            "verification_status": verification_status,
            "truth_status": truth_status,
            "verifier_id": verifier_id,
            "method": method,
            "reason": reason,
            "evidence_digest": evidence_digest,
            "freshness_status": freshness_status,
            "corroboration_status": corroboration_status,
            "assurance_status": assurance_status,
        }
    )


def _issue_result(
    *,
    verification_status: str,
    truth_status: str,
    verifier_id: str,
    method: str,
    reason: str,
    evidence_digest: str,
    freshness_status: str = "UNASSESSED",
    corroboration_status: str = "UNASSESSED",
    assurance_status: str = "UNASSESSED",
) -> VerificationResult:
    return VerificationResult(
        verification_status,
        truth_status,
        verifier_id,
        method,
        reason,
        _result_digest(
            verification_status=verification_status,
            truth_status=truth_status,
            verifier_id=verifier_id,
            method=method,
            reason=reason,
            evidence_digest=evidence_digest,
            freshness_status=freshness_status,
            corroboration_status=corroboration_status,
            assurance_status=assurance_status,
        ),
        evidence_digest=evidence_digest,
        anchor_id=TRUST_ANCHOR_ID,
        freshness_status=freshness_status,
        corroboration_status=corroboration_status,
        assurance_status=assurance_status,
        _seal=_RESULT_SEAL,
    )


def _issue_handle(verifier: IndependentVerifier, spec: TrustedVerifierSpec) -> TrustedVerifierHandle:
    """Trusted bootstrap seam. Not a public caller API."""
    return TrustedVerifierHandle(verifier, spec, _seal=_HANDLE_SEAL)


def get_trusted_verifier(verifier_id: str | None = None) -> TrustedVerifierHandle | None:
    for binding in TRUSTED_VERIFIER_REGISTRY:
        if binding.spec.anchor_id != TRUST_ANCHOR_ID:
            continue
        if verifier_id is None or binding.spec.verifier_id == verifier_id:
            return _issue_handle(binding.verifier, binding.spec)
    return None


def _validate_handle(handle: TrustedVerifierHandle | None) -> TrustedVerifierSpec:
    if not isinstance(handle, TrustedVerifierHandle):
        raise IVVError("TRUSTED_VERIFIER_HANDLE_REQUIRED")
    spec = handle.spec
    implementation = f"{handle.verifier.__class__.__module__}:{handle.verifier.__class__.__qualname__}"
    if spec.anchor_id != TRUST_ANCHOR_ID:
        raise IVVError("VERIFIER_TRUST_ANCHOR_MISMATCH")
    if spec.implementation != implementation:
        raise IVVError("VERIFIER_IMPLEMENTATION_MISMATCH")
    for binding in TRUSTED_VERIFIER_REGISTRY:
        if binding.spec == spec and binding.verifier is handle.verifier:
            return spec
    raise IVVError("VERIFIER_NOT_TRUST_ANCHORED")


def assert_independent(
    *,
    producer_id: str,
    producer_authority_domain: str,
    producer_failure_domain: str,
    verifier: TrustedVerifierHandle,
) -> TrustedVerifierSpec:
    spec = _validate_handle(verifier)
    obj = verifier.verifier
    if obj.verifier_id == producer_id:
        raise IVVError("PRODUCER_EQUALS_VERIFIER")
    if obj.authority_domain != spec.authority_domain:
        raise IVVError("VERIFIER_AUTHORITY_DOMAIN_MISMATCH")
    if obj.failure_domain != spec.failure_domain:
        raise IVVError("VERIFIER_FAILURE_DOMAIN_MISMATCH")
    if obj.authority_domain == producer_authority_domain:
        raise IVVError("VERIFIER_SHARES_AUTHORITY_DOMAIN")
    if obj.failure_domain == producer_failure_domain:
        raise IVVError("VERIFIER_SHARES_FAILURE_DOMAIN")
    return spec


def verify_evidence(
    *,
    claim: str,
    evidence: dict[str, Any],
    producer_id: str,
    producer_authority_domain: str,
    producer_failure_domain: str,
    verifier: TrustedVerifierHandle | None,
) -> VerificationResult:
    """Fail closed unless the verifier came from the canonical registry."""
    evidence_digest = _digest({"claim": claim, "evidence": evidence})
    if verifier is None:
        return _issue_result(
            verification_status=epistemics.VerificationStatus.UNVERIFIED.value,
            truth_status=epistemics.TruthStatus.UNVERIFIED.value,
            verifier_id="",
            method="none",
            reason="NO_INDEPENDENT_VERIFIER",
            evidence_digest=evidence_digest,
        )

    try:
        spec = assert_independent(
            producer_id=producer_id,
            producer_authority_domain=producer_authority_domain,
            producer_failure_domain=producer_failure_domain,
            verifier=verifier,
        )
    except IVVError as exc:
        return _issue_result(
            verification_status=epistemics.VerificationStatus.VERIFICATION_FAILED.value,
            truth_status=epistemics.TruthStatus.UNVERIFIED.value,
            verifier_id=getattr(getattr(verifier, "spec", None), "verifier_id", ""),
            method="trust_boundary_check",
            reason=exc.code,
            evidence_digest=evidence_digest,
        )

    result = verifier.verifier.verify(
        claim=claim, evidence=evidence, producer_id=producer_id
    )
    if not isinstance(result, VerificationResult):
        return _issue_result(
            verification_status=epistemics.VerificationStatus.VERIFICATION_FAILED.value,
            truth_status=epistemics.TruthStatus.UNVERIFIED.value,
            verifier_id=spec.verifier_id,
            method="result_type_check",
            reason="UNTRUSTED_RESULT_TYPE",
            evidence_digest=evidence_digest,
        )

    expected = _result_digest(
        verification_status=result.verification_status,
        truth_status=result.truth_status,
        verifier_id=result.verifier_id,
        method=result.method,
        reason=result.reason,
        evidence_digest=evidence_digest,
        freshness_status=result.freshness_status,
        corroboration_status=result.corroboration_status,
        assurance_status=result.assurance_status,
    )
    if (
        result.anchor_id != TRUST_ANCHOR_ID
        or result.verifier_id != spec.verifier_id
        or result.evidence_digest != evidence_digest
        or result.digest != expected
    ):
        return _issue_result(
            verification_status=epistemics.VerificationStatus.VERIFICATION_FAILED.value,
            truth_status=epistemics.TruthStatus.UNVERIFIED.value,
            verifier_id=spec.verifier_id,
            method="result_binding_check",
            reason="VERIFICATION_RESULT_BINDING_INVALID",
            evidence_digest=evidence_digest,
        )
    return result


def promotion_gate(result: VerificationResult) -> dict[str, Any]:
    """Only registry-bound, anchor-bound, internally consistent results promote."""
    if not isinstance(result, VerificationResult):
        return {"promotable": False, "truth_status": "UNVERIFIED", "verification_status": "UNVERIFIED"}

    binding = next(
        (
            b for b in TRUSTED_VERIFIER_REGISTRY
            if b.spec.verifier_id == result.verifier_id
            and b.spec.anchor_id == result.anchor_id
        ),
        None,
    )
    if binding is None:
        return {
            "promotable": False,
            "truth_status": epistemics.TruthStatus.UNVERIFIED.value,
            "verification_status": result.verification_status,
        }

    expected_digest = _result_digest(
        verification_status=result.verification_status,
        truth_status=result.truth_status,
        verifier_id=result.verifier_id,
        method=result.method,
        reason=result.reason,
        evidence_digest=result.evidence_digest,
        freshness_status=result.freshness_status,
        corroboration_status=result.corroboration_status,
        assurance_status=result.assurance_status,
    )
    if result.digest != expected_digest:
        return {
            "promotable": False,
            "truth_status": epistemics.TruthStatus.UNVERIFIED.value,
            "verification_status": result.verification_status,
            "reason": "VERIFICATION_RESULT_DIGEST_INVALID",
        }

    admitted = result.verification_status == epistemics.VerificationStatus.INDEPENDENTLY_VERIFIED.value
    truth = result.truth_status == epistemics.TruthStatus.VERIFIED.value
    fresh = result.freshness_status == "CURRENT"
    corroborated = result.corroboration_status == "CORROBORATED"
    assured = result.assurance_status == "ASSESSED"
    return {
        "promotable": admitted and truth and fresh and corroborated and assured,
        "truth_status": epistemics.TruthStatus.VERIFIED.value if admitted and truth and fresh and corroborated and assured else epistemics.TruthStatus.UNVERIFIED.value,
        "verification_status": result.verification_status,
        "freshness_status": result.freshness_status,
        "corroboration_status": result.corroboration_status,
        "assurance_status": result.assurance_status,
    }
