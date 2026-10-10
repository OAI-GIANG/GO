# MTC-1.0 — Phase 2 Closure Record

Recorded by: STT (accepting Deep's reported results). **STT did not independently access runtime
artifacts**; this record transcribes Deep's reported runtime evidence and the evidence committed
on the working branch. Deep (acting execution agent) holds the runtime evidence.

- Recorded at: 2026-10-10T12:2xZ
- Branch: `feature/stt-b1-b5-reconciliation-20261010`
- Remote HEAD at time of record (before this record's commit): `15f270e0b8fce7a617235c79c71cdcfa255c5d79`
- Status flags: **`PHASE2_COMPLETED = TRUE`**, **`ANDROID_HANDOVER_COMPLETED = TRUE`**, **`B2 = PASS`**

## Gate summary (REQUIRED)
| Gate | Status | Evidence (path) |
|---|---|---|
| B1 — VPS1 GO liveness + authenticated 200/401 | PASS (runtime) | `tests/OUTPUT_vps1_runtime.txt`, `tests/OUTPUT_final_state.txt` |
| B2 — tunnel + post-restart authenticated E2E | PASS (runtime) | `tests/OUTPUT_b2_post_restart_pass.txt`, `tests/OUTPUT_b2_runtime_verified.txt` |
| TLS — valid cert + renewal timer | PASS (runtime) | `tests/vps1_fix_acme.sh`, `tests/vps1_cert_timer.sh` |
| B5-a — canonical fail-closed + ledger | PASS (runtime) | `tests/OUTPUT_vps1_runtime.txt` |
| B5-b DENY | PASS (runtime) | `tests/OUTPUT_vps1_runtime.txt` |
| B5-b ALLOW — COMPLETED + witness + ledger | PASS (runtime) | `tests/OUTPUT_b5b_allow_pass.txt` |
| Evidence / manifest / SHA-256 | PASS | `MANIFEST.sha256` |
| GPT Action; phone-local GO | OUT_OF_SCOPE | owner decision |

## B2 evidence (exact, as reported by Deep)
- Restart event: runsv `hg-health-tunnel`=13889; supervisor changed **13890 → 30181**; tunnel
  **14085 persisted (PPid 1)**; counts after restart **tunnel=1, supervisor=1, runsv=1** (no duplicate).
- Fresh authenticated requests (VPS1; Bearer token never printed):
  - `#1` 2026-10-10T12:20:51Z → **HTTP 200**; device `GATE_REQUEST`
    `request_id=r_c1cd7223ee1d84eb`, timestamp 12:20:51Z, status 200.
  - `#2` 2026-10-10T12:21:02Z → **HTTP 200**; device `GATE_REQUEST`
    `request_id=r_446ba1aa1e7271e3`, timestamp 12:21:02Z, status 200.
- Edge `…/edge/tunnel/status?device_id=phone-primary-u0_a460` → `queue=0, pending=0` (both times).
- Correlation: edge response `at` == device `GATE_REQUEST` `at` (12:20:51Z, 12:21:02Z); the earlier
  11:56:37Z result was **not** used as the pass evidence.
- Artifact/build identity: tunnel `/sdcard/HG-GO-DEPLOY/health-tunnel.py` sha256
  `790de550ced4cb75a2445c4a07f6bca6e18f0dec579fbc4d0683fbfd675e6889`; repo commit provenance
  `ad6fe947… → 15f270e0…`.
- Verification class: **PRODUCTION_RUNTIME_PASS** (VPS1 edge + Android/Termux device), with
  supporting isolated tests (`tests/test_supervisor_e2e_linux.sh`, `tests/tunnel_negative.py`).

## Scope limitations — explicitly NOT demonstrated by this test
- **Demonstrated:** supervisor/service restart recovery — the runit service's `run` script
  (supervisor) was replaced (13890→30181), the existing tunnel survived, no duplicate was created,
  and authenticated E2E returned 200 afterward.
- **NOT demonstrated:** (a) **tunnel-crash recovery** (the tunnel process itself being killed and
  re-spawned by the supervisor) was not induced; (b) **full Termux/runsvdir restart or full-device
  reboot** recovery was not performed as part of this verification.
- Therefore these two recovery modes remain unverified; they are not claimed.

## Governance constraints honored (record)
- No merge to `main`.
- External authority not reprovisioned/altered: `/etc/hg/authority/root.key` unchanged
  (mode 600, size 32; provenance `EXTERNAL_FILE`); B5-b ALLOW not re-run.
- No secrets printed or committed.
- Historical evidence preserved (append-only additions; no overwrite).
- STT did not access runtime artifacts; STT records Deep's reported results.
