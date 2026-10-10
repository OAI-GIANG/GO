# G2_WORKSTREAM_REGISTER_PROPOSED_V1 (PROPOSED mapping — not a historical definition)

**Status:** PROPOSED. The mandate referenced `D-G2-01..11`, but no canonical definition of
`D-G2-01..11` exists in any scanned scope (repo history/branches/tags/PRs/issues/local tree/web).
This register maps the mandate's own workstreams to explicit rows so work can proceed.
**It is not presented as the historical D-G2 definition.**

| ID (proposed) | Objective | Location | Acceptance oracle | Owner | Status |
|---|---|---|---|---|---|
| G2-W1 | AuthorityRoot single-issuer, external root, revoke/scope | `runtime/go_runtime/core/authority.py` | no self-authority; `AUTHORITY_ROOT_NOT_*` | Deep | SOURCE-CONFIRMED |
| G2-W2 | Evidence create→verify→promote→immutable | `go_kernel.py`, `evidence.py`, `ivv.py` | promotion needs `VerificationResult` | Deep | SOURCE-CONFIRMED |
| G2-W3 | Policy V1 hash binding end-to-end | `governance_source.py`, server, cognitive, tool_governance | 503/deny on invalid; witness hash | Deep | SOURCE-CONFIRMED |
| G2-W4 | IV&V verification + promotion gate | `ivv.py`, `certification_firewall.py` | verifier required; failure⇒no promotion | **external (BLK-3)** | BLOCKED |
| G2-W5 | Approval binding | `approval.py` | string ≠ evidence; binding mismatch denies | Deep | SOURCE-CONFIRMED |
| G2-W6 | Replay owner Option A | `replay_contract.py`, `store.py` | chain/digest/sequence fail-closed | Deep | SOURCE-CONFIRMED |
| G2-W7 | Idempotency/fingerprint/concurrency | `engine/durable_execution.py`, `tool_governance.py` | collision/dup handled | Deep | SOURCE-CONFIRMED |
| G2-W8 | UNKNOWN + reconciliation/recovery | `reconciliation.py` | UNKNOWN not retried blindly | Deep | SOURCE-CONFIRMED |
| G2-W9 | `vps2_target_id` from request/env | `server.py` | `req.target_id or env` | Deep | SOURCE-CONFIRMED |
| G2-W10 | Governance bypass prevention | `server.py` entry points | every side-effect path guarded | Deep | SOURCE-CONFIRMED |
| G2-W11 | Provenance chain | repo + evidence | source→artifact→runtime→evidence | Deep | PARTIAL |

Closure condition: a row is CLOSED only when its oracle is executed on an identified revision
and evidence is stored. Rows with `external` owner cannot be closed by Deep.
