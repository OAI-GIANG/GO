# MASTER GOVERNANCE RULESET V1 — Default-Branch Integration Report

Date: 2026-10-10
Repository: `OAI-GIANG/GO`
Default branch: `hg-core`
Integration PR: [#9](https://github.com/OAI-GIANG/GO/pull/9)
Merge commit: `6a700ede39d2118fb2e5289ce1f0f49070877a17`
Integration branch: `feature/master-governance-v1-integration-20261010`

## Objective and method
The earlier cutover commit `7f46b1a` removes a broad set of LOVE/PARADISE implementation files. It was not cherry-picked wholesale into the current GO runtime branch because that would combine governance integration with broad implementation deletion. A clean worktree was created from `origin/hg-core`, and the V1 policy was ported selectively with GO runtime ownership preserved.

## Canonical source integrity
- Canonical path: `control/MASTER_GOVERNANCE_RULESET_V1.md`
- Required SHA-256: `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`
- After merge, both the default-branch worktree bytes and Git HEAD blob were hashed and matched the required SHA-256.
- `.gitattributes` marks the canonical source `-text` so `core.autocrlf` cannot rewrite its bytes on Windows checkout.
- Approval binding is retained at `control/MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json`. The source's internal draft-status text remains unchanged; the binding discloses the owner's later direction and metadata discrepancy rather than rewriting source bytes.

## Runtime integration merged into `hg-core`
1. Added `runtime/go_runtime/core/governance_source.py` to fail closed if the canonical source, source hash, required G1 heading/order, or approval binding is invalid.
2. GO startup verifies the source before creating runtime storage.
3. GO task submission, direct execution entry points, tool execution, objective routing, VPS2 execution, and HTTP POST handling re-verify the source before side effects. `/healthz` returns 503 when verification fails and reports the verified source hash when it succeeds.
4. OpenAI-compatible model requests receive the exact V1 source in the `system` message; user/task/memory content remains in the `user` message. The source is re-verified at each model invocation.
5. Execution evidence integrity includes the governance source SHA-256. The kernel carries that binding through evidence admission/promotion while preserving compatibility for older `Evidence` instances without a governance hash.
6. Tool-governance event ledger records and returned witnesses include `governance_source_sha256`.
7. `control/GO_RUNTIME_AUTHORITY_V1.md` was reconciled: it defines runtime ownership/identity only and explicitly subordinates itself to V1; evidence requirements include the policy hash.
8. No legacy implementation tree was deleted by this integration. Historical branches and Git history were not rewritten.

## Post-merge verification
- Pre-change baseline: `95 passed`.
- Integration branch test suite: `105 passed`.
- Fresh worktree from merged `hg-core` commit `6a700ed`: `105 passed`.
- `python -m compileall -q runtime`: PASS on the merged default branch.
- Local runtime smoke test on merged default: `governance_status=VERIFIED`, policy SHA-256 matched, test `echo` task state `COMPLETED`, and persisted execution evidence carried the same `governance_source_sha256`.
- New tests cover canonical source verification, tamper rejection, binding mismatch, startup and task-submit fail-closed, tool fail-closed before adapter/ledger side effects, exact V1 model system-message binding, evidence integrity/source-hash binding, tool event/witness binding, and authority-contract reconciliation.

## Remote branch audit
- Audited all 12 GitHub remote branch heads. See `MASTER_GOVERNANCE_RULESET_V1_REMOTE_BRANCH_AUDIT_20261010.md`.
- V1 source is present with the required hash on `hg-core`, the merged integration branch, and the earlier cutover branch. The other remote branches do not contain the canonical V1 source.
- No legacy policy identifier references were found in scanned active Python/shell/YAML/TOML code across remote heads.
- `hg-core-distilled` still contains 10 legacy governance/design paths and 29 legacy implementation paths. Its deployment/maintenance status is unproven; no cleanup was performed there.
- PR #8 (`HG-V2-REMEDIATION`) remains open and GitHub now reports it `CONFLICTING` after the V1 merge. It overlaps four runtime files: `runtime/go_kernel.py`, `runtime/go_runtime/core/cognitive.py`, `runtime/go_runtime/core/server.py`, and `runtime/go_runtime/core/tool_governance.py`. This integration did not modify or merge PR #8; its V2/P0 changes must be reconciled without losing them.

## Limits / not claimed
- VPS/phone production runtime commit and loaded policy hash remain `UNVERIFIED`.
- The V1 hash check proves source identity, not independent semantic enforcement of every principle. Runtime enforcement coverage still requires dedicated per-rule and adversarial evidence.
- No remote branch was deleted, no force-push/history rewrite was performed, and no production runtime was changed.

## State
DEFAULT_BRANCH_INTEGRATION: MERGED
DEFAULT_BRANCH_SOURCE_HASH: VERIFIED
DEFAULT_BRANCH_FULL_TEST_SUITE: 105_PASS
LOCAL_RUNTIME_SMOKE: VERIFIED
REMOTE_BRANCH_HEAD_INVENTORY: 12
PR8_CONFLICT_RECONCILIATION: BLOCKED_CONFLICTING
EXTERNAL_RUNTIME_ADOPTION: UNVERIFIED
HISTORY_PURGE: NOT_PERFORMED
SYSTEM_WIDE_COMPLETION: NOT_CLAIMED
