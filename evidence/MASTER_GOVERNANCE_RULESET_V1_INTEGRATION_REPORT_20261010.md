# MASTER GOVERNANCE RULESET V1 — Default-Branch Integration Report

Date: 2026-10-10
Repository: `OAI-GIANG/GO`
Default branch at audit time: `hg-core`
Default branch base commit: `a4d453519ea8994650cb520606eb013ddca8896e`
Integration branch: `feature/master-governance-v1-integration-20261010`

## Objective and method
The earlier cutover commit `7f46b1a` removes a broad set of LOVE/PARADISE implementation files. It was not cherry-picked wholesale because doing so on the current GO runtime branch would combine governance integration with broad implementation deletion. A clean worktree was created from `origin/hg-core`, and the V1 policy was ported selectively with GO runtime ownership preserved.

## Canonical source integrity
- Canonical path: `control/MASTER_GOVERNANCE_RULESET_V1.md`
- Required SHA-256: `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`
- Source bytes were copied directly from the cutover Git object and checked against the required hash.
- `.gitattributes` marks the canonical source `-text` so `core.autocrlf` cannot rewrite its bytes on Windows checkout.
- Approval binding is retained at `control/MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json`. The source's internal draft-status text remains unchanged; the binding discloses the owner's later direction and the metadata discrepancy rather than rewriting source bytes.

## Runtime integration implemented on this branch
1. Added `runtime/go_runtime/core/governance_source.py` to fail closed if the canonical source, source hash, required G1 heading/order, or approval binding is invalid.
2. GO startup verifies the source before creating runtime storage.
3. GO task submission, direct execution entry points, tool execution, objective routing, VPS2 execution, and HTTP POST handling re-verify the source before side effects. `/healthz` returns 503 when verification fails and reports the verified source hash when it succeeds.
4. OpenAI-compatible model requests receive the exact V1 source in the `system` message; user/task/memory content remains in the `user` message. The source is re-verified at each model invocation.
5. Execution evidence integrity now includes the governance source SHA-256. The kernel carries that binding through evidence admission/promotion while preserving compatibility for older `Evidence` instances that have no governance hash.
6. Tool-governance event ledger records and returned witnesses include `governance_source_sha256`.
7. `control/GO_RUNTIME_AUTHORITY_V1.md` was reconciled: it defines runtime ownership/identity only and explicitly subordinates itself to V1; evidence requirements include the policy hash.
8. No legacy implementation tree was deleted in this integration branch. Historical branches and Git history were not rewritten.

## Verification results
- Baseline before integration: `95 passed`.
- After integration: `105 passed` across the complete repository test suite.
- `python -m compileall -q runtime`: PASS.
- New governance-specific tests cover canonical source verification, tampered source rejection, approval-binding hash mismatch, startup fail-closed, task submission fail-closed before task side effects, tool dispatch fail-closed before adapter/ledger side effects, model system-message binding, execution-evidence integrity binding, tool event/witness binding, and runtime-authority contract reconciliation.
- The source SHA-256 is asserted by the tests. After staging, both the worktree bytes and the Git index blob were independently hashed and matched the required SHA-256. `.gitattributes` reports `text: unset` for this path.

## Remote branch audit
- Audited all 11 GitHub branch heads returned by `git ls-remote` by fetching them into local-only `refs/remotes/audit/*` references.
- At audit time, V1 source was present only on `feature/master-governance-ruleset-v1-cutover-20261010`, with the required hash. The default branch `hg-core` and the other remote branches did not contain the canonical V1 source.
- No legacy policy identifier references were found in scanned active Python/shell/YAML/TOML code on the remote heads. `control/GO_RUNTIME_AUTHORITY_V1.md` appeared on multiple branches as a runtime ownership contract, not as a competing V1 ruleset.
- `hg-core-distilled` contains 10 legacy governance/design paths and 29 legacy implementation paths. Its deployment/maintenance status is not proven; those paths were not deleted.
- See `MASTER_GOVERNANCE_RULESET_V1_REMOTE_BRANCH_AUDIT_20261010.md` for the branch table and limits.

## Scope and stop conditions
- This is a source/runtime integration branch, not a deployment proof.
- VPS/phone production runtime commit and loaded policy hash remain UNVERIFIED.
- The V1 hash check proves source identity, not independent semantic enforcement of every principle. Runtime enforcement coverage still requires dedicated per-rule and adversarial evidence.
- No remote branch was deleted, no force-push/history rewrite was performed, and no production runtime was changed.
- The default branch has not yet been changed by this report. The integration branch must be committed, pushed, and reviewed through a Pull Request before default-branch integration can be claimed.

## State
LOCAL_INTEGRATION: IMPLEMENTED
FULL_TEST_SUITE: 105_PASS
CANONICAL_SOURCE_HASH: VERIFIED_LOCALLY
REMOTE_BRANCH_AUDIT: 11_HEADS
DEFAULT_BRANCH_MERGE: NOT_YET_APPLIED
EXTERNAL_RUNTIME_ADOPTION: UNVERIFIED
SYSTEM_WIDE_COMPLETION: NOT_CLAIMED
