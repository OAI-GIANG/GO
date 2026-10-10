# Owner Runbook — exact minimal actions to unblock (MTC-1.0 Phase 2)

Access model (measured 2026-10-10T10:36Z):
- Deep holds: `adb` (read-only) on OPPO PKC110 `BIXSMFNBRCNN95T4`; VPS1 edge HTTPS (read).
- **runit IS running** on the phone: `runsvdir …/usr/var/service` (pid 9688) supervises
  `go-runtime`, `hg-runtime`, `hg-backend`, `sshd`, `cloudflared`, `og-runtime`, `ssh-agent`.
- `sshd:8022` is **closed**; `adb` cannot read/write Termux private storage (Android UID
  isolation — not to be bypassed). So all Termux mutations below are **owner** actions.
- Never print token values. All examples read tokens as data and print only presence/size.

Grounding: Termux services README (runit): enable with `sv-enable`/`sv up`; on failure read
`$PREFIX/var/log/sv/<service>/current`. runit `runsv(8)`: restarts after an immediate exit
(1s). Canonical `GO_RUNTIME_DEPLOYMENT_V1`: the **unit owns the GO process**.

---

## 0. Preflight (Termux, read-only, safe to paste)

```sh
set -u
echo "== tools =="; command -v sv; command -v python3; command -v curl
echo "== service supervision =="; sv status go-runtime; sv status hg-runtime
echo "== GO tree =="; test -d "$HOME/go/runtime/go_runtime/core" && echo GO_TREE_OK || echo GO_TREE_MISSING
echo "== GO env (presence only, no values) =="
if [ -f "$HOME/.config/hg/go.env" ]; then
  stat -c 'go.env mode=%a' "$HOME/.config/hg/go.env"
  echo "GO_API_TOKEN_present=$(grep -c '^GO_API_TOKEN=' "$HOME/.config/hg/go.env")"
else echo "go.env MISSING"; fi
echo "== recent GO service log =="; tail -n 40 "$PREFIX/var/log/sv/go-runtime/current" 2>/dev/null
echo "== edge config presence =="
[ -f "$HOME/.config/hg/edge.conf" ] && echo edge.conf_OK || echo edge.conf_MISSING
[ -f "$HOME/.config/hg/edge_token" ] && stat -c 'edge_token mode=%a size=%s' "$HOME/.config/hg/edge_token" || echo edge_token_MISSING
```
Expected for a healthy GO: `sv status go-runtime` shows `run:` and the log shows a listening
line. **Stop criterion:** if `GO_TREE_MISSING` or `go.env MISSING`, do NOT start the service;
finish materialize/credentials first (below).

---

## 1. B1 — stop the GO crash/restart loop (who: owner, Termux)

Observed by Deep: `runsv go-runtime` exists but the server process lives <~2s and never
binds `127.0.0.1:8877` (no listener) → **crash loop**. Deep verified the entrypoint itself
is sound on a replica (see `tests/OUTPUT_go_replica_boot.txt`); the fault is environmental.

Diagnose (read-only):
```sh
tail -n 60 "$PREFIX/var/log/sv/go-runtime/current"
```
Typical causes and the minimal fix:
- **`~/go` incomplete** → re-materialize the candidate, then redeploy the service:
  ```sh
  cd ~/HG-GO-DEPLOY 2>/dev/null || cd /sdcard/HG-GO-DEPLOY
  bash preflight-go.sh            # writes ~/go-candidate, verifies against the manifest
  # then either re-run deploy-go-service.sh (creates the service and sv up), or, if ~/go exists:
  ```
- **Missing `GO_API_TOKEN`** in `~/.config/hg/go.env` (mode 600) → the runtime requires a
  token unless `GO_ALLOW_ANONYMOUS=true`; add the token (do not print it) and restart.
- **Stale/incorrect service `run`** → re-create it (from `deploy-go-service.sh` G4 template).

Restart the **service** (canonical-aligned; the unit owns the process):
```sh
sv down go-runtime 2>/dev/null; sleep 1; sv up go-runtime; sleep 3
sv status go-runtime
tail -n 40 "$PREFIX/var/log/sv/go-runtime/current"
curl -fsS -m 5 http://127.0.0.1:8877/healthz || echo HEALTHZ_FAILED
```
**Stop criterion:** if it still exits, STOP and return the last 40 log lines; do not loop.

### About `run-go-nohup.sh`
`run-go-nohup.sh` starts GO **without runit** and is a **deviation** from
`GO_RUNTIME_DEPLOYMENT_V1` ("the unit owns the GO process"). Since `runsvdir` is running,
prefer the `go-runtime` service. Use nohup only as a time-boxed fallback, and only if you
then wrap it under runsv; otherwise a second unsupervised process violates the single-owner
invariant. If used: `pgrep -f go_runtime.core.server` must show exactly **one** process.

