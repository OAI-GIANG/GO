# MTC-1.0 Phase 2 — Acceptance Matrix (GPT removed)

**Owner decision:** GPT / ChatGPT Action (old "B4") is **OUT_OF_SCOPE** — excluded from
acceptance and from the completion condition. No GPT action is required or requested.

Legend — Class: **REQUIRED / CONDITIONAL / OUT_OF_SCOPE**. Evidence: `runtime`/`unit`/`replica`/`code`.
Status: `PASS`/`FAIL`/`BLOCKED`/`NOT_RUN`. Full classification & closure conditions:
`PHASE2_GATE_CLASSIFICATION.md`.

Targets: VPS1 `160.191.242.198` (`vps-hjcscw`) = edge + canonical GO runtime (`/opt/go`,
systemd `go-runtime`, `127.0.0.1:8877`). Phone OPPO PKC110 = HG legacy runtime + toolplane.

---

| Gate | Class | Status | Evidence |
|---|---|---|---|
| B1 `go_health`: VPS1 GO process + listener | REQUIRED | **PASS** (runtime) | `go-runtime` active; `127.0.0.1:8877` |
| B1 `/healthz` contract | REQUIRED | **PASS** (runtime) | `{"status":"ok","version":"0.1.1"}` |
| B1 `/v1/status` authenticated | REQUIRED | **PASS** (runtime) | Bearer 200 (production, 28 ops); no token 401 |
| B1 identity | REQUIRED | **PASS** (runtime) | `GO_COMMIT=d635e883…` |
| B2 supervisor (phone) | REQUIRED | **PASS** (runtime) | pid `10459` running |
| B2 tunnel single/stable | REQUIRED | **PASS** (runtime) | pid `2773` stable 4×/30s |
| B2 `edge queue=0` | REQUIRED | **PASS** (runtime) | `/edge/tunnel/status` queue=0 |
| B2 `GATE_REQUEST 200` (device evidence) | REQUIRED | **PASS** (runtime) | gate 200; phone `GATE_REQUEST status:200` |
| TLS valid + renewal | REQUIRED | **PASS** (runtime) | cert `notAfter 2026-10-17`; `certbot-renew.timer` active |
| B5-a deny-list (tool layer) | REQUIRED | **PASS** (unit) | governance negative 13/13 |
| B5-a canonical fail-closed / DENY on runtime | REQUIRED | **PASS** (runtime) | VPS1 `ToolGovernance` DENY; production ledger DENIED |
| B5-a audit ledger present (canonical) | REQUIRED | **PASS** (runtime) | `/opt/go/data/tool-events.jsonl` (1733 lines) |
| B5-a phone toolplane hash-chain audit | CONDITIONAL | **BLOCKED** | phone audit Termux-private |
| B5-b DENY E2E | REQUIRED | **PASS** (runtime) | ledger `…→AUTHORIZATION_PENDING→DENIED` |
| B5-b ALLOW E2E | REQUIRED | **BLOCKED** | `AUTHORITY_ROOT_NOT_EXTERNAL`; no `/etc/hg/authority/root.key` |
| Evidence / manifest / SHA-256 | REQUIRED | **PASS** | `MANIFEST.sha256` (LF clean-clone verified) |
| B1 phone-local GO | OUT_OF_SCOPE | n/a | not a dependency (`go_health` targets VPS1) |
| B4 ChatGPT Action | OUT_OF_SCOPE | n/a | owner decision |

---

## Final status: **INCOMPLETE**

Every REQUIRED gate is **PASS with runtime evidence** except **B5-b ALLOW**, which is
**BLOCKED** pending an **externally provisioned authority root key** (owner/authority action).
CONDITIONAL B5-a phone audit is blocked on Termux. OUT_OF_SCOPE: GPT Action, phone-local GO.
See `PHASE2_GATE_CLASSIFICATION.md` §4 for the minimal unlock action.
