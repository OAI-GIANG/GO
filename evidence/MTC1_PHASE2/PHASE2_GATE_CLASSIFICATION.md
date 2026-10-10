# MTC-1.0 Phase 2 — Gate Classification & Closure Conditions

Owner decision applied: **GPT / ChatGPT Action (B4) = OUT_OF_SCOPE**. It is excluded from
acceptance and from the completion condition. No GPT work is requested below.

Evidence classes: `runtime` (real host/device), `unit`, `replica`, `code`.
Raw captures: `tests/OUTPUT_*.txt`.

## 1. Gate classification

| Gate | Class | Status | Evidence |
|---|---|---|---|
| B1 — `go_health` (VPS1 GO liveness + authenticated 200) | **REQUIRED** | **PASS** (runtime) | `/healthz` ok; `/v1/status` Bearer 200; no-token 401 (`OUTPUT_vps1_runtime.txt`) |
| B2 — tunnel (single/stable, `queue=0`, `GATE_REQUEST 200`) | **REQUIRED** | **PASS** (runtime) | runit service; restart → supervisor 13890→30181, tunnel persisted, counts 1/1/1 (no duplicate); post-restart gate 200 @12:20:51Z/@12:21:02Z; queue=0 (`tests/OUTPUT_b2_post_restart_pass.txt`) |
| TLS — valid cert + active renewal (edge health continuity) | **REQUIRED** | **PASS** (runtime) | cert `notAfter 2026-10-17`; `certbot-renew.timer` active |
| B5-a — deny-list + canonical fail-closed on runtime | **REQUIRED** | **PASS** (runtime) | canonical `ToolGovernance` DENY on VPS1; production ledger DENIED events |
| B5-a — phone toolplane hash-chain audit (`audit_tail`) | **CONDITIONAL** | **BLOCKED** (needs Termux) | phone audit is Termux-private; canonical runtime ledger is the runtime audit |
| B5-b DENY — canonical denial E2E | **REQUIRED** | **PASS** (runtime) | ledger `ACCEPTED→…→AUTHORIZATION_PENDING→DENIED` |
| B5-b ALLOW — authorized execution E2E | **REQUIRED** | **PASS** (runtime) | external root provisioned; `vps1.edge.health` → COMPLETED + witness + ledger `STARTED→COMPLETED` (`tests/OUTPUT_b5b_allow_pass.txt`) |
| Evidence / manifest / SHA-256 | **REQUIRED** | **PASS** | `MANIFEST.sha256` (LF clean-clone verified) |
| B1 phone-local GO | **OUT_OF_SCOPE** | n/a | `go_health` probes VPS1; no gate depends on phone GO (see §3) |
| B4 ChatGPT Action | **OUT_OF_SCOPE** | n/a | owner decision |

## 2. Precise minimal, verifiable closure conditions

Phase 2 = **COMPLETED** iff every REQUIRED gate PASS with runtime evidence:

1. **B1** VPS1: `/healthz` ok AND `/v1/status` Bearer 200 AND no-token 401. *(PASS)*
2. **B2**: exactly one tunnel process stable AND edge `queue=0` AND `GATE_REQUEST status:200` with device-side evidence. *(PASS)*
3. **TLS**: edge cert valid (not expired) AND an active renewal schedule. *(PASS)*
4. **B5-a**: canonical runtime denies unauthorized side-effect tools AND records audit (ledger). *(PASS)*
5. **B5-b DENY**: canonical runtime returns DENY for an unauthorized call. *(PASS)*
6. **B5-b ALLOW**: with an externally provisioned authority root, an authorized call returns
   `COMPLETED` with a witness and ledger `…→STARTED→COMPLETED`. *(PASS — external root provisioned
   2026-10-10; see `tests/OUTPUT_b5b_allow_pass.txt`)*
7. **Evidence/manifest**: `MANIFEST.sha256` verifies. *(PASS)*

Only item 6 is a **REQUIRED** blocker. The CONDITIONAL B5-a phone audit does not gate Phase 2
provided the canonical runtime ledger is accepted as the runtime audit of record.

## 3. B1 phone-local GO — not a dependency (recommend OUT_OF_SCOPE)

- The tool `go_health` runs (per the toolplane) `curl 127.0.0.1:8877/healthz` + authenticated
  `/v1/status` **on VPS1** via the ops-agent — i.e. the canonical GO runtime on VPS1.
- VPS1 GO is `active` and satisfies B1; the phone carries no GO-runtime role in the measured
  topology (phone = HG legacy runtime + toolplane; VPS1 = edge + GO runtime).
- Therefore the phone-local GO crash-loop does **not** affect any REQUIRED gate. Recommend
  removing phone-local GO from Phase-2 scope (it may be revisited as a separate change).

## 4. Remaining work, priority order

1. **[DONE] B5-b ALLOW.** External authority root provisioned by the owner; Deep ran the ALLOW E2E
   (COMPLETED + witness + ledger `STARTED→COMPLETED`). See `tests/OUTPUT_b5b_allow_pass.txt`.
2. **[CONDITIONAL] B5-a phone audit-chain.** Needs Termux access (toolplane audit file is
   private). Provide access or accept the canonical ledger as audit of record.
3. **[OPTIONAL hardening]** Install the hardened supervisor (`patch/health-tunnel-supervisor.hardened.sh`)
   so `--apply`/env are explicit in the canonical supervisor rather than relying on the tunnel
   self-config.

## 5. Final status

**COMPLETED.** All REQUIRED gates PASS with runtime evidence: B1/VPS1, **B2** (runit-managed;
post-restart HTTP 200; queue=0/pending=0; correlated `GATE_REQUEST`; no duplicate on restart),
TLS (renewed + timer), B5-a canonical fail-closed + ledger, B5-b DENY, **B5-b ALLOW** (external
authority; COMPLETED + witness + ledger `STARTED→COMPLETED`), and evidence/manifest. B4/GPT and
phone-local GO are OUT_OF_SCOPE.
