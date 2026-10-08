# HG V2 P0-D Gate Evidence

## Scope
P0-D: certification firewall must consume evidence-backed inputs rather than caller-supplied certification booleans/status.

## Baseline
P0-C enforced commit: cd3fd9e7f46973f030212520ca7bac70989a1d00

## Forensic finding
Previous certification_firewall.required_checks() accepted raw caller-controlled booleans and ivv_status. No runtime caller wired those values from canonical evidence. That path was therefore insufficient for certification truth.

## Duplicate/collision audit
Reused existing:
- runtime/go_runtime/core/evidence.py — canonical evidence semantic owner
- runtime/go_runtime/core/assurance.py — assurance case semantic owner
- runtime/go_runtime/core/ivv.py — IVV trust owner

No new evidence/assurance/authority semantic owner was created.

## Remediation
Certification firewall now exposes evaluate_evidence_backed() and consumes CanonicalEvidence only.

Every required criterion must have exactly one canonical evidence record containing:
- observation.firewall_check
- observation.value
- INDEPENDENTLY_VERIFIED
- truth_status=VERIFIED
- provenance
- verifier

Missing, duplicate, false, self-observed, or invalid evidence fails closed.

Legacy raw-boolean required_checks API removed.

## Execution evidence
- Evidence-backed complete set: CERTIFICATION_READY, 20 references.
- One false verified criterion: CERTIFICATION_BLOCKED.
- One SELF_OBSERVED criterion: CERTIFICATION_BLOCKED.
- One missing criterion: CERTIFICATION_BLOCKED.

Reproduction stdout:
evidence/HG_V2_P0D_REPRO_STDOUT.txt
SHA-256: 838D56B66FDF02C81A5E0594633E4B6F4D490B4FE5D4A3799E3FE866B4FC8CC7

Firewall artifact:
runtime/go_runtime/core/certification_firewall.py
SHA-256: 756E5AED0F48BBC44E18FBE3FEBB2B42328DA814F01AEB9198731B8D78C311FE

## Tests
- Targeted remediation/threat tests: 30 passed
- Full regression: 154 passed in 6.85s
- git diff --check with CRLF-aware whitespace: PASS

## Gate decision
P0-D = ENFORCED / CLOSED.

This gate does not certify HG V2 globally. Certification still depends on later gates and genuinely verified evidence.
