# MTC-1.0 Phase 2 — Acceptance Matrix (current)

**Owner decisions:** GPT/ChatGPT Action = OUT_OF_SCOPE; phone-local GO = OUT_OF_SCOPE.
Evidence classes: `runtime`/`unit`/`replica`/`code`. Status: `PASS`/`FAIL`/`BLOCKED`/`NOT_RUN`.

Targets: VPS1 `160.191.242.198` (edge + canonical GO `/opt/go`, `127.0.0.1:8877`); phone OPPO PKC110.

| Gate | Class | Status | Evidence |
|---|---|---|---|
| B1 VPS1 GO: process + `/healthz` | REQUIRED | **PASS** (runtime) | active; `/healthz` 200 |
| B1 `/v1/status` auth + no-token | REQUIRED | **PASS** (runtime) | Bearer 200; no token 401 |
| B5-a canonical deny/fail-closed + ledger | REQUIRED | **PASS** (runtime) | DENY + production ledger |
| B5-b DENY E2E | REQUIRED | **PASS** (runtime) | `AUTHORITY_PROVENANCE_MISSING` DENIED |
| **B5-b ALLOW E2E** | REQUIRED | **PASS (runtime)** | external root provisioned; `vps1.edge.health` → **COMPLETED** + witness + ledger `STARTED→COMPLETED` + idempotency (`tests/OUTPUT_b5b_allow_pass.txt`) |
| TLS valid + renewal | REQUIRED | **PASS** (runtime) | `notAfter 2026-10-17`; `certbot-renew.timer` active |
| Evidence/manifest/SHA | REQUIRED | **PASS** | `MANIFEST.sha256` |
| **B2 tunnel (single/stable, `queue=0`, gate 200)** | REQUIRED | **FAIL (regressed 2026-10-10T11:46Z)** | runit restarted; manual supervisor gone → no `health-tunnel.py`; edge `queue=1`; gate `000` (`tests/OUTPUT_regression_20261010T1146.txt`) |
| B5-a phone toolplane hash-chain | CONDITIONAL | BLOCKED | needs Termux |
| B1 phone-local GO | OUT_OF_SCOPE | n/a | `go_health` targets VPS1 |
| B4 ChatGPT Action | OUT_OF_SCOPE | n/a | owner decision |

## Final status: **INCOMPLETE**

**New this run:** B5-b ALLOW **PASS** (real runtime) — the last REQUIRED governance blocker is
closed with a valid external `EXTERNAL_FILE` authority, `COMPLETED`, witness and
`STARTED→COMPLETED` ledger.

**Regression:** B2 tunnel is currently **FAIL** — the supervisor was a manual `nohup` process and
did not survive a Termux/runit restart; it is not a managed service. The patched tunnel file is
intact on `/sdcard`. Restoring B2 (owner Termux action) is the only remaining REQUIRED item.

`PHASE2_COMPLETED = FALSE` (B2 REQUIRED currently failing). `ANDROID_HANDOVER_COMPLETED = TRUE`.
