# HG V2 P0-C Gate Evidence

## Scope
P0-C only: trusted verifier anchor/registry and caller-proof verification-result promotion.

Baseline: 830fee4efab216cb2dc443a7bbf24111878821bc

## Research
- NIST Trust Anchor: an authoritative entity for which trust is assumed; integrity/authenticity of the trust anchor is foundational.
- SLSA v1.2 verification: verification checks trusted identities against a preconfigured root of trust and verifies provenance/attestation against expectations.
- SLSA VSA: signature verification uses preconfigured roots of trust and the attestation subject must match the artifact.

## Repository duplicate/collision audit
- Existing authority owner: runtime/go_runtime/core/authority.py
- Existing provenance owner: runtime/go_runtime/core/provenance.py
- Existing canonical evidence owner: runtime/go_runtime/core/evidence.py
- Existing assurance owner: runtime/go_runtime/core/assurance.py
- No existing IVV trust-anchor/registry implementation was found before P0-C.
- P0-C adds only IVV trust-boundary primitives; it does not create a second authority/provenance/evidence owner.

## Control
caller
-> TrustedVerifierHandle from canonical registry
-> anchored immutable VerificationResult
-> promotion_gate
-> Kernel.verify_and_promote_evidence
-> persistence decision

## Negative execution evidence
- Direct VerificationResult construction: DENY / VERIFICATION_RESULT_CONSTRUCTION_FORBIDDEN
- Raw caller verifier object: DENY / TRUSTED_VERIFIER_HANDLE_REQUIRED
- Forged/tampered VerificationResult: promotion DENY
- Empty trusted registry: no trusted verifier / fail-closed
- Caller-injected server verifier field: ignored; server resolves verifier only through ivv.get_trusted_verifier()

## Positive execution evidence
- Registry-bound verifier produced INDEPENDENTLY_VERIFIED result.
- Result carried HG_IVV_TRUST_ANCHOR_V1.
- promotion_gate returned promotable=True.
- Kernel promotion returned ALLOW and promoted evidence status VERIFIED.

## Tests
- P0-C targeted tests: 11 passed
- Full regression: 152 passed in 6.69s

## Reproduction
evidence/HG_V2_P0C_REPRO_STDOUT.txt
SHA-256: 57C0B6CB9D63FCF275163850BD4EA5FAB90DB1ECB40A3A45800A553BE253B3C1

## Artifact hashes
runtime/go_runtime/core/ivv.py
SHA-256: 2079B763FA744F374DDF9E8E623C06C75E2F7A843514BAD15DB52906050F4491

runtime/go_runtime/core/server.py
SHA-256: 4B6A15730E3FF9A4EE1CEBB5B22AB3945AF2EE5437D308607CE161BBD828DC9F

runtime/go_kernel.py
SHA-256: B11EF0424C1122595CF3F482A5DF2BD271B8C6D315D0AFF558BE502EBA81E2BA

tests/test_hg_v2_p0c.py
SHA-256: EA8F3F0EED450A9249988FF5234AEF5A7FA06A335046812B7D0A12D702AEAF0B

## Gate decision
P0-C = ENFORCED / CLOSED for the caller-controlled verification-result promotion vulnerability.

This does not certify HG V2 as a whole. Production independent verification remains fail-closed until a genuinely provisioned verifier is registered.
