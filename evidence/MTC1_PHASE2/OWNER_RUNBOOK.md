# Owner Runbook — exact minimal actions to unblock (MTC-1.0 Phase 2)

Access measured 2026-10-10T10:50Z:
- Workstation → **root SSH to VPS1** `160.191.242.198` (`vps-hjcscw`) works (key
  `love_admin_ed25519`). VPS1 hosts the canonical GO runtime (`/opt/go`, systemd
  `go-runtime`, `127.0.0.1:8877`) and the edge (`hg-edge.service`).
- Phone: `adb` read-only **+ `adb` can write `/sdcard`**; `sshd:8022` closed; Termux private
  storage NOT reachable (Android UID isolation — not bypassed).
- VPS2 `36.50.135.233`: not reachable with available keys.
- Never print token/key values; read them as data.

---

## 0. Preflight (safe, read-only)

VPS1 (run over SSH as root):
```sh
systemctl is-active go-runtime; ss -ltnp | grep 8877
curl -s -m5 http://127.0.0.1:8877/healthz
T=$(grep -m1 '^GO_API_TOKEN=' /etc/go/go-runtime.env | cut -d= -f2- | tr -d '"')
curl -s -o /dev/null -w 'status HTTP %{http_code}\n' -H "Authorization: Bearer $T" http://127.0.0.1:8877/v1/status
curl -s http://127.0.0.1:8899/edge/health
```
Phone (Termux): `sv status go-runtime hg-runtime`; read
`$PREFIX/var/log/sv/go-runtime/current`; check `~/.config/hg/edge.conf` + `edge_token` (mode 600).
Stop if a prerequisite is missing — fix it before starting anything.

### B1 status (already PASS on VPS1)
GO is `active`, listener `8877`, `/healthz` → `{"status":"ok"}`, `/v1/status` (Bearer) → 200,
no token → 401; `GO_COMMIT=d635e883…`. No action needed for B1 on the canonical host.

---

## 1. Phone-local GO (only if you require a GO runtime on the phone)

Measured: `runsv go-runtime` exists but the process churns (<2s), never binds 8877.
Root cause (replica-demonstrated): `GOApplication.__init__` → `verify_governance_source()`
requires `control/MASTER_GOVERNANCE_RULESET_V1.md` (sha `cc1a8b17…`); the phone deploy
manifest has no such entry → `V1_CANONICAL_SOURCE_MISSING`. Fix = redeploy a **complete**
tree, never a placeholder:
```sh
cd ~/HG-GO-DEPLOY 2>/dev/null || cd /sdcard/HG-GO-DEPLOY
bash preflight-go.sh && bash deploy-go-service.sh   # must include control/ governance files
# then confirm the cause first:
tail -n 60 "$PREFIX/var/log/sv/go-runtime/current"
```
Do not use `run-go-nohup.sh` as a fix (uncanonical: `GO_RUNTIME_DEPLOYMENT_V1` says the unit
owns the process). One restart attempt only; return the log if it still fails.

---

## 2. B2 — tunnel recovery (phone + VPS1 verification)

Measured: edge `/edge/tunnel/status` → `queue=3, pending=0`; `hg-edge` logs `GATE_TIMEOUT 504`;
no `health-tunnel.py` process on the phone. The phone tunnel is not draining.

Install the hardened supervisor (fixes missing `HG_EDGE_*` export) in Termux:
```sh
cp "$HOME/health-tunnel-supervisor.sh" "$HOME/health-tunnel-supervisor.sh.bak-$(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null || true
# place patch/health-tunnel-supervisor.hardened.sh (from this repo) in $HOME, then:
pkill -f health-tunnel-supervisor.sh 2>/dev/null
nohup bash "$HOME/health-tunnel-supervisor.hardened.sh" >> "$HOME/health-tunnel.log" 2>&1 &
```
Verify (phone): exactly one `health-tunnel.py`; log `tunnel alive`.
Verify (VPS1, Deep/owner): `/edge/tunnel/status` shows `queue` draining toward `0`; a gate call
`/h/phone-primary-u0_a460/api/health` with the gate token returns HTTP 200; `/sdcard/
hg-tunnel-evidence.jsonl` gains a `GATE_REQUEST status=200`.

---

## 3. B4 — ChatGPT Action + TLS

Schema verified (openapi 3.1.0, GET `hgPhoneHealth`, bearer). TLS verified: valid Let's Encrypt
cert, IP SAN `160.191.242.198`, `notAfter 2026-10-13T01:54:10Z`. **Renewal is NOT configured**
(certbot absent, no timer). Owner/authority action before expiry:
- install an ACME client (e.g. `certbot`) and (re)issue via HTTP-01/webroot or DNS-01, then add
  a systemd timer/cron for `certbot renew`; **or** reissue by the same method originally used
  (per EFF certbot guide). Deep did not alter TLS.
- GPT editor: Actions → Create new action → paste the OpenAPI; Authentication → **Bearer** with
  `HG_GATE_TOKEN` in the **secret** field; ensure the workspace action-domain allowlist includes
  `160.191.242.198`; **Test** → expect HTTP 200. (Custom GPTs are deprecating → plan Plugins.)
- E2E gate requires the tunnel up (section 2). Deep verifies server-side: a new
  `GATE_REQUEST status=200`.

---

## 4. B5-a — phone toolplane runtime

Once Termux is reachable: `python3 ~/hg/core/runtime/toolplane/hg_tool_plane.py selftest`
(must list the six tools); then Deep runs a governed deny call and `verify_audit()` over
`~/.config/hg/toolplane_audit.jsonl`, capturing raw output + exit code + SHA-256.

---

## 5. B5-b ALLOW — canonical authority provisioning (external owner)

Measured on VPS1: `/etc/hg/authority/` is **absent** (no `root.key`); `/etc/go/go-runtime.env`
has empty `HG_TOOL_AUTHORITY_PROVENANCE/_SUBJECT`; the deployed VPS1 ToolGovernance is the
**env-provenance** variant (its DENY = `AUTHORITY_PROVENANCE_MISSING`, confirmed on the real
runtime and in the production ledger). The newer token-file/`AuthorityRoot` design lives only
on `feature/stt-b1-b5-…` (not deployed). Reconcile which contract is authoritative, then:
1. Provision an **external** authority root (`HG_AUTHORITY_ROOT_KEY_FILE`, default
   `/etc/hg/authority/root.key`) — provenance `EXTERNAL_FILE` (else `AUTHORITY_ROOT_NOT_PROVISIONED`).
2. Configure `HG_AUTHORITY_REVOCATION_FILE`.
3. Populate `TRUSTED_APPROVAL_ISSUERS` via trusted bootstrap outside the runtime package.
4. Issue a scoped token to `HG_TOOL_AUTHORITY_TOKEN_FILE`, set `HG_TOOL_AUTHORITY_SUBJECT=HG_SESSION_*`.

Deep will not self-provision. After provisioning, Deep runs DENY + ALLOW E2E and verifies
`COMPLETED`, witness, ledger `STARTED→COMPLETED`, and idempotency.

---

## Stop criteria (all)
- Fix prerequisites before starting; never start GO/tunnel with missing config.
- One restart attempt, then return logs — no infinite restart.
- Never print or paste tokens/keys; no secrets in chat/repo/log.
- Never create authority/verifier identities Deep does not own. No placeholder governance files.
