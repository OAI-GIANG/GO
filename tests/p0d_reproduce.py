from runtime.go_runtime.core import evidence, certification_firewall


def ev(check, value=True, status="INDEPENDENTLY_VERIFIED"):
    return evidence.CanonicalEvidence(
        evidence_id="p0d-" + check,
        subject="certification",
        producer="independent-certifier",
        claim="criterion " + check,
        observation={"firewall_check": check, "value": value},
        integrity="sha256:fixture",
        provenance={"source": "independent"},
        verification_status=status,
        truth_status="VERIFIED" if status == "INDEPENDENTLY_VERIFIED" else "UNVERIFIED",
        assurance_status="ASSESSED",
        verifier="verifier-B",
        captured_at="2026-10-08T00:00:00+00:00",
    )


all_items = [ev(name) for name in certification_firewall.REQUIRED_CHECKS]
ready = certification_firewall.evaluate_evidence_backed(all_items)
print("EVIDENCE_BACKED_READY=", ready["result"], "REFS=", len(ready["evidence_refs"]))
assert ready["result"] == "CERTIFICATION_READY"

tampered = list(all_items)
tampered[0] = ev(certification_firewall.REQUIRED_CHECKS[0], False)
blocked = certification_firewall.evaluate_evidence_backed(tampered)
print("FALSE_EVIDENCE=", blocked["result"], "FAILED=", certification_firewall.REQUIRED_CHECKS[0] in blocked["failed"])
assert blocked["result"] == "CERTIFICATION_BLOCKED"

self_observed = list(all_items)
self_observed[0] = ev(certification_firewall.REQUIRED_CHECKS[0], True, "SELF_OBSERVED")
blocked2 = certification_firewall.evaluate_evidence_backed(self_observed)
print("SELF_OBSERVED=", blocked2["result"], "FAILED=", certification_firewall.REQUIRED_CHECKS[0] in blocked2["failed"])
assert blocked2["result"] == "CERTIFICATION_BLOCKED"

missing = certification_firewall.evaluate_evidence_backed(all_items[:-1])
print("MISSING_EVIDENCE=", missing["result"], "FAILED=", "assurance_case_complete" in missing["failed"])
assert missing["result"] == "CERTIFICATION_BLOCKED"
