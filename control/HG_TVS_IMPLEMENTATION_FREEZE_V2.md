# HG TVS Implementation Freeze V2

Status: FROZEN / NOT IMPLEMENTED
Canonical baseline: 4346afdb775e68e7f1499896920a894b8a6e6878
Canonical branch: hg-core
hg-core MUST remain untouched.

## 1. Selected authority model
SELECTED: signed OpenPGP annotated Git tag + externally pinned TVS root key.

Rejected:
- V1 self-contained manifest inside the verified tree.
- mutable branch/tag or runtime self-report as trust anchor.
- local unsigned deployment manifest as sole authority.

Reason: no self-reference cycle, cryptographic source authentication, immutable commit/tree identity, runtime remains verifier, no second source repository required.

## 2. External trust-root requirement
TVS root public key/fingerprint is provisioned outside GO.
No private signing key may enter repository, runtime data, environment evidence, tests, or evidence artifacts.
Production trust-root material is NOT created by this freeze.

## 3. Implementation file scope
CREATE:
1. control/HG_TRUSTED_VERSION_SOURCE_CONTRACT_V2.md
2. runtime/go_runtime/core/trusted_version_source.py
3. tests/test_trusted_version_source.py
4. tests/test_trusted_version_source_adversarial.py
5. tests/test_trusted_version_source_runtime_binding.py
6. evidence/HG_TVS_VERIFICATION_EVIDENCE.json

MODIFY:
7. runtime/go_runtime/core/server.py

EXTERNAL / OUTSIDE REPOSITORY:
8. TVS root public key/fingerprint
9. Signed TVS annotated tag

The signed production tag is a separate release action and is NOT authorized by this freeze.

## 4. No-touch
runtime/go_kernel.py
runtime/go_runtime/core/vps2_execution_bridge.py
control/GO_RUNTIME_AUTHORITY_V1.md
control/GO_RUNTIME_DEPLOYMENT_V1.md
contracts/VPS2_EXECUTION_BRIDGE_CONTRACT_V3.md
contracts/VPS2_EXECUTION_BRIDGE_CONTRACT_V3_PROVENANCE.json
contracts/HG_V3_E2E_CLOSURE_EVIDENCE.json
existing V3 evidence/provenance artifacts

## 5. Required tests
T0 unit/schema/canonicalization
T1 signed-tag positive verification
T2 AC-TVS-01..12 adversarial closure
T3 runtime binding
T4 existing GO regression
T5 existing VPS2 V3 regression
T6 full evidence closure

Negative controls: unsigned tag, lightweight tag, wrong signer, invalid signature, tag target mismatch, commit mismatch, tree mismatch, runtime version mismatch, TVS_ID mismatch, repository mismatch, missing root, forged runtime attestation.

## 6. Acceptance gates
AG-01 contract consistent
AG-02 no self-referential anchor
AG-03 signed annotated tag verifies
AG-04 signer matches pinned root
AG-05 exact commit/tree match
AG-06 TVS_ID recomputation
AG-07 runtime binding
AG-08 AC-TVS-01..12
AG-09 GO regression
AG-10 VPS2 V3 regression
AG-11 no authority collision
AG-12 evidence integrity/provenance
AG-13 no unauthorized files
AG-14 no secrets/private keys
AG-15 no production deployment
AG-16 merge remains blocked until explicit authorization

## 7. Release boundary
Implementation only on a feature branch based on 4346afd.
No rewrite, force-push, merge, or production deployment.

## 8. Rollback
Any failed gate: stop, preserve evidence, do not merge, do not rewrite canonical history, return to last verified canonical baseline.

## 9. Freeze statement
V1 self-referential manifest model is CLOSED and REJECTED.
V2 signed-tag authority is the selected implementation model.
Implementation status: NOT STARTED.


