# MASTER GOVERNANCE RULESET V1 ? Remote Branch and Legacy Reference Audit

Date: 2026-10-10
Repository: OAI-GIANG/GO
Method: fetched all remote heads into local-only `refs/remotes/audit/*`; no remote branch was changed.

## Branch inventory

| Remote branch | HEAD | Tracked files | V1 source | V1 SHA-256 | Legacy policy/design files | Legacy implementation paths | GO authority contract |
|---|---:|---:|---|---|---:|---:|---|
| HG-V2-REMEDIATION | cecfb72 | 84 | NO | MISSING | 0 | 0 | YES |
| feature/hg-bounded-autonomy-v2-20261008 | 9aa1e29 | 44 | NO | MISSING | 0 | 0 | YES |
| feature/hg-tool-runtime-mcp-20261007 | 274bb56 | 33 | NO | MISSING | 0 | 0 | YES |
| feature/master-governance-ruleset-v1-cutover-20261010 | 8eaf2d7 | 19 | YES | cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af | 0 | 0 | NO |
| feature/phone-agent-v1 | 3e09815 | 51 | NO | MISSING | 0 | 0 | YES |
| feature/tvs-implementation-20261007 | 41d53f6 | 33 | NO | MISSING | 0 | 0 | YES |
| feature/tvs-trust-anchor-remediation-20261007 | b793e45 | 40 | NO | MISSING | 0 | 0 | YES |
| feature/vps2-execution-bridge-v3-20261007 | 6209498 | 29 | NO | MISSING | 0 | 0 | YES |
| hg-core | a4d4535 | 42 | NO | MISSING | 0 | 0 | YES |
| hg-core-distilled | 452165b | 40 | NO | MISSING | 10 | 29 | NO |
| hg-phone-bridge-v1 | 4a20c31 | 3 | NO | MISSING | 0 | 0 | NO |

Expected canonical V1 SHA-256: `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`.

## Active-code references to legacy policy identifiers (0)

No matches in scanned Python, shell, YAML, or TOML files across fetched remote branch heads.

## Active-code references to V1 source (17)

- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/bootstrap.py:13:SOURCE = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/bootstrap.py:14:BINDING = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/bootstrap.py:34:        "generated_from": "control/MASTER_GOVERNANCE_RULESET_V1.md",`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/engine.py:10:SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/engine.py:11:BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/generated/runtime.py:10:SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:runtime_v1/generated/runtime.py:11:BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_hg_coherence.py:9:        source = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_phone_payload.py:17:SOURCE = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_phone_payload.py:18:BINDING = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_phone_payload.py:33:            target = Path(tmp) / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_runtime.py:25:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", target / "MASTER_GOVERNANCE_RULESET_V1.md")`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_runtime.py:26:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json", target / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json")`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_runtime.py:27:            p = target / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_runtime.py:35:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", target / "MASTER_GOVERNANCE_RULESET_V1.md")`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_runtime.py:36:            binding = json.loads((ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").read_text(encoding="utf-8"))`
- `feature/master-governance-ruleset-v1-cutover-20261010`: `audit/feature/master-governance-ruleset-v1-cutover-20261010:tests/test_v1_runtime.py:38:            (target / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").write_text(json.dumps(binding), encoding="utf-8")`

## Interpretation and limits
- `control/GO_RUNTIME_AUTHORITY_V1.md` is a runtime ownership/identity contract, not automatically a competing ruleset. It is reconciled in the integration branch to subordinate ownership semantics to V1 and to bind execution evidence to the policy hash.
- Presence of legacy design or implementation paths on a branch does not prove the branch is deployed or active. `hg-core-distilled` contains a separate historical/legacy tree and needs an explicit lifecycle decision before any branch cleanup.
- All 11 remote branch heads returned by GitHub were inventoried. This does not identify the actual VPS/phone deployment commit or uncommitted external worktrees.
- No branch deletion, force-push, history rewrite, or production deployment was performed.

## State
REMOTE_BRANCH_HEAD_INVENTORY: COMPLETE_FOR_11_FETCHED_HEADS
V1_SOURCE_ON_DEFAULT_AT_AUDIT_TIME: ABSENT
EXTERNAL_RUNTIME_ADOPTION: UNVERIFIED
HISTORY_PURGE: NOT_PERFORMED
