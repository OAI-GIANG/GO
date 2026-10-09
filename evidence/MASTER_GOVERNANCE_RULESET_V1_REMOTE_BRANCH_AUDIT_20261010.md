# MASTER GOVERNANCE RULESET V1 ? Remote Branch and Legacy Reference Audit

Date: 2026-10-10
Repository: OAI-GIANG/GO
Default branch: `hg-core`
Method: all remote heads fetched into local-only `refs/remotes/audit/*`; no remote branch changed by the audit.

## Remote branch inventory

| Remote branch | HEAD | Tracked files | V1 source | V1 SHA-256 | Legacy policy/design files | Legacy implementation paths | GO authority contract |
|---|---:|---:|---|---|---:|---:|---|
| HG-V2-REMEDIATION | cecfb72 | 84 | NO | MISSING | 0 | 0 | YES |
| feature/hg-bounded-autonomy-v2-20261008 | 9aa1e29 | 44 | NO | MISSING | 0 | 0 | YES |
| feature/hg-tool-runtime-mcp-20261007 | 274bb56 | 33 | NO | MISSING | 0 | 0 | YES |
| feature/master-governance-ruleset-v1-cutover-20261010 | 8eaf2d7 | 19 | YES | cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af | 0 | 0 | NO |
| feature/master-governance-v1-integration-20261010 | 4d1ce8b | 49 | YES | cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af | 0 | 0 | YES |
| feature/phone-agent-v1 | 3e09815 | 51 | NO | MISSING | 0 | 0 | YES |
| feature/tvs-implementation-20261007 | 41d53f6 | 33 | NO | MISSING | 0 | 0 | YES |
| feature/tvs-trust-anchor-remediation-20261007 | b793e45 | 40 | NO | MISSING | 0 | 0 | YES |
| feature/vps2-execution-bridge-v3-20261007 | 6209498 | 29 | NO | MISSING | 0 | 0 | YES |
| hg-core | 6a700ed | 49 | YES | cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af | 0 | 0 | YES |
| hg-core-distilled | 452165b | 40 | NO | MISSING | 10 | 29 | NO |
| hg-phone-bridge-v1 | 4a20c31 | 3 | NO | MISSING | 0 | 0 | NO |

Expected canonical V1 SHA-256: `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`. The default branch now contains V1 and its hash matches the expected value.

## Active-code references to legacy policy identifiers (0)

No matches in scanned Python, shell, YAML, or TOML files across fetched remote branch heads.

## Active-code references to V1 source (37)

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
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:runtime/go_runtime/core/governance_source.py:9:SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:runtime/go_runtime/core/governance_source.py:10:BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:39:        self.assertIn("control/MASTER_GOVERNANCE_RULESET_V1.md` is the sole governing policy source", text)`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:55:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", root / "control" / "MASTER_GOVERNANCE_RULESET_V1.md")`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:56:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json", root / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json")`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:57:            p = root / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:66:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", root / "control" / "MASTER_GOVERNANCE_RULESET_V1.md")`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:67:            binding = json.loads((ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").read_text(encoding="utf-8"))`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:69:            (root / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").write_text(json.dumps(binding), encoding="utf-8")`
- `feature/master-governance-v1-integration-20261010`: `audit/feature/master-governance-v1-integration-20261010:tests/test_governance_source.py:126:        self.assertIn((ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md").read_text(encoding="utf-8"), body["messages"][0]["content"])`
- `hg-core`: `audit/hg-core:runtime/go_runtime/core/governance_source.py:9:SOURCE_NAME = "MASTER_GOVERNANCE_RULESET_V1.md"`
- `hg-core`: `audit/hg-core:runtime/go_runtime/core/governance_source.py:10:BINDING_NAME = "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:39:        self.assertIn("control/MASTER_GOVERNANCE_RULESET_V1.md` is the sole governing policy source", text)`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:55:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", root / "control" / "MASTER_GOVERNANCE_RULESET_V1.md")`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:56:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json", root / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json")`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:57:            p = root / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:66:            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", root / "control" / "MASTER_GOVERNANCE_RULESET_V1.md")`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:67:            binding = json.loads((ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").read_text(encoding="utf-8"))`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:69:            (root / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").write_text(json.dumps(binding), encoding="utf-8")`
- `hg-core`: `audit/hg-core:tests/test_governance_source.py:126:        self.assertIn((ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md").read_text(encoding="utf-8"), body["messages"][0]["content"])`

## Active PR / branch reconciliation
- PR #9 (`feature/master-governance-v1-integration-20261010` ? `hg-core`) was merged at `6a700ede39d2118fb2e5289ce1f0f49070877a17`.
- PR #8 (`HG-V2-REMEDIATION` ? `hg-core`) remains OPEN and is now reported by GitHub as CONFLICTING after the V1 merge. It overlaps four runtime files: `runtime/go_kernel.py`, `runtime/go_runtime/core/cognitive.py`, `runtime/go_runtime/core/server.py`, and `runtime/go_runtime/core/tool_governance.py`.
- PR #8 branch was not modified or merged by this integration. It must be reconciled while preserving its P0/V2 changes before it can be merged.

## Interpretation and limits
- `control/GO_RUNTIME_AUTHORITY_V1.md` is a runtime ownership/identity contract, not automatically a competing ruleset. The default branch version now subordinates it to V1 and binds execution evidence to the policy hash.
- `hg-core-distilled` still contains 10 legacy governance/design paths and 29 legacy implementation paths. Its deployment/maintenance status is unproven; those paths were not deleted.
- All remote branch heads were inventoried; branch presence alone does not prove deployment or current activity.
- No remote branch was deleted, no force-push/history rewrite was performed, and no VPS/phone deployment was performed.

## State
REMOTE_BRANCH_HEAD_INVENTORY: 12
DEFAULT_BRANCH_V1_SOURCE: VERIFIED
DEFAULT_BRANCH_SOURCE_HASH: VERIFIED
LEGACY_ACTIVE_CODE_REFERENCES: 0_FOUND_IN_SCANNED_CODE_TYPES
PR8_RECONCILIATION: BLOCKED_CONFLICTING
EXTERNAL_RUNTIME_ADOPTION: UNVERIFIED
HISTORY_PURGE: NOT_PERFORMED
