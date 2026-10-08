from __future__ import annotations

from runtime.go_kernel import Evidence, GateResult, Kernel
from runtime.go_runtime.core import ivv


class TrustedVerifier:
    verifier_id = "evidence-verifier-1"
    authority_domain = "ivv-external"
    failure_domain = "ivv-isolated"

    def verify(self, *, claim, evidence, producer_id):
        d = ivv._digest({"claim": claim, "evidence": evidence})
        return ivv._issue_result(
            verification_status="INDEPENDENTLY_VERIFIED",
            truth_status="VERIFIED",
            verifier_id=self.verifier_id,
            method="external-attestation",
            reason="PASS",
            evidence_digest=d,
        )


def make_evidence():
    from datetime import datetime, timezone
    base = Evidence("P0C-E", "producer-A", "MODEL_EXECUTION", "runtime",
                    datetime.now(timezone.utc), "prov", "", "UNVERIFIED", "claim")
    return Evidence(base.evidence_id, base.subject, base.scope, base.source,
                    base.captured_at, base.provenance, base.expected_integrity(),
                    base.verification_status, base.claim)


# 1. Caller cannot construct a promotable result.
try:
    ivv.VerificationResult("INDEPENDENTLY_VERIFIED", "VERIFIED", "attacker",
                           "forged", "forged", "sha256:forged")
except ivv.IVVError as e:
    print("FORGED_CONSTRUCTOR=DENY", e.code)
else:
    raise AssertionError("caller constructor unexpectedly succeeded")

# 2. Caller cannot pass a raw verifier object.
raw = TrustedVerifier()
raw_result = ivv.verify_evidence(
    claim="claim", evidence={"claim": "claim"},
    producer_id="producer-A", producer_authority_domain="runtime",
    producer_failure_domain="runtime", verifier=raw)
print("RAW_VERIFIER=DENY", raw_result.reason)
assert raw_result.verification_status == "VERIFICATION_FAILED"

# 3. Bind an independently provisioned verifier fixture to the canonical registry.
spec = ivv.TrustedVerifierSpec(
    raw.verifier_id, raw.authority_domain, raw.failure_domain,
    f"{raw.__class__.__module__}:{raw.__class__.__qualname__}",
)
ivv.TRUSTED_VERIFIER_REGISTRY = (ivv.TrustedVerifierBinding(spec, raw),)
handle = ivv.get_trusted_verifier(raw.verifier_id)
assert handle is not None

# 4. Trusted path: verifier -> anchored result -> promotion.
evidence = make_evidence()
result = ivv.verify_evidence(
    claim=evidence.claim, evidence={"claim": evidence.claim},
    producer_id="producer-A", producer_authority_domain="runtime",
    producer_failure_domain="runtime", verifier=handle)
print("TRUSTED_RESULT=", result.verification_status, result.anchor_id, result.verifier_id)
gate = ivv.promotion_gate(result)
print("PROMOTION_GATE=", gate)
status, promoted = Kernel().verify_and_promote_evidence(
    evidence, "producer-A", "MODEL_EXECUTION", verification_result=result)
print("KERNEL_PROMOTION=", status.value, "PROMOTED=", promoted.verification_status if promoted else None)
assert status is GateResult.ALLOW
assert promoted is not None and promoted.verification_status == "VERIFIED"

# 5. Forge an object after creation; immutable anchor/registry binding must still deny.
forged = object.__new__(ivv.VerificationResult)
for field in ("verification_status", "truth_status", "verifier_id", "method", "reason", "digest", "evidence_digest", "anchor_id", "freshness_status", "corroboration_status", "assurance_status"):
    object.__setattr__(forged, field, getattr(result, field))
object.__setattr__(forged, "verifier_id", "attacker")
print("TAMPERED_PROMOTION=", ivv.promotion_gate(forged))
assert ivv.promotion_gate(forged)["promotable"] is False

# 6. Empty trusted registry remains fail-closed.
ivv.TRUSTED_VERIFIER_REGISTRY = ()
print("NO_TRUSTED_VERIFIER=", ivv.get_trusted_verifier())
assert ivv.get_trusted_verifier() is None
