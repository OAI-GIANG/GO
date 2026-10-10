# MTC-1.0 Phase 2 — Acceptance Matrix

Legend — **Evidence class**: `code` (static), `unit` (isolated), `replica` (executed,
not on the phone), `runtime` (on the real device/edge), `external` (web doc).
**Status**: `PASS` / `FAIL` / `BLOCKED` / `NOT_RUN`. Runtime PASS requires device/edge evidence.

Mandate name → real artifact:

| Mandate | Real artifact |
|---|---|
| `toolplane` (6 tools) | `/sdcard/Phần Mềm HG/toolplane/hg_tool_plane.py` (sha256 `16AE914D…524`) |
| `stt-health-readonly.yaml` | `HG-GO-DEPLOY/HG-CONNECTOR-HEALTH-OPENAPI.yaml` |
| `verify_b1_runtime.py` | does not exist → runtime probes + `tests/test_*` |
| `c_allow.sh` | does not exist → canonical `AuthorityRoot.issue()` path |
| branch `mtc1/legacy-decoupling-governance` | does not exist → `feature/stt-b1-b5-reconciliation-20261010` |

Raw captures: `tests/OUTPUT_runtime_evidence.txt`, `tests/OUTPUT_go_replica_boot.txt`,
`tests/OUTPUT_b5b_allow_replica.txt`, `tests/OUTPUT_regression.txt`,
`tests/OUTPUT_supervisor_logic.txt`, `tests/OUTPUT_governance_negative.txt`.

---

## Gate B1 — `go_health` (liveness + authenticated HTTP 200)

| Item | Status | Class | Evidence |
|---|---|---|---|
| VPS1 edge liveness | **PASS** | runtime | `GET /edge/health` → 200 `{"ok":true,"edge":"HG_EDGE","gate":true}` |
| Auth enforced (no token ⇒ 401) | **PASS** | runtime | gate endpoint → 401; GO `/v1/status` (replica) → 401 |
| GO entrypoint sound (`-m runtime.go_runtime.core.server`) | **PASS** | replica | `/healthz` `status:ok`, `/v1/status` RUNNING, 28 ops incl. `vps1.edge.health` |
| GO governance source verified | **PASS** | replica | `source_sha256=cc1a8b17…` == protected Policy V1 hash |
| **GO runtime on phone** | **FAIL** | runtime | `runsv go-runtime` present but server lives <~2s (pid sample 2 caught `30217`, samples 1/3 empty); **no `127.0.0.1:8877` listener** |
| Legacy HG `/api/health` via `adb forward` | **PASS** | runtime | `HTTP 200 {"runtime":"READY","core":"HG_LOCAL","phone_bridge":"V2"}` |

## Gate B2 — supervisor runtime

| Item | Status | Class | Evidence |
|---|---|---|---|
| runit supervision running | **PASS** | runtime | `runsvdir` pid 9688; `runsv{go-runtime,hg-runtime,hg-backend,sshd,…}` |
| Supervisor process running | **PASS** | runtime | pid `10459` `bash …/toolplane/health-tunnel-supervisor.sh` |
| Tunnel process / serving | **FAIL** | runtime | 0 `health-tunnel.py`; last `GATE_REQUEST` `2026-10-10T00:38:59Z` |
| Root cause | **PASS (identified)** | code | `start-health-tunnel.sh` exports `HG_EDGE_*`; supervisor did not |
| Fix (hardened supervisor) | **PASS** | unit | `tests/OUTPUT_supervisor_logic.txt` 15/15 incl. T7 env-export proof |
| Device E2E | **NOT_RUN** | runtime | needs Termux; `test_supervisor_e2e_linux.sh` provided |

## Gate B5-a — deny-list, `audit_tail`, audit integrity

| Item | Status | Class | Evidence |
|---|---|---|---|
| 6 tools exact | **PASS** | code | `selftest` → the six names |
| Deny-list; `approved=true` no bypass | **PASS** | unit | governance negative 13/13 |
| Audit hash-chain verify + tamper detect | **PASS** | unit | good→ok, tamper→`hash mismatch` |
| Canonical fail-closed for side-effect tools | **PASS** | unit | mapped/unmapped/unavailable/malformed |
| Governance coverage gap | **FIXED** | code | `patch/hg_tool_plane.governance.patch` (default-deny unmapped) |
| Deny-list / `audit_tail` on **runtime** | **NOT_RUN** | runtime | toolplane needs Termux; phone audit is private |

## Gate B4 — ChatGPT Action E2E

| Item | Status | Class | Evidence |
|---|---|---|---|
| Schema valid OpenAPI 3.1, GET-only, Bearer | **PASS** | code | `HG-CONNECTOR-HEALTH-OPENAPI.yaml` |
| HTTPS endpoint + valid TLS | **PASS** | runtime | Let's Encrypt cert, IP SAN `160.191.242.198`, expires 2026-10-13 |
| No token plaintext in repo/schema/log | **PASS** | code | yaml references `gateBearer` only |
| Import + E2E (real request, HTTP 200) | **BLOCKED** | external | no ChatGPT UI/credentials; workspace domain allowlist |

## Gate B5-b — canonical GO DENY + ALLOW

| Item | Status | Class | Evidence |
|---|---|---|---|
| DENY: no external root ⇒ `AUTHORITY_ROOT_NOT_PROVISIONED` | **PASS** | replica | `tests/OUTPUT_b5b_allow_replica.txt` |
| DENY: ephemeral root cannot issue ⇒ `AUTHORITY_ROOT_NOT_TRUSTED` | **PASS** | replica | same |
| DENY: no revocation store ⇒ `AUTHORITY_REVOCATION_STORE_NOT_CONFIGURED` | **PASS** | replica | same |
| DENY: no token file ⇒ `AUTHORITY_PROVENANCE_MISSING` | **PASS** | replica | same |
| **ALLOW mechanics** (external root→token→`STARTED→COMPLETED`→witness) | **PASS** | replica | ledger `ACCEPTED..COMPLETED`, witness + `governance_source_sha256` |
| Idempotency (`IDEMPOTENT_RESULT_REUSE_DENIED`) | **PASS** | replica | same |
| ALLOW on the **phone runtime** | **BLOCKED** | runtime | external owner must provision root/issuers/token |

## Gate — Evidence / manifest / SHA-256

| Item | Status | Class | Evidence |
|---|---|---|---|
| Canonical regression (reproduced) | **PASS** | unit | 196 passed, exit 0 |
| This directory hashed | **PASS** | code | `MANIFEST.sha256` (+ `verify_artifacts.sh`) |
| Repo manifest vs phone | **PARTIAL** | code | `GO-MATERIALIZATION-MANIFEST.json`; no phone hash verify |

---

## Overall

**INCOMPLETE.** Notable progress this run: GO entrypoint and full ALLOW/DENY authority
mechanics verified on a **replica**; phone GO crash-loop precisely characterised; runit
supervision confirmed; edge TLS confirmed valid. Remaining blockers require **Termux access
(B1, B2, B5-a runtime)**, **ChatGPT UI (B4)**, and **external authority provisioning
(B5-b ALLOW)** — exact actions in `OWNER_RUNBOOK.md`.
