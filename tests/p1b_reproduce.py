from runtime.go_kernel import GateResult, Kernel
from runtime.go_runtime.core import ivv


class V:
    verifier_id = "p1b-repro-verifier"
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
            method="p1b-repro",
            reason="PASS",
            evidence_digest=d,
            freshness_status=self.freshness,
            corroboration_status=self.corroboration,
            assurance_status=self.assurance,
        )


def install(v):
    spec = ivv.TrustedVerifierSpec(v.verifier_id, v.authority_domain, v.failure_domain,
                                   f"{v.__class__.__module__}:{v.__class__.__qualname__}")
    ivv.TRUSTED_VERIFIER_REGISTRY = (ivv.TrustedVerifierBinding(spec, v),)
    return ivv.get_trusted_verifier(v.verifier_id)


def run(v):
    h = install(v)
    return ivv.verify_evidence(
        claim="claim", evidence={"claim": "claim"},
        producer_id="producer", producer_authority_domain="runtime",
        producer_failure_domain="runtime", verifier=h,
    )


good = run(V())
print("GOOD_GATE=", ivv.promotion_gate(good))
assert ivv.promotion_gate(good)["promotable"] is True

for label, v in [
    ("STALE", V(freshness="STALE")),
    ("NO_CORROBORATION", V(corroboration="NOT_CORROBORATED")),
    ("NO_ASSURANCE", V(assurance="BLOCKED")),
]:
    result = run(v)
    print(label, "=", ivv.promotion_gate(result))
    assert ivv.promotion_gate(result)["promotable"] is False

forged = object.__new__(ivv.VerificationResult)
for field in ("verification_status", "truth_status", "verifier_id", "method", "reason",
              "digest", "evidence_digest", "anchor_id", "freshness_status",
              "corroboration_status", "assurance_status"):
    object.__setattr__(forged, field, getattr(good, field))
object.__setattr__(forged, "freshness_status", "STALE")
print("TAMPERED=", ivv.promotion_gate(forged))
assert ivv.promotion_gate(forged)["reason"] == "VERIFICATION_RESULT_DIGEST_INVALID"
