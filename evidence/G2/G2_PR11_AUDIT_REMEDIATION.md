# PR #11 Audit Findings — Remediation Record

Branch: `feature/g2-design-finalization-20261010` (base `hg-core`). PR #11.
Scope: close the approval-transport finding and strengthen tests. **No merge/deploy.**

## Finding → remediation

| # | Finding | Remediation | Evidence |
|---|---|---|---|
| F1 | HTTP submission path coerced approval to string: `approval=str(body.get("approval") or "not_required")` ⇒ an approval object could never be transported (and was stringified) | Added `GOApplication._deserialize_approval()` (never stringifies an object; `None`/""/"not_required" → sentinel; object → strict `ApprovalEvidence.from_json`; anything else → `ValueError` → HTTP 400). Added strict `ApprovalEvidence.from_json`/`to_dict` (required fields, no unknown fields, non-empty strings). `verify_approval` now also binds `target`. `ToolGovernance` passes `target=name`. Fail-closed when no trusted issuer. | `runtime/go_runtime/core/{server,approval,tool_governance}.py`; tests `test_g2_approval_api.py` |
| F2 | Missing approval integration tests | Added unit + transport + ToolGovernance integration tests: valid; bad signature; wrong subject/tool/scope/fingerprint/policy-hash/target; expired; replayed nonce; malformed payload; missing issuer; string-approval denied; destructive not executed when invalid | `tests/test_g2_approval_api.py` (25 tests) |
| F3 | Weak source-text checks (`server.py` string count) | Replaced with per-entry-point **behavior** oracle: force `verify_governance_source` to raise and assert `execute_tool`/`execute`/`run_objective`/`submit`/`execute_vps2` all fail closed | `test_g2_entrypoints_fail_closed_on_invalid_governance` |
| F4 | No `unify_evidence` behavior test | Added behavior test: single item → count 1, no conflicts; duplicate id → `duplicate_representations["E1"]==2` | `test_g2_unify_evidence_behavior` |
| F5 | Trust provisioning | `TRUSTED_VERIFIER_REGISTRY` / `TRUSTED_APPROVAL_ISSUERS` remain EMPTY (not self-granted). Tests register a **test-only** issuer via monkeypatch; production stays fail-closed. | `approval.py` (`TRUSTED_APPROVAL_ISSUERS = ()`) |
| F6 | Policy V1 / approval binding integrity | Unchanged: policy blob `64862401…`, binding blob `0e489463…` identical to `hg-core`; content sha256 policy `cc1a8b17…`, binding `e8f1f6bb…` | git object ids; `MANIFEST` |
| F7 | Regression/compile/diff | Full suite **232 passed**; `compileall` exit 0; `git diff --check` clean | `G2_APPROVAL_REMEDIATION_TESTS.txt` |

## Behaviour notes
- Approval remains **evidence, not a flag**: a bare `"approved"` yields `APPROVAL_EVIDENCE_REQUIRED`.
- Transport validates *shape*; `verify_approval` (trusted issuer) validates *signature + binding + expiry + nonce*.
- No trusted issuer provisioned ⇒ destructive operations stay blocked (`TRUSTED_APPROVAL_ISSUER_NOT_PROVISIONED`).

## Remaining blockers (unchanged)
- BLK-3 trusted verifier provisioning (external); BLK-4 trusted approval issuer (external);
  BLK-1 PAG-1.0; BLK-2 D-G2 definitions; BLK-6 runtime build-identity mapping.
- Independent audit (STT) NOT RUN. Merge held.
