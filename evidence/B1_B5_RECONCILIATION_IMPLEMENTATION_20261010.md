# B1–B5 PR #8 / canonical reconciliation — implementation evidence

**Status:** IMPLEMENTED ON A NEW WORKING BRANCH; REGRESSION PASS; PRODUCTION CERTIFICATION BLOCKED.

## Scope and immutable inputs

- Canonical repository: `OAI-GIANG/GO`
- Canonical base: `hg-core` at `955d9a5e1a0b217f756c4f443354dc7b02ecc22a`
- PR #8 head reconciled locally: `cecfb72052f0041d79ec4c5146f59f76b621be70`
- Merge base: `a4d453519ea8994650cb520606eb013ddca8896e`
- Working branch: `feature/stt-b1-b5-reconciliation-20261010`
- Protected Policy V1 SHA-256: `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`
- Protected approval-binding SHA-256: `538c0b4054d17f4ff6aa6beb6eecfb3e37c09c1986aec236a458b14ad8e66b17`
- `git diff --exit-code HEAD -- control/MASTER_GOVERNANCE_RULESET_V1.md control/MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json`: exit code `0`.
- No bytes in either protected file were changed.

## Implemented changes

### B1 — Reconcile PR #8

- Merged PR #8 into the isolated working branch only; no merge into `hg-core`.
- Resolved textual conflicts while preserving the canonical governance-source guard in `server.py` and the Policy V1 binding.
- Kept the IV&V promotion boundary, but bound promotion to the exact evidence payload digest and matching evidence subject/scope. With no trusted verifier provisioned, evidence remains `UNVERIFIED`.
- Retained the VPS2 target-id correction separately from evidence-promotion changes.
- Imported PR P0/P1 modules and tests for local validation; historical evidence artifacts remain historical, not production certification.

### B2 — Replay, lifecycle, checkpoint, transaction, migration

- Added `runtime/go_runtime/core/replay_contract.py`: versioned canonical Replay serialization, digest validation, chain/sequence validation, and bounded legacy-digest verification.
- `CognitiveService` and `DurableExecution` now delegate Replay append/verification to the shared store contract.
- `RuntimeStore.append_replay` uses a serialized SQLite write transaction and strict `INSERT`, rather than `INSERT OR REPLACE`; sequence races and tampered records fail closed.
- Checkpoint plus Replay are written in one transaction. Task identity, sequence, digest, and existing chain are checked before insertion; mismatches roll back.
- Migration preflight stops on invalid legacy Replay chains, unknown legacy task statuses, or checkpoint-to-Replay binding mismatches.
- Idempotency fingerprint now binds goal, delay, execution mode, idempotency scope, and metadata.
- Lifecycle completion remains distinct from task outcome. An ambiguous legacy lifecycle status cannot be promoted to `SUCCESS`.

### B3 — Authority, approval, trust, replay controls

- Missing authority root is now `AUTHORITY_ROOT_NOT_PROVISIONED`; no silent self-provisioned trust anchor.
- `ToolGovernance` consumes a signed, task-and-tool-scoped authority token from `HG_TOOL_AUTHORITY_TOKEN_FILE`; it no longer mints its own token from matching environment strings.
- Revocation can be persisted through `HG_AUTHORITY_REVOCATION_FILE`; missing persistence configuration fails closed when revocation is requested.
- Added `runtime/go_runtime/core/approval.py`. The plain string `"approved"` is not approval evidence. Approval must be issuer-verified and bound to subject, tool, arguments digest, Policy V1 hash, scope, expiry, and nonce. Reused approval nonces are denied.
- `TRUSTED_APPROVAL_ISSUERS` is intentionally empty until trusted bootstrap provisions an issuer. Consequently, destructive operations remain blocked until that trust boundary is actually provisioned.
- Certification firewall now validates a stored evidence digest against current canonical fields, rather than comparing a digest to itself.

### B4 — Unknown external side effects

- A negative response with a possible side effect now classifies as `UNKNOWN`, not retryable `FAILED`.
- Unknown side-effect states refuse blind retry and require reconciliation.
- Added negative tests for negative responses after possible side effects and for approval-string bypass attempts with an assertion that the adapter was not invoked.

### B5 — Regression and provenance

- Regression ran locally on the isolated working tree using Python 3.14.6 in Termux/Android; no production runtime was changed or restarted.
- Full suite: `196 passed in 4.49s`, exit code `0`.
- `python -m compileall -q runtime tests`: exit code `0`.
- `git diff --check` with `cr-at-eol` configured for the canonical CRLF `server.py`: exit code `0`.
- Raw test output: `evidence/B1_B5_REGRESSION_STDOUT.txt`; exit code: `evidence/B1_B5_REGRESSION_EXIT_CODE.txt`.
- Compile output and exit code: `evidence/B1_B5_COMPILEALL_STDOUT.txt`, `evidence/B1_B5_COMPILEALL_EXIT_CODE.txt`.
- Diff-check output and exit code: `evidence/B1_B5_DIFF_CHECK_STDOUT.txt`, `evidence/B1_B5_DIFF_CHECK_EXIT_CODE.txt`.
- Source/test patch snapshot: `evidence/B1_B5_RECONCILIATION_DIFF.patch.gz` (gzip-compressed patch snapshot).

## SHA-256 of captured evidence

- Regression stdout: `3d53f22a3c06053ca7bed0be6e6f45d38a07952110372cce86d4ab691479faa2`
- Regression exit code file: `bde294368bfed77c2cddf8cec271d398aee9cdbab3b26e1059281bd33adb0120`
- Compile stdout: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Compile exit code file: `bde294368bfed77c2cddf8cec271d398aee9cdbab3b26e1059281bd33adb0120`
- Diff-check stdout: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Diff-check exit code file: `bde294368bfed77c2cddf8cec271d398aee9cdbab3b26e1059281bd33adb0120`
- Reconciliation patch: `6ee2b814f2ade2c8fd55a7aa628ba39eb7d0a18b16c92ababf68ca5d93cc18f6`

## Remaining blockers — do not certify

- `TRUSTED_VERIFIER_REGISTRY` remains empty. No production independent verifier was provisioned or exercised.
- `TRUSTED_APPROVAL_ISSUERS` remains empty. Destructive approval is fail-closed; production approval issuance is not yet operational.
- No independent production E2E was run. Local tests do not establish production runtime commit/tree identity, deployment provenance, or external-system behavior.
- Therefore PAG-1.0 remains `BLOCKED`; `INDEPENDENTLY_VERIFIED`, `PRODUCTION_READY`, and release certification are not claimed.
- No merge into canonical, deploy, restart, or production mutation was performed.
