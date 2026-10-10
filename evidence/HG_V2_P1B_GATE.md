# HG V2 P1-B Gate Evidence

## Scope
Wire freshness, corroboration, and assurance into the actual evidence promotion gate.

## Forensic finding
The prior assurance/freshness/corroboration modules existed but were not admission conditions in IVV promotion. A result could be independently verified yet lack current/fresh evidence, corroboration, or assurance.

## Remediation
VerificationResult now carries:
- freshness_status
- corroboration_status
- assurance_status
- evidence_digest

The result digest cryptographically binds these fields to the evidence digest and verifier identity.

promotion_gate now requires:
- INDEPENDENTLY_VERIFIED
- truth_status=VERIFIED
- freshness_status=CURRENT
- corroboration_status=CORROBORATED
- assurance_status=ASSESSED
- registry/anchor binding
- valid result digest

A tampered status invalidates the result digest and is denied.

## Research
HG's separation is aligned with the existing assurance/freshness/corroboration contracts and the evidence-first/provenance principles used in the external references already reviewed for HG V2.

## Execution
GOOD_GATE = promotable True
STALE = promotable False
NO_CORROBORATION = promotable False
NO_ASSURANCE = promotable False
TAMPERED = promotable False / VERIFICATION_RESULT_DIGEST_INVALID

Reproduction SHA-256:
CFEF3D3070E11580C24F9DA79E994A494A30C393C2537BB3571D006AA6BC2D57

IVV artifact SHA-256:
5E7BFAD70F1A9CEB52C089DCD56097728CD086CCC0CB7753441453703303279D

## Tests
- P1-B + prior security suites: 43 passed
- Full regression: 165 passed in 7.28s
- diff check: PASS with CRLF-aware whitespace

## Gate decision
P1-B = ENFORCED / CLOSED.
