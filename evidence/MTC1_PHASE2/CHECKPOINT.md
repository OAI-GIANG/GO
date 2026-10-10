# MTC-1.0 Phase 2 — Execution Checkpoint

- Updated: 2026-10-10T11:15Z
- Branch: `feature/stt-b1-b5-reconciliation-20261010`
- Base HEAD before this commit: `d3b56bff5fe62d7fb594b89260067490af52c7cc`
- Overall status: **INCOMPLETE**

## OBJECTIVE
Close the remaining mandatory acceptance gates of HG MTC-1.0 Phase 2 with implementation,
runtime verification, E2E tests and independently checkable evidence.

## RESULTS (this run — real fixes, not plans)
- **B2 PASS (runtime).** Root cause: supervisor spawned `python3 /sdcard/HG-GO-DEPLOY/
  health-tunnel.py` **without `--apply`** and without `HG_EDGE_*`, so the tunnel printed
  `DRY_RUN_OK` and exited → restart loop → edge `GATE_TIMEOUT 504`. Fix: replaced that file
  with a self-configuring, apply-by-default build (backup `health-tunnel.py.bak-20261010T110939Z`).
  Result: single tunnel `pid 2773` stable (4 samples/30s), edge `queue=0`, gate round-trip 200,
  phone evidence `GATE_REQUEST status:200 @11:10:53Z`.
- **B4 server-side PASS + TLS renewal.** Gate Bearer → HTTP 200 (`HG_TUNNEL_HEALTH`, py 3.14.6,
  aarch64) with device-side evidence; no token → 401. TLS renewed (2026-10-13 → **2026-10-17**)
  after adding the ACME webroot location (nginx backup `hg-edge.bak-20261010T110157Z`);
  `certbot-renew.timer` enabled (twice daily). Remaining B4: ChatGPT editor import (owner).
- **B1 PASS (runtime, VPS1)** and **B5-b DENY PASS (runtime, VPS1)** retained.

## ACCESS
- root SSH → VPS1 (`vps-hjcscw`) works.
- `adb` read-only **+ write to `/sdcard`** works (used to fix the tunnel artifact live).
- Termux shell NOT available: `sshd:8022` closed; `RUN_COMMAND` denies the shell uid (verified).
- VPS2 not reachable with available keys.

## REMAINING (blocked, exact owner action in OWNER_RUNBOOK.md)
- **B4 UI import** (ChatGPT editor + Bearer secret + domain allowlist) — owner.
- **B5-b ALLOW** — external authority root/issuers absent (`/etc/hg/authority/` missing).
- **B5-a phone audit runtime** — needs Termux (toolplane audit is private).
- **phone-local GO** — crash-loop (missing governance source); not required for B1.

## RISKS
- The deployed tunnel patch self-configures/apply-defaults; prefer also installing the
  hardened supervisor so behavior is explicit in the canonical file.
- Verify no duplicate tunnel if the supervisor is later changed.

## NEXT ACTION
1. Owner (ChatGPT): import the OpenAPI, set Bearer secret, allowlist domain, run Test → 200.
2. External authority: provision root + revocation + approval issuers → Deep runs ALLOW E2E.
3. If phone GO is required: redeploy `~/go` including `control/` governance files.
