from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runtime.go_kernel import Evidence, GateResult, Kernel
from runtime.go_runtime.core import ivv


def make_evidence() -> Evidence:
    captured = datetime.now(timezone.utc)
    base = Evidence(
        "ev-p0b",
        "producer-A",
        "MODEL_EXECUTION",
        "runtime",
        captured,
        "producer-proof",
        "",
        "UNVERIFIED",
        "claim",
    )
    return Evidence(
        base.evidence_id,
        base.subject,
        base.scope,
        base.source,
        base.captured_at,
        base.provenance,
        base.expected_integrity(),
        base.verification_status,
        base.claim,
    )


class TrustedVerifier:
    verifier_id = "verifier-B"
    authority_domain = "ivv-external"
    failure_domain = "isolated-verifier"

    def verify(self, *, claim, evidence, producer_id):
        evidence_digest = ivv._digest({"claim": claim, "evidence": evidence})
        return ivv._issue_result(
            verification_status="INDEPENDENTLY_VERIFIED",
            truth_status="VERIFIED",
            verifier_id=self.verifier_id,
            method="trusted-test-verifier",
            reason="trusted-positive",
            evidence_digest=evidence_digest,
        )


@pytest.fixture
def trusted_handle(monkeypatch):
    verifier = TrustedVerifier()
    spec = ivv.TrustedVerifierSpec(
        verifier.verifier_id,
        verifier.authority_domain,
        verifier.failure_domain,
        f"{verifier.__class__.__module__}:{verifier.__class__.__qualname__}",
    )
    monkeypatch.setattr(
        ivv,
        "TRUSTED_VERIFIER_REGISTRY",
        (ivv.TrustedVerifierBinding(spec, verifier),),
    )
    return ivv.get_trusted_verifier(verifier.verifier_id)


def test_caller_controlled_promotion_is_denied():
    kernel = Kernel()
    evidence = make_evidence()
    with pytest.raises(TypeError):
        kernel.verify_and_promote_evidence(
            evidence,
            "producer-A",
            "MODEL_EXECUTION",
            independent_verification="INDEPENDENTLY_VERIFIED",
        )


def test_forged_verification_result_is_denied():
    kernel = Kernel()
    evidence = make_evidence()
    forged = {"verification_status": "INDEPENDENTLY_VERIFIED"}
    status, promoted = kernel.verify_and_promote_evidence(
        evidence, "producer-A", "MODEL_EXECUTION", verification_result=forged
    )
    assert status is GateResult.BLOCKED
    assert promoted is None


def test_missing_or_untrusted_verification_is_denied():
    kernel = Kernel()
    evidence = make_evidence()
    with pytest.raises(ivv.IVVError, match="VERIFICATION_RESULT_CONSTRUCTION_FORBIDDEN"):
        ivv.VerificationResult(
            "UNVERIFIED", "UNVERIFIED", "", "none", "NO_INDEPENDENT_VERIFIER", "sha256:none"
        )


def test_same_producer_verifier_is_denied(trusted_handle):
    result = ivv.verify_evidence(
        claim="claim",
        evidence={"claim": "claim"},
        producer_id="verifier-B",
        producer_authority_domain="runtime",
        producer_failure_domain="runtime",
        verifier=trusted_handle,
    )
    assert result.verification_status == "VERIFICATION_FAILED"
    assert result.reason == "PRODUCER_EQUALS_VERIFIER"


def test_trusted_verification_result_allows_promotion(trusted_handle):
    kernel = Kernel()
    evidence = make_evidence()
    result = ivv.verify_evidence(
        claim=evidence.claim,
        evidence={"claim": evidence.claim},
        producer_id="producer-A",
        producer_authority_domain="runtime",
        producer_failure_domain="runtime",
        verifier=trusted_handle,
    )
    status, promoted = kernel.verify_and_promote_evidence(
        evidence, "producer-A", "MODEL_EXECUTION", verification_result=result
    )
    assert status is GateResult.ALLOW
    assert promoted is not None
    assert promoted.verification_status == "VERIFIED"
