# MTC-1.0 Phase 2 — Execution Checkpoint

- Updated: 2026-10-10T10:35Z
- Branch: `feature/stt-b1-b5-reconciliation-20261010`
- Base HEAD (before this commit): `946163c0c03c168f17128371c1b3ed6baa67b104`
- Remote: `github.com/OAI-GIANG/GO`
- Overall status: **INCOMPLETE**

## OBJECTIVE
Close the remaining mandatory acceptance gates of HG MTC-1.0 Phase 2 with
implementation, runtime verification, E2E tests and independently checkable evidence.

## SCOPE
- Allowed: `feature/stt-b1-b5-reconciliation-20261010` only. No merge, no `main`, no
  `hg-core` change, no production mutation.
- Device access actually held: `adb` read-only on OPPO PKC110; VPS1 edge HTTPS read.
- Not held: Termux shell (`sshd:8022` closed), ChatGPT Action UI/credentials.

## INPUT (measured this run)
- Phone `BIXSMFNBRCNN95T4`, Termux user `u0_a460`, LAN `192.168.1.194`, sshd `8022` **closed**.
- Running on phone: `hg_backend.py`, `hg_runtime.py` (legacy HG). **No GO runtime.**
- Supervisor `10459` running; **no `health-tunnel.py`**; last tunnel serve `00:38:59Z`.
- `/sdcard/hg-go-deploy-result.txt`: GO deploy `FAIL: sv up thất bại`.
- VPS1: `/edge/health` 200; gate endpoint 401 without token.
- Repo `hg-core` also carries `tool_runtime.py` (26315 B) absent on phone.

## OUTPUT (this run)
- `evidence/MTC1_PHASE2/` set: acceptance matrix, research, runbook, tests, patches, manifest.
- `patch/health-tunnel-supervisor.hardened.sh` (+ `.original.sh`, unified diff): fixes B2 loop.
- `patch/hg_tool_plane.governance.patch`: closes B5-a coverage gap (default-deny side effects).
- Tests: supervisor logic `PASS 15/15`; governance negative `PASS 13/13`; regression `196 passed`.

## ACCEPTANCE CRITERIA
See `ACCEPTANCE_MATRIX.md`. Runtime PASS requires device/edge evidence.

## EVIDENCE
- This directory + `tests/OUTPUT_*.txt` (raw stdout, exit codes embedded by the harnesses).
- Device evidence files under `/sdcard/*.txt` captured via `adb` (referenced, not copied).

## RISKS
- Termux sshd down ⇒ device-side automation impossible; owner must restore.
- Custom GPT Actions deprecating (Dec 11 2026) ⇒ B4 is time-bounded; prefer Plugins migration.
- PID hygiene via `/proc/cmdline` is best-effort (PID reuse) — third-party supervision safer.

## STOP CONDITION
Stop only when all mandatory gates PASS, or each remaining blocker is objectively shown to
be outside current tools/rights with a precise unlock action. Do **not** fabricate a PASS.

## NEXT ACTION
1. Owner: apply `patch/health-tunnel-supervisor.hardened.sh` in Termux (see `OWNER_RUNBOOK.md`);
   fix GO service (`~/go` + `sv up go-runtime`).
2. Owner: import the B4 OpenAPI + set Bearer secret; allowlist domain.
3. External owner: provision authority root + trusted approval issuers (B5-b ALLOW).
4. Deep (when sshd restored): run B1/B5-a/B2 runtime verification; then B5-b DENY; then ALLOW.
