from __future__ import annotations

from runtime.go_kernel import Evidence, GateResult, Kernel
from runtime.go_runtime.core import ivv


class V:
    verifier_id = "verifier-p1b"
    authority_domain = "external"
    failure_domain = "isolated"

    def __init__(self, freshness="CURRENT", corroboration="CORROBORATED", assurance="ASSESSED"):
        self.freshness = freshness
        self.corroboration = corroboration
        self.assurance = assurance

    def verify(self, *, claim, evidence, producer_id):
        d = ivv._digest({"claim": claim, "evidence": evidence})
        return ivv._issue_result(
            verification_status="INDEPENDENTLY_VERIFIED",
            truth_status="VERIFIED",
            verifier_id=self.verifier_id,
            method="p1b-fixture",
            reason="PASS",
            evidence_digest=d,
            freshness_status=self.freshness,
            corroboration_status=self.corroboration,
            assurance_status=self.assurance,
        )


def handle(monkeypatch, verifier):
    spec = ivv.TrustedVerifierSpec(
        verifier.verifier_id,
        verifier.authority_domain,
        verifier.failure_domain,
        f"{verifier.__class__.__module__}:{verifier.__class__.__qualname__}",
    )
    monkeypatch.setattr(ivv, "TRUSTED_VERIFIER_REGISTRY", (ivv.TrustedVerifierBinding(spec, verifier),))
    return ivv.get_trusted_verifier(verifier.verifier_id)


def test_all_three_admission_dimensions_are_enforced(monkeypatch):
    h = handle(monkeypatch, V())
    result = ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )
    assert ivv.promotion_gate(result)["promotable"] is True


def test_stale_freshness_blocks_promotion(monkeypatch):
    h = handle(monkeypatch, V(freshness="STALE"))
    result = ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )
    assert ivv.promotion_gate(result)["promotable"] is False


def test_missing_corroboration_blocks_promotion(monkeypatch):
    h = handle(monkeypatch, V(corroboration="NOT_CORROBORATED"))
    result = ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )
    assert ivv.promotion_gate(result)["promotable"] is False


def test_unassessed_assurance_blocks_promotion(monkeypatch):
    h = handle(monkeypatch, V(assurance="BLOCKED"))
    result = ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )
    assert ivv.promotion_gate(result)["promotable"] is False


def test_result_status_tampering_invalidates_digest(monkeypatch):
    h = handle(monkeypatch, V())
    result = ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )
    forged = object.__new__(ivv.VerificationResult)
    for field in ("verification_status", "truth_status", "verifier_id", "method", "reason",
                  "digest", "evidence_digest", "anchor_id", "freshness_status",
                  "corroboration_status", "assurance_status"):
        object.__setattr__(forged, field, getattr(result, field))
    object.__setattr__(forged, "freshness_status", "STALE")
    assert ivv.promotion_gate(forged)["promotable"] is False
    assert ivv.promotion_gate(forged).get("reason") == "VERIFICATION_RESULT_DIGEST_INVALID"


def test_kernel_cannot_promote_without_all_admission_dimensions(monkeypatch):
    h = handle(monkeypatch, V())
    result = ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )
    assert result.freshness_status == "CURRENT"
    assert result.corroboration_status == "CORROBORATED"
    assert result.assurance_status == "ASSESSED"
