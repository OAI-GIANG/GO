# MTC-1.0 Phase 2 — Execution Checkpoint

- Updated: 2026-10-10T10:37Z
- Branch: `feature/stt-b1-b5-reconciliation-20261010`
- Base HEAD (before this commit): `05423bc6c18ec7287b631a4c1b17af775837f1f2`
- Remote: `github.com/OAI-GIANG/GO`
- Overall status: **INCOMPLETE**

## OBJECTIVE
Close the remaining mandatory acceptance gates of HG MTC-1.0 Phase 2 with
implementation, runtime verification, E2E tests and independently checkable evidence.

## SCOPE
- Allowed branch only. No merge, no `main`, no `hg-core` change, no production mutation.
- Device access held: `adb` read-only (+ loopback `adb forward`), VPS1 edge HTTPS read.

## INPUT (measured this run, 2026-10-10T10:36Z)
- runit running: `runsvdir` pid 9688 + `runsv go-runtime` (9694), `runsv hg-runtime`,
  `hg-backend`, `sshd`, `cloudflared`, `og-runtime`, `ssh-agent`.
- **GO on phone: crash/restart loop** — server lives <~2s (pid `30217` seen once, then
  gone), **no `127.0.0.1:8877` listener**. `runsv go-runtime` restarts it.
- Legacy HG `/api/health` on `127.0.0.1:8787` → 200 `READY / HG_LOCAL / phone_bridge V2`.
- health-tunnel: **no process**; supervisor `10459` running; last `GATE_REQUEST` 00:38:59Z.
- `sshd:8022` **closed**; Termux private storage not reachable via adb.
- Edge TLS: valid Let's Encrypt cert, IP SAN `160.191.242.198`, expires **2026-10-13**.

## OUTPUT (this run)
- New evidence: `tests/OUTPUT_runtime_evidence.txt`, `tests/OUTPUT_go_replica_boot.txt`,
  `tests/OUTPUT_b5b_allow_replica.txt`.
- New test: `tests/test_b5b_allow_replica.py` → **11/11 PASS** (DENY paths + full ALLOW
  mechanics + idempotency).
- Updated `OWNER_RUNBOOK.md` (preflight/backup/rollback/stop; GO service fix via runit;
  nohup flagged as a canonical deviation).

## ACCEPTANCE CRITERIA
See `ACCEPTANCE_MATRIX.md`. Runtime PASS requires device/edge evidence; replica ≠ runtime.

## EVIDENCE
- This directory + `MANIFEST.sha256`; phone evidence under `/sdcard/*.txt` (referenced).

## RISKS
- Edge cert expires 2026-10-13 (renewal required for B4 continuity).
- GO crash loop root cause needs `$PREFIX/var/log/sv/go-runtime/current` (owner read).
- Custom GPT Actions deprecating → B4 time-bounded; prefer Plugins migration.

## STOP CONDITION
Stop only when all mandatory gates PASS, or each blocker is objectively outside current
tools/rights with a precise unlock action. No fabricated PASS.

## NEXT ACTION
1. Owner: `tail -n 60 "$PREFIX/var/log/sv/go-runtime/current"`, fix `~/go`/`go.env`, then
   `sv down/up go-runtime` (one attempt; return logs on failure).
2. Owner: install hardened supervisor + restore tunnel (B2).
3. Owner: B4 import + Bearer secret + domain allowlist.
4. External owner: provision authority root/revocation/issuers/token (B5-b ALLOW).
5. Deep (when `sshd:8022` opens or loopback GO is up): run B1/B2/B5-a runtime verification;
   then B5-b DENY; then ALLOW.
