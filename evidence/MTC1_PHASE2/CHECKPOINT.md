# MTC-1.0 Phase 2 — Execution Checkpoint

- Updated: 2026-10-10T10:50Z
- Branch: `feature/stt-b1-b5-reconciliation-20261010`
- Base HEAD before this commit: `4316ed155f60018fe3f2790313a22cb6a2dd3769`
- Overall status: **INCOMPLETE**

## OBJECTIVE
Close the remaining mandatory acceptance gates of HG MTC-1.0 Phase 2 with implementation,
runtime verification, E2E tests and independently checkable evidence.

## SCOPE / ACCESS (measured this run)
- Workstation → **root SSH to VPS1** `160.191.242.198` (`vps-hjcscw`) works (key
  `love_admin_ed25519`). This is the canonical deployment host for `go_health` and B5-b.
- Phone: `adb` read-only **+ `adb` can write `/sdcard`**; `sshd:8022` still closed; Termux
  private storage not reachable. VPS2 `36.50.135.233` not reachable with available keys.

## RESULTS (this run)
- **B1 PASS (runtime, VPS1):** `go-runtime` active; listener `127.0.0.1:8877`; `/healthz`
  `{"status":"ok"}`; `/v1/status` Bearer **200** (production, 28 ops); no token **401**;
  `GO_COMMIT=d635e883…`.
- **B5-b DENY PASS (runtime, VPS1):** `ToolGovernance.execute(vps1.edge.health)` →
  `AUTHORITY_PROVENANCE_MISSING` DENIED; production ledger `/opt/go/data/tool-events.jsonl`
  (1733 lines) contains real phone-originated DENIED events.
- **B2 FAIL (runtime):** edge `/edge/tunnel/status` → `queue=3, pending=0`;
  `hg-edge` logs `GATE_TIMEOUT 504`; no `health-tunnel.py` process on the phone.
- **B4:** TLS valid (Let's Encrypt, IP SAN, `notAfter=2026-10-13T01:54Z`) but **no renewal
  configured** (certbot absent, no timer); gate auth enforced (401 no token); E2E 200 blocked
  by the tunnel (+ UI).
- **B5-b ALLOW BLOCKED (runtime):** `/etc/hg/authority/` absent (no `root.key`); authority env
  empty; `TRUSTED_APPROVAL_ISSUERS` empty. Must be provisioned by the external owner.
- Phone GO (separate local deploy) still crash-loops; root-caused (missing governance source).

## EVIDENCE
- `tests/OUTPUT_vps1_runtime.txt` (raw VPS1 captures), `tests/vps1_*_verify.sh` (scripts),
  plus prior `tests/OUTPUT_*`.

## RISKS
- Edge cert expires 2026-10-13 with no auto-renewal → B4 continuity risk (owner w/ authority).
- Phone tunnel not draining → B2/B4 blocked.
- Newer B1–B5 token-file authority design is NOT deployed on VPS1 (older env-provenance) —
  reconcile before claiming B5-b on the newer contract.

## STOP CONDITION
All mandatory gates PASS, or each remaining blocker objectively outside current rights with a
precise unlock action. No fabricated PASS.

## NEXT ACTION
1. Owner (Termux): fix phone GO (redeploy `~/go` with governance files) **and** restore the
   tunnel (hardened supervisor + edge config) → then Deep verifies B2/B5-a runtime.
2. Owner (authority): renew the edge certificate (install certbot/acme + timer) before 2026-10-13.
3. Owner (authority): provision external authority root + approvers → then Deep runs ALLOW E2E.
4. Owner (ChatGPT): import the action + Bearer secret + domain allowlist → Deep verifies 200.
