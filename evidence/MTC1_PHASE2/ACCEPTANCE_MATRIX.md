# MTC-1.0 Phase 2 — Acceptance Matrix

Legend — **Evidence class**: `code` (static/analysis), `unit` (isolated test),
`replica` (non-device execution), `runtime` (on the real device/edge), `external` (web doc).
**Status**: `PASS` / `FAIL` / `BLOCKED` / `NOT_RUN`.
Runtime PASS is only claimed with device/edge evidence. Unit/replica never substitute.

Mandate name → real artifact mapping:

| Mandate | Real artifact |
|---|---|
| `toolplane` (6 tools) | `/sdcard/Phần Mềm HG/toolplane/hg_tool_plane.py` (sha256 `16AE914D…524`) |
| `stt-health-readonly.yaml` | `HG-GO-DEPLOY/HG-CONNECTOR-HEALTH-OPENAPI.yaml` |
| `verify_b1_runtime.py` | (does not exist) → runtime probes + `tests/test_governance_negative.py` |
| `c_allow.sh` | (does not exist) → canonical `AuthorityRoot.issue()` path |
| branch `mtc1/legacy-decoupling-governance` | does not exist → `feature/stt-b1-b5-reconciliation-20261010` |
| `ACCEPTANCE_MATRIX.md` | this file |

---

## Gate B1 — `go_health` (liveness + authenticated HTTP 200)

| Item | Status | Class | Evidence |
|---|---|---|---|
| VPS1 edge liveness | **PASS** | runtime | `GET https://160.191.242.198/edge/health` → HTTP 200 `{"ok":true,"edge":"HG_EDGE","gate":true}` (2026-10-10T10:24Z) |
| Auth enforced (no token ⇒ 401) | **PASS** | runtime | `GET /h/phone-primary-u0_a460/api/health` → HTTP 401 |
| GO runtime (tool `go_health` → `/healthz` + `/v1/status`) | **FAIL** | runtime | `/sdcard/hg-go-deploy-result.txt`: `FAIL: sv up thất bại` … `DEPLOY OR PROBE FAILED` |
| Tool `go_health` executes on phone | **NOT_RUN** | runtime | no GO runtime process on phone; Termux private storage not readable |

## Gate B5-a — D1–D4, tool deny-list, `audit_tail`, audit integrity

| Item | Status | Class | Evidence |
|---|---|---|---|
| 6 tools present & exact | **PASS** | code | `python hg_tool_plane.py selftest` → `[vps_exec, go_health, github_whoami, github_api, audit_tail, phone_health]` |
| Destructive deny-list; `approved=true` does NOT bypass | **PASS** | unit | `tests/OUTPUT_supervisor…`/`OUTPUT_governance_negative.txt` (denylist_rmrf/dd/delete) |
| Audit hash-chain verify + tamper detection | **PASS** | unit | `verify_audit()` good→ok, tamper→`hash mismatch` (module test) |
| Canonical fail-closed for side-effect tools | **PASS** | unit | `write_mapped_unavailable_failclosed`, `write_unmapped_default_deny` |
| Deny-list at tool layer on **runtime** | **NOT_RUN** | runtime | requires toolplane executing on phone (Termux access) |
| `audit_tail` returns real phone audit | **NOT_RUN** | runtime | phone audit is `~/.config/hg/toolplane_audit.jsonl` (private Termux) — unreadable |
| Governance coverage gap (CANON_MAP) | **FAIL→fixed in patch** | code | only `go_health` was mapped; `vps_exec`/`github_api` writes bypassed canonical gov → closed by `patch/hg_tool_plane.governance.patch` |

Note: `D1–D4` labels are not found anywhere in the repository; verified here are the
concrete controls the labels presumably denote (schema validation, deny-list, canonical
fail-closed, audit integrity).

## Gate B2 — supervisor runtime

| Item | Status | Class | Evidence |
|---|---|---|---|
| Supervisor process running | **PASS** | runtime | `adb` 4× samples: pid `10459` `bash …/toolplane/health-tunnel-supervisor.sh` |
| Tunnel stays up / serves | **FAIL** | runtime | 0 `health-tunnel.py` processes across samples; last `GATE_REQUEST` 2026-10-10T00:38:59Z |
| No restart loop | **FAIL** | runtime | supervisor restarts a process that exits immediately (missing env) |
| Root cause | **PASS (identified)** | code | `start-health-tunnel.sh` exports `HG_EDGE_*`; supervisor did not |
| Fix (hardened supervisor) | **PASS** | unit | `tests/OUTPUT_supervisor_logic.txt` 15/15 incl. T7 env-export proof |
| Duplicate/restart-loop E2E on device | **NOT_RUN** | runtime | needs Termux; harness provided (`test_supervisor_e2e_linux.sh`) |
| `edge queue=0` | **PASS (historical)** | runtime | `/sdcard/hg-verify-result.txt` 2026-10-09: `/edge/tunnel/status` queue=0 (tunnel live then) |

## Gate B4 — ChatGPT Action E2E

| Item | Status | Class | Evidence |
|---|---|---|---|
| Schema valid OpenAPI 3.1, HTTPS, GET-only, Bearer | **PASS** | code/external | `HG-CONNECTOR-HEALTH-OPENAPI.yaml` + OpenAI docs |
| No token plaintext in repo/schema/log | **PASS** | code | yaml references `gateBearer`; no secret value present |
| Import + configure in ChatGPT | **BLOCKED** | external | no ChatGPT session/credentials; workspace domain allowlist + retirement caveat |
| Request reaches endpoint, HTTP 200, server-side evidence | **NOT_RUN** | runtime | requires an authenticated call (token holder) |

## Gate B5-b — canonical GO DENY + ALLOW

| Item | Status | Class | Evidence |
|---|---|---|---|
| DENY path exists & fail-closed | **PASS** | code | `tool_governance.py`; `governance_decide` canonical deny → DENY |
| DENY observed on real phone | **NOT_RUN** | runtime | no phone audit readable |
| ALLOW prerequisite: external authority root | **BLOCKED** | code | `authority.py::_require_external` ⇒ `AUTHORITY_ROOT_NOT_EXTERNAL`; no `/etc/hg/authority/root.key` |
| ALLOW prerequisite: trusted approval issuers / verifier | **BLOCKED** | code | `TRUSTED_APPROVAL_ISSUERS`/verifier intentionally empty (B1_B5 impl doc) |
| ALLOW (`state=COMPLETED`, witness, ledger STARTED→COMPLETED) | **NOT_RUN** | runtime | blocked by prerequisites; must not fabricate external authority |

## Gate — Evidence / manifest / SHA-256

| Item | Status | Class | Evidence |
|---|---|---|---|
| Local test suite (reproduced independently) | **PASS** | unit/replica | `196 passed` exit 0 (`tests/OUTPUT_regression.txt`) |
| Repo manifest vs phone | **PARTIAL** | code | `GO-MATERIALIZATION-MANIFEST.json`: 20 files `ABSENT_ON_PHONE`; no phone hash verify |
| This directory hashed | **PASS** | code | `MANIFEST.sha256` |

---

## Overall

**INCOMPLETE.** Runtime PASS: B1-edge liveness (partial), B2 supervisor process (partial).
All other required gates are FAIL / BLOCKED / NOT_RUN with evidence. No gate is claimed
COMPLETED without device evidence.
