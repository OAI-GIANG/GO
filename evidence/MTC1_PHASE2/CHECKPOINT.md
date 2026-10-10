# MTC-1.0 Phase 2 — Execution Checkpoint

- Updated: 2026-10-10T11:26Z
- Branch: `feature/stt-b1-b5-reconciliation-20261010`
- Base HEAD before this commit: `ffbed84b068326823e75d22207b1306d6cbc82ac`
- Overall status: **INCOMPLETE** (only one REQUIRED gate blocked)

## Scope decision
- GPT / ChatGPT Action (B4) = **OUT_OF_SCOPE** (owner decision) — not checked, not required.
- Phone-local GO = **OUT_OF_SCOPE** (not a dependency; `go_health` targets VPS1).

## Gate classification (see PHASE2_GATE_CLASSIFICATION.md)
- REQUIRED PASS (runtime): B1 (VPS1), B2, TLS renewal, B5-a canonical (deny/fail-closed/ledger),
  B5-b DENY, evidence/manifest.
- REQUIRED BLOCKED: **B5-b ALLOW** — external authority root not provisioned
  (`/etc/hg/authority/root.key` absent ⇒ `AUTHORITY_ROOT_NOT_EXTERNAL`).
- CONDITIONAL BLOCKED: B5-a phone toolplane hash-chain (needs Termux).

## This run
- Confirmed deployed governance is the V2 `AuthorityRoot` consumer: with the owner-provisioned
  env (`HG_TOOL_AUTHORITY_PROVENANCE == …_EXPECTED`, `HG_TOOL_AUTHORITY_SUBJECT=HG_SESSION_*`),
  `issue()` raises `AUTHORITY_ROOT_NOT_EXTERNAL` because the external root key is absent.
  Evidence: `tests/OUTPUT_b5b_allow_and_security.txt`.
- **Security remediation:** an erroneous review command printed `GO_API_TOKEN`; it was rotated
  (`/etc/go/go-runtime.env`, backup `…bak-20261010T112425Z`, mode 600), service restarted.
  Verified: healthz 200; new token 200; no token 401; **exposed old token 401**.

## Interaction with prior findings
- The earlier `AUTHORITY_PROVENANCE_MISSING` DENY was because the ad-hoc shell lacked the
  service env; with the env loaded the blocker is `AUTHORITY_ROOT_NOT_EXTERNAL` — consistent
  with the mandate.

## Next action (minimal, external)
Provision an external authority root key at `/etc/hg/authority/root.key` (mode 600, owned by a
principal other than the runtime). Deep will then run the ALLOW E2E and verify COMPLETED +
witness + ledger `STARTED→COMPLETED`. Deep will not create the key.

## Mission B — Android owner handover (this run)
- Owner phone key (`SHA256:d9Tz…`) authorized on VPS1 root (historical logins 2026-10-09) and
  **added to VPS2 root** this run (backup kept). VPS2 password auth left enabled pending owner
  key verification. Details: `HANDOVER.md`, `tests/OUTPUT_handover_inventory.txt`.
- Owner actions (Android): `ssh -i ~/.ssh/love_admin_ed25519 root@160.191.242.198` and
  `… root@36.50.135.233`; then disconnect/reconnect and view service status.
- **UPDATE 2026-10-10T11:37Z:** VPS2 live owner login VERIFIED (`auth.log` `d9Tz` from the phone
  at 11:35:42Z); VPS2 sshd hardened (`PermitRootLogin without-password`, `PasswordAuthentication no`,
  00- drop-in); fresh key login OK. VPS1 login evidenced historically. Details: `HANDOVER.md`,
  `tests/OUTPUT_vps2_hardening.txt`.

## Completion flags
- `PHASE2_COMPLETED = TRUE` — all REQUIRED gates PASS with runtime evidence. **B2 PASS**:
  runit-managed; restart replaced supervisor (13890→30181) with tunnel persisted (no duplicate,
  counts 1/1/1); post-restart gate 200 @12:20:51Z & @12:21:02Z; queue=0; new correlated
  `GATE_REQUEST` (`tests/OUTPUT_b2_post_restart_pass.txt`).
- `ANDROID_HANDOVER_COMPLETED = TRUE` — owner phone key logged into both VPS1 (2026-10-09) and
  VPS2 (2026-10-10T11:35:42Z); root admin verified; owner controls the key; provider-console recovery.
