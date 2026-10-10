# HG RUNTIME CANONICAL DEPLOYMENT — V1

**Status:** RECORDED, NOT DEPLOYED
**Canonical authority:** `OAI-GIANG/GO` @ `hg-core`
**Verified on:** VPS1 (vps-hjcscw)

## 1. Reconciliation of `hg-core` and `HG-V2-REMEDIATION`

| Fact | Value |
|---|---|
| merge-base | `a4d453519ea8` (2026-10-08 19:34:32 +0700) |
| commits exclusive to `hg-core` | 6 |
| commits exclusive to `HG-V2-REMEDIATION` | 16 |
| modules only on HG-V2 | 11: assurance, authority, certification_firewall, corroboration, epistemics, evidence, freshness, intelligence_eval, ivv, provenance, reconciliation |
| modules only on hg-core | 5: contract_identity, evidence_ladder, governance_lifecycle, governance_source, governance_supplement |
| modules on both | 20 (including server.py, tool_governance.py, tool_runtime.py, cognitive.py, store.py, go_kernel.py) |

## 2. Compatibility finding — no remediation component is accepted

- `hg-core` imports **none** of the 11 HG-V2-only modules.
- On `HG-V2-REMEDIATION` itself, only **`authority`** and **`evidence`** are imported (by cognitive.py, tool_governance.py, checkpoint.py, store.py). The other **9 are dead code on their own branch**.
- `hg-core`'s versions of those consuming files do not import them.
- `hg-core` already owns its execution gate: `server.py` calls `verify_governance_source()` at 10 points, including `__init__`, every protected operation, the status payload, and before evidence promotion under `GateResult.ALLOW`.

**Decision:** the canonical artifact is `hg-core` itself. No `HG-V2-REMEDIATION` component is merged, so **no second authority owner and no competing execution runtime is created**.

## 3. Deployment delta

| | files (.py) | digest |
|---|---|---|
| canonical artifact | 53 | `0a1919b5bfd9338f7fb1cc65279c0d071ffb76c9cc1f233412694794784d2bda` |
| deployed `/opt/go` | 50 | `d1e8bfab95f8264f3cabbe5482aa731ad52c98f189886d9580c74dcae0a1509e` |

Files present in canon but missing from `/opt/go`: **none**.
Files present in `/opt/go` but absent from canon: the **11 orphans** listed in §1.

## 4. Staging verification (production untouched)

| Test | Result |
|---|---|
| positive: hg-core runtime + copy of the production datastore | starts; `/healthz` 200; `governance.status = VERIFIED` |
| negative: ruleset tampered by 1 byte | exit 1, `GovernanceSourceError: V1_CANONICAL_SOURCE_HASH_MISMATCH` |
| negative: ruleset removed | exit 1, `GovernanceSourceError: V1_CANONICAL_SOURCE_MISSING` |
| negative: approval binding removed | exit 1, `GovernanceSourceError: V1_APPROVAL_BINDING_MISSING` |
| negative: `GO_API_TOKEN` absent | exit 1, `ValueError: GO_API_TOKEN is required unless anonymous mode is explicitly enabled` |
| restart/recovery x3 | `health=200 governance=VERIFIED` on every start; datastore intact, 10 tables |
| regression | 137 tests, 3 skipped, 3 collection errors — all three are `ModuleNotFoundError: pytest` (pytest is absent on the host); no test failure |

## 5. Deployment plan (NOT executed)

1. Record a pre-deployment manifest of `/opt/go` (50 files) — already captured.
2. Archive the 11 orphan modules to `srv/hg-legacy-archive-*/opt-go-orphans-*` rather than deleting them.
3. Extract the canonical artifact over `/opt/go`.
4. `systemctl restart go-runtime`; expect `/healthz` 200 with `governance.status = VERIFIED`.
5. Smoke test the protected routes and confirm the datastore opens.

## 6. Rollback

`/srv/hg-legacy-archive-20261011/opt-go-backup-20261011/opt-go-pre-governance-20261011.tgz` (439,468 bytes) contains the exact running `server.py` and the 4 live modules.
Rollback: `tar xzf <backup> -C / && systemctl restart go-runtime`.

## 7. Open blocker

Deployment is **not** executed: choosing to move VPS1 from the `HG-V2-REMEDIATION` execution model to the `hg-core` canonical model is an **owner architectural decision**, not an executor patch.