Deep will then run (over `adb forward tcp:18877 tcp:8877`): `/healthz` (contract), and
(with the token, held on-device) `/v1/status`; capturing raw output, exit code, timing.

---

## 2. B2 — restore tunnel supervision (who: owner, Termux)

Observed: supervisor `10459` runs, but **no `health-tunnel.py`** process and no `GATE_REQUEST`
since `2026-10-10T00:38:59Z`. Root cause: the supervisor did not export `HG_EDGE_*`.

```sh
# back up, then install the hardened supervisor (contents in patch/; or apply the diff)
cp "$HOME/health-tunnel-supervisor.sh" "$HOME/health-tunnel-supervisor.sh.bak-$(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null || true
# place patch/health-tunnel-supervisor.hardened.sh in $HOME (or /sdcard) and run it, e.g.:
#   pkill -f health-tunnel-supervisor.sh
#   nohup bash "$HOME/health-tunnel-supervisor.hardened.sh" >> "$HOME/health-tunnel.log" 2>&1 &
# verify config (no token value printed)
stat -c 'edge_token mode=%a size=%s' "$HOME/.config/hg/edge_token"
```
Expected: exactly **one** `health-tunnel.py`; the log shows `tunnel alive`; no restart flap.

Deep will verify: one tunnel process; `/sdcard/hg-tunnel-evidence.jsonl` gains a
`GATE_REQUEST … "status": 200`; edge tunnel status `queue=0`.

---

## 3. B5-a — tool-layer runtime deny + phone audit (who: owner enables Termux access)

Deep cannot launch the toolplane on-device without Termux. Once reachable:
```sh
python3 ~/hg/core/runtime/toolplane/hg_tool_plane.py selftest   # must list the six tools
```
Deep will then run a governed deny call, `verify_audit()` over the real
`~/.config/hg/toolplane_audit.jsonl`, and capture raw output + exit code + SHA-256.

---

## 4. B4 — ChatGPT Action E2E (who: owner, GPT editor)

Schema facts verified: `openapi 3.1.0`, server `https://160.191.242.198`, GET
`operationId hgPhoneHealth`, bearer scheme `gateBearer`. TLS verified this run: **valid
Let's Encrypt cert, IP SAN `160.191.242.198`, expires 2026-10-13** (renew before/after).
Steps: Actions → Create new action → paste schema; Authentication → API key → **Bearer**
with `HG_GATE_TOKEN` in the **secret** field; ensure the workspace action-domain allowlist
includes `160.191.242.198`; click **Test**; expect HTTP 200. Then Deep verifies server-side:
a new `GATE_REQUEST status=200` in the tunnel evidence.
Note: OpenAI is retiring custom GPTs → plan a Plugins migration.

---

## 5. B5-b ALLOW — provision canonical authority (who: external authority owner)

Deep cannot and must not self-provision. Prerequisites (from `authority.py`, `approval.py`,
`tool_governance.py`, verified on replica):
1. `HG_AUTHORITY_ROOT_KEY_FILE` (default `/etc/hg/authority/root.key`) with an externally
   owned secret → provenance `EXTERNAL_FILE`. Without it, `AuthorityRoot.instance()`
   raises `AUTHORITY_ROOT_NOT_PROVISIONED` (fail-closed; no self-trust).
2. `HG_AUTHORITY_REVOCATION_FILE` configured (revocation persistence; else
   `AUTHORITY_REVOCATION_STORE_NOT_CONFIGURED`).
3. A trusted bootstrap **outside the runtime package** populating `TRUSTED_APPROVAL_ISSUERS`
   (destructive approvals stay blocked until then).
4. Issue a token and point `HG_TOOL_AUTHORITY_TOKEN_FILE` at it; set
   `HG_TOOL_AUTHORITY_SUBJECT=HG_SESSION_*`. Token JSON must carry:
   `token_id, subject(HG_SESSION_*), scope⊇{tool:<name>, task:<task_id>}, action=execute,
   audience=tool:<name>, issued_at, expires_at, nonce, sig` (signed by the external root).

Deep will then run the ALLOW E2E and verify `state=COMPLETED`, witness, ledger
`STARTED→COMPLETED`, idempotency and provenance — raw output, exit code and hash saved.

---

## Stop criteria (all)
- Do not start GO if the tree/credentials are missing (fix prerequisites first).
- Do not loop restarts: one attempt, then return logs.
- Do not print or paste any token/key value.
- Do not create authority or verifier identities Deep does not own.
