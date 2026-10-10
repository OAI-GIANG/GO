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
| Tunnel stable (single, no restart loop) | **PASS** | runtime | pid `2773` unchanged across 4 samples/30s |
| `edge queue = 0` | **PASS** | runtime | `/edge/tunnel/status` → `queue=0` stable |
| `GATE_REQUEST` HTTP 200 | **PASS** | runtime | gate round-trip 200; phone evidence `GATE_REQUEST …status:200 @11:10:53Z` |
| Root cause + fix | **PASS** | runtime+code | supervisor spawned the tunnel without `--apply`/env, so it exited instantly; tunnel artifact patched (self-config + apply-by-default); `tests/health-tunnel.phone.patch` |

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
| HTTPS + valid TLS | **PASS** | runtime | renewed: cert `notAfter 2026-10-17T02:09:59Z` |
| TLS renewal durable | **PASS** | runtime | `certbot-renew.timer` enabled (twice daily); certbot 5.8.0 |
| Gate auth enforced | **PASS** | runtime | no token → **401**; wrong token → 401 |
| Server-side authenticated 200 + device evidence | **PASS** | runtime | gate Bearer → **200** (`HG_TUNNEL_HEALTH`, `python 3.14.6`, `aarch64`); phone evidence `GATE_REQUEST status:200 @11:10:53Z` |
| ChatGPT UI import + domain allowlist (owner) | **BLOCKED** | external | no ChatGPT session; import + secret + allowlist is an owner/UI step |

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

**INCOMPLETE.** Runtime PASS this round: **B1** (VPS1 GO liveness + authenticated 200 + 401),
**B5-b DENY** (VPS1 canonical ToolGovernance + production-ledger DENIED events), **B2**
(phone tunnel single/stable, edge `queue=0`, `GATE_REQUEST 200`), and **B4 server-side +
TLS renewal** (authenticated gate 200 with device evidence; cert renewed to 2026-10-17 with a
renewal timer). Remaining: **B4 UI import** (owner), **B5-b ALLOW** (external authority not
provisioned), **B5-a phone-side audit runtime** (Termux), **phone-local GO** (separate; not
required for B1). Exact owner actions in `OWNER_RUNBOOK.md`.
