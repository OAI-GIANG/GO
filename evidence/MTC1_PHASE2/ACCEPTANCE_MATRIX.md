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
| **B2 tunnel (single/stable, `queue=0`, gate 200)** | REQUIRED | **PASS** (runtime) | runit service `hg-health-tunnel`; restart replaced supervisor (13890→30181) with tunnel persisted (no duplicate; counts 1/1/1); post-restart gate **200** @12:20:51Z & @12:21:02Z, queue=0, new `GATE_REQUEST` correlated; negatives + Linux restart/dup E2E PASS (`tests/OUTPUT_b2_post_restart_pass.txt`) |
| B5-a phone toolplane hash-chain | CONDITIONAL | BLOCKED | needs Termux |
| B1 phone-local GO | OUT_OF_SCOPE | n/a | `go_health` targets VPS1 |
| B4 ChatGPT Action | OUT_OF_SCOPE | n/a | owner decision |

## Final status: **INCOMPLETE**

**New this run:** B5-b ALLOW **PASS** (real runtime) — the last REQUIRED governance blocker is
closed with a valid external `EXTERNAL_FILE` authority, `COMPLETED`, witness and
`STARTED→COMPLETED` ledger.

## Final status: **COMPLETED**

All REQUIRED gates PASS with runtime evidence: B1 (VPS1 GO liveness/auth), **B2** (runit-managed
tunnel, post-restart HTTP 200, queue=0/pending=0, correlated `GATE_REQUEST`, no duplicate), TLS
(renewed + timer), B5-a canonical fail-closed + ledger, B5-b DENY, **B5-b ALLOW** (external
authority; COMPLETED + witness + ledger), and evidence/manifest. OUT_OF_SCOPE: GPT Action,
phone-local GO.

`PHASE2_COMPLETED = TRUE`. `ANDROID_HANDOVER_COMPLETED = TRUE`.
