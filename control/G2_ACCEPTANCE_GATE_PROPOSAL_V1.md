# G2_ACCEPTANCE_GATE_PROPOSAL_V1 (PROPOSED — NOT PAG-1.0)

**Status:** PROPOSED (new document). **This is NOT PAG-1.0 and does not claim to be it.**
PAG-1.0 was searched and is `NOT_FOUND_IN_SCANNED_SCOPE` (see
`evidence/G2/PAG1_PROVENANCE_SEARCH_REPORT` inside `evidence/G2/G2_RECONCILIATION_AND_PROVENANCE.md`).
This proposal exists only to give G2 an explicit, auditable gate while PAG-1.0 remains unresolved.
It carries **no authority** on its own; it requires Owner/authority approval to become canonical.

## Scope
Defines the acceptance gate for G2 (design finalization + controlled integration of the
`HG-V2-REMEDIATION` (PR #8) governance work with canonical `hg-core`).

## Gate conditions (all REQUIRED)
| ID | Condition | Oracle |
|---|---|---|
| G2-A | Semantic reconciliation of the 4 overlapping files recorded (`KEEP/REPLACE/COMBINE/REJECT`) | `evidence/G2/G2_RECONCILIATION_AND_PROVENANCE.md` §1 |
| G2-B | AuthorityRoot: no self-authorization path; external root required | tests `test_g2_*` + `authority.py` |
| G2-C | Evidence promotion requires a trusted `VerificationResult` | `test_g2_evidence_promotion_requires_verifier` |
| G2-D | Approval bound to identity/action/target/scope/fingerprint/policy-hash/expiry/nonce | `approval.py` + tests |
| G2-E | Policy V1 source + approval binding byte-identical to canonical | hash check (§Integrity) |
| G2-F | Replay owner Option A unchanged; schema/lifecycle/migration specified | `replay_contract.py` + tests |
| G2-G | Governance enforced at every side-effect entry point | `test_g2_server_entrypoints_guard_governance` |
| G2-H | Negative/concurrency/recovery tests defined and (subset) executed | `tests/test_g2_governance_conformance.py` |
| G2-I | External research register with URL/clause/date/mapping | this repo `evidence/G2/...` §2 |
| G2-J | Trusted verifier + trusted approval issuer provisioned by external authority | **BLOCKED (external)** |
| G2-K | Source→artifact→runtime→evidence provenance linked | `evidence/G2/...` §3 |
| G2-L | Independent audit by STT/auditor | **NOT RUN** |

## Explicitly NOT claimed
- This is not PAG-1.0; no approval signature is fabricated.
- G2 is **not** `G2_COMPLETE` while G2-J/G2-L are unmet.
- Merging into `hg-core`/deployment requires G2-A..L + review; not done here.

## Approval binding (for this proposal)
`issuing_authority: <OWNER REQUIRED>` · `version: V1` ·
`binding: owner identity + this file SHA-256 + scope=G2 + nonce + expiry`.
