# MTC-1.0 Phase 2 — Gate Classification & Closure Conditions

Owner decision applied: **GPT / ChatGPT Action (B4) = OUT_OF_SCOPE**. It is excluded from
acceptance and from the completion condition. No GPT work is requested below.

Evidence classes: `runtime` (real host/device), `unit`, `replica`, `code`.
Raw captures: `tests/OUTPUT_*.txt`.

## 1. Gate classification

| Gate | Class | Status | Evidence |
|---|---|---|---|
| B1 — `go_health` (VPS1 GO liveness + authenticated 200) | **REQUIRED** | **PASS** (runtime) | `/healthz` ok; `/v1/status` Bearer 200; no-token 401 (`OUTPUT_vps1_runtime.txt`) |
| B2 — tunnel (single/stable, `queue=0`, `GATE_REQUEST 200`) | **REQUIRED** | **PASS** (runtime) | pid stable/30s; edge queue=0; gate 200 + device evidence (`OUTPUT_b2_b4_runtime.txt`) |
| TLS — valid cert + active renewal (edge health continuity) | **REQUIRED** | **PASS** (runtime) | cert `notAfter 2026-10-17`; `certbot-renew.timer` active |
| B5-a — deny-list + canonical fail-closed on runtime | **REQUIRED** | **PASS** (runtime) | canonical `ToolGovernance` DENY on VPS1; production ledger DENIED events |
| B5-a — phone toolplane hash-chain audit (`audit_tail`) | **CONDITIONAL** | **BLOCKED** (needs Termux) | phone audit is Termux-private; canonical runtime ledger is the runtime audit |
| B5-b DENY — canonical denial E2E | **REQUIRED** | **PASS** (runtime) | ledger `ACCEPTED→…→AUTHORIZATION_PENDING→DENIED` |
| B5-b ALLOW — authorized execution E2E | **REQUIRED** | **BLOCKED** (external authority) | `AUTHORITY_ROOT_NOT_EXTERNAL`; `/etc/hg/authority/root.key` absent |
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
   `COMPLETED` with a witness and ledger `…→STARTED→COMPLETED`. *(BLOCKED — see §4)*
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

1. **[REQUIRED, external] B5-b ALLOW provisioning.** Provision an **external** authority root
   key owned by a principal other than the runtime. On VPS1, as the owner (Deep must NOT do this):
   ```sh
   install -d -m 700 /etc/hg/authority
   umask 077; head -c 32 /dev/urandom > /etc/hg/authority/root.key
   chmod 600 /etc/hg/authority/root.key
   systemctl restart go-runtime
   ```
   `AuthorityRoot._load()` then reads the file ⇒ provenance `EXTERNAL_FILE`, so `issue()`
   succeeds and `AUTHORITY_ROOT_NOT_EXTERNAL` no longer applies. The tool-authority env in
   `/etc/go/go-runtime.env` is already set (`HG_TOOL_AUTHORITY_PROVENANCE == …_EXPECTED`,
   `HG_TOOL_AUTHORITY_SUBJECT=HG_SESSION_*`). After provisioning, Deep runs the ALLOW E2E and
   verifies COMPLETED + witness + ledger `STARTED→COMPLETED`.
2. **[CONDITIONAL] B5-a phone audit-chain.** Needs Termux access (toolplane audit file is
   private). Provide access or accept the canonical ledger as audit of record.
3. **[OPTIONAL hardening]** Install the hardened supervisor (`patch/health-tunnel-supervisor.hardened.sh`)
   so `--apply`/env are explicit in the canonical supervisor rather than relying on the tunnel
   self-config.

## 5. Final status

**INCOMPLETE** — all REQUIRED gates PASS **except B5-b ALLOW**, which is BLOCKED on external
authority provisioning (§4.1). B1/VPS1, B2, TLS, B5-a (canonical), B5-b DENY and evidence are
PASS with runtime evidence. B4/GPT and phone-local GO are OUT_OF_SCOPE.
