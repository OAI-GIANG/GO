# MTC-1.0 Phase 2 — Acceptance Matrix

Legend — **Evidence class**: `code` (static), `unit` (isolated), `replica` (executed off-target),
`runtime` (on the real device/host), `external` (web doc). **Status**: `PASS`/`FAIL`/`BLOCKED`/`NOT_RUN`.
Runtime PASS requires on-target evidence. Raw captures in `tests/OUTPUT_*.txt`.

Targets (measured): **VPS1** `160.191.242.198` (`vps-hjcscw`) hosts the canonical GO runtime
(`/opt/go`, systemd `go-runtime`, `127.0.0.1:8877`) and the edge (`hg-edge.service`). The
**phone** (OPPO PKC110) runs the HG legacy runtime + the toolplane. `go_health` probes VPS1.

---

## Gate B1 — `go_health` (liveness + authenticated HTTP 200) — target VPS1

| Item | Status | Class | Evidence |
|---|---|---|---|
| GO process stable | **PASS** | runtime | `go-runtime` active/running, MainPID 83645, `Restart=always` |
| Listener `127.0.0.1:8877` | **PASS** | runtime | `ss` → python3 pid 83645 |
| `/healthz` contract | **PASS** | runtime | `{"status":"ok","version":"0.1.1"}` |
| `/v1/status` authenticated | **PASS** | runtime | HTTP **200**, `environment=production`, 28 ops |
| Auth enforced (no token) | **PASS** | runtime | HTTP **401** |
| Identity: commit/tree | **PASS** | runtime | `GO_COMMIT=d635e883…`, `GO_TREE_SHA=00ba3fcd…` |
| Phone-local GO (separate deploy) | **FAIL** | runtime | crash loop; root-caused: missing governance source (`tests/OUTPUT_go_crashloop_rootcause.txt`) |

## Gate B2 — tunnel/supervisor runtime

| Item | Status | Class | Evidence |
|---|---|---|---|
| Supervisor process (phone) | **PASS** | runtime | pid `10459` running |
| Tunnel draining / serving | **FAIL** | runtime | edge `queue=3, pending=0`; `GATE_TIMEOUT 504` + BrokenPipeError in `hg-edge` |
| Restart-loop | **FAIL** | runtime | no `health-tunnel.py`; supervisor cannot keep it up |
| Fix (hardened supervisor) | **PASS** | unit | 15/15 incl. env-export proof |
| `edge queue=0` | **FAIL** | runtime | currently `3` |

## Gate B5-a — tool-layer deny / audit

| Item | Status | Class | Evidence |
|---|---|---|---|
| 6 tools exact | **PASS** | code | toolplane `selftest` |
| Deny-list; `approved` no bypass | **PASS** | unit | governance negative 13/13 |
| Audit hash-chain verify/tamper | **PASS** | unit | module test |
| Governance coverage gap | **FIXED** | code | `patch/hg_tool_plane.governance.patch` |
| Canonical tool-layer DENY on real runtime | **PASS** | runtime | VPS1 `ToolGovernance.execute(vps1.edge.health)` → DENIED `AUTHORITY_PROVENANCE_MISSING`; production ledger `/opt/go/data/tool-events.jsonl` (1733 lines) shows phone-originated DENIED events |
| Phone `audit_tail` / audit-chain | **NOT_RUN** | runtime | phone audit is Termux-private |

## Gate B4 — ChatGPT Action E2E

| Item | Status | Class | Evidence |
|---|---|---|---|
| Schema valid OpenAPI 3.1, GET, Bearer | **PASS** | code | `HG-CONNECTOR-HEALTH-OPENAPI.yaml` |
| HTTPS + valid TLS | **PASS** | runtime | Let's Encrypt cert, IP SAN `160.191.242.198` |
| TLS renewal configured | **FAIL/BLOCKED** | runtime | certbot **not installed**, no renewal timer; cert expires `2026-10-13T01:54Z` |
| Gate auth enforced | **PASS** | runtime | `/h/...` no token → 401 |
| E2E real request HTTP 200 | **BLOCKED** | runtime | tunnel down (queue=3/GATE_TIMEOUT); also needs ChatGPT UI + domain allowlist |

## Gate B5-b — canonical DENY + ALLOW

| Item | Status | Class | Evidence |
|---|---|---|---|
| DENY (replica) | **PASS** | replica | `tests/OUTPUT_b5b_allow_replica.txt` |
| **DENY (real runtime VPS1)** | **PASS** | runtime | `tests/OUTPUT_vps1_runtime.txt` (ledger `…→AUTHORIZATION_PENDING→DENIED`) |
| ALLOW mechanics (replica) | **PASS** | replica | external root→token→`STARTED→COMPLETED`+witness+idempotency |
| ALLOW on real target | **BLOCKED** | runtime | `/etc/hg/authority/` **absent** (no `root.key`); authority env empty; `TRUSTED_APPROVAL_ISSUERS` empty; must be provisioned by the external owner (not Deep) |

## Gate — Evidence / manifest / SHA-256

| Item | Status | Class | Evidence |
|---|---|---|---|
| Canonical regression | **PASS** | unit | 196 passed, exit 0 |
| This directory hashed (LF check) | **PASS** | code | `MANIFEST.sha256`; fresh-clone `sha256sum -c` all OK |

---

## Overall

**INCOMPLETE.** New runtime PASS this round: **B1** (VPS1 GO liveness + authenticated 200 +
401) and **B5-b DENY** (VPS1 canonical ToolGovernance, and the production ledger shows real
DENIED events). Remaining: **B2** tunnel (edge `queue=3`, phone tunnel not running), **B4**
tunnel+UI+**cert renewal**, **B5-b ALLOW** (external authority not provisioned), **B5-a**
phone-side audit runtime. Exact owner actions in `OWNER_RUNBOOK.md`.
