# HG V2 P1-A Gate Evidence

## Scope
Wire the canonical evidence.unify() semantic owner through kernel, store, audit-event ledger, and checkpoint.

## Research
W3C PROV recommends translating heterogeneous domain-specific provenance into a common core model so provenance can be integrated and trust judgments made consistently.

## Duplicate/collision audit
Existing canonical owner retained: runtime/go_runtime/core/evidence.py.
No second evidence model was created.
Existing audit_events table is treated as the ledger adapter.
Checkpoint EvidenceReference remains the checkpoint representation and is projected through the canonical evidence adapter.

## Remediation
- evidence.from_ledger_event() added.
- evidence.unify() now reports duplicate representations and digest conflicts.
- Kernel.unify_evidence() uses canonical adapters + unify().
- RuntimeStore.unified_evidence() uses canonical adapters + unify().
- RuntimeStore.unified_audit_evidence() uses the ledger adapter + unify().
- checkpoint.unify_evidence_refs() uses the canonical checkpoint adapter + unify().
- Checkpoint.validated() now invokes unify and fails closed on duplicate/conflicting evidence references.

## Execution
KERNEL_UNIFY= 1 {'E1': 2}
STORE_UNIFY= 1
LEDGER_UNIFY= 1
CHECKPOINT_UNIFY= 1 {'E1': 2} True
CANONICAL_UNIFY= 1 {'E1': 2} True

Reproduction SHA-256:
9C3C261B6E0CFEBFBDB0AC7A0EE4FC9FC2D88267ADDB9FECE991B310EA06B524

## Tests
- P1-A targeted + P0-C regression: 16 passed
- Full regression: 159 passed in 7.44s
- diff check: PASS with CRLF-aware whitespace

## Artifact hashes
evidence.py: 212E2A51B998857789018DE5C2A618CE165B101DC633BA648A62FEDDCB5414D4
store.py: 6E23B6E3DB3D3A14CAA83DA1A4424DD3F93D68F36327564D43A9DEA680D8F53A
checkpoint.py: B7150BA01A87839361C961DDE61774D66EAD805FAD13E93D5E080A9D99274C40
go_kernel.py: 2451D086DE6F6FB26EA08209DF802B8F3DC6359029D24A8D836C1383AFF9E309

## Gate decision
P1-A = ENFORCED / CLOSED.
