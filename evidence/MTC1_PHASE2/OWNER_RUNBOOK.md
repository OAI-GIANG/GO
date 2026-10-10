# Owner Runbook — exact minimal actions to unblock (MTC-1.0 Phase 2)

Each item states: **who**, **what (minimal)**, **why Deep cannot**, and **what Deep will run
immediately after** to produce runtime evidence.

---

## 1. B2 — restore tunnel supervision (who: owner, in Termux)

Deep cannot reach Termux private storage: `sshd:8022` is closed and `adb` has no
`run-as`/`RUN_COMMAND` (Android UID isolation — not to be bypassed).

Minimal steps (Termux):
```sh
# 1) back up the current supervisor, then drop in the hardened one
cp "$HOME/.../health-tunnel-supervisor.sh" "$HOME/health-tunnel-supervisor.sh.bak-$(date -u +%Y%m%dT%H%M%SZ)"
# copy the hardened file from /sdcard (contents in evidence/MTC1_PHASE2/patch/), or apply the patch:
#   patch -p1 < health-tunnel-supervisor.patch
# 2) ensure config exists (data-only; token mode 600)
#    ~/.config/hg/edge.conf :  HG_EDGE_URL=https://160.191.242.198
#                              HG_EDGE_DEVICE=phone-primary-u0_a460
#    ~/.config/hg/edge_token : <the 64-byte HG_EDGE_TOKEN>, chmod 600
# 3) restart the supervisor
pkill -f health-tunnel-supervisor.sh; nohup bash "$HOME/health-tunnel-supervisor.sh" >> "$HOME/health-tunnel.log" 2>&1 &
```
Expected: exactly one `health-tunnel.py`, no restart flap, log shows `tunnel alive`.

Deep will then verify: `ps` (1 tunnel), `/sdcard/hg-tunnel-evidence.jsonl` gains
`GATE_REQUEST status=200`, `/edge/tunnel/status` queue=0.

## 2. B1 — bring up the GO runtime (who: owner, in Termux)

Observed: `sv up go-runtime` fails with `unable to open supervise/ok` (runsvdir not running).
Precise fix — use the no-runit launcher:
```sh
cd "$HOME/HG-GO-DEPLOY"        # or wherever the kit is on the phone
bash run-go-nohup.sh
```
(Requires `~/go` from `go_materialize.py` and `~/.config/hg/go.env` with `GO_API_TOKEN`,
mode 600.) Expected: `GET http://127.0.0.1:8877/healthz` OK and `/v1/status` (auth) OK.

Alternatively, enable Termux service supervision so `sv up` works:
`pkg install termux-services` then restart, and re-run `deploy-go-service.sh`.

Deep will then verify: `go_health` via the toolplane (`vps_exec→127.0.0.1:8877`), liveness +
authenticated status, and capture raw output/hash/exit code.

## 3. B5-a — tool-layer runtime deny + phone audit (who: owner opens Termux)

Once `sshd:8022` is up (or Termux is otherwise reachable), Deep needs only read/exec access
to run the toolplane in the runtime context and read `~/.config/hg/toolplane_audit.jsonl` to
prove the deny-list and hash-chain on-device.

Deep will then run: `python3 hg_tool_plane.py selftest`; a governed deny call; `verify_audit`
over the real audit file; and capture raw output + exit code + SHA-256.

## 4. B4 — ChatGPT Action E2E (who: owner, in the GPT editor)

Per OpenAI docs (see `EXTERNAL_RESEARCH.md`):
1. GPT editor → **Actions → Create new action**.
2. Paste `HG-CONNECTOR-HEALTH-OPENAPI.yaml` (OpenAPI 3.1.0, server
   `https://160.191.242.198`, operation `hgPhoneHealth`).
3. Authentication → **API key → Bearer**; put `HG_GATE_TOKEN` in the **secret field**
   (never in chat, never in the schema/repo).
4. Ensure the workspace **action-domain allowlist** includes `160.191.242.198`.
5. Click **Test** on the action; confirm HTTP 200 and the health payload.

Deep cannot operate the editor (no ChatGPT session/credentials). Deep will verify by
checking that a real request reached the tunnel (`/sdcard/hg-tunnel-evidence.jsonl` gains a
`GATE_REQUEST` with `status=200`) and the payload matches the contract.

Note: OpenAI is retiring custom GPTs → plan a Plugins migration (`EXTERNAL_RESEARCH.md §1.2`).

## 5. B5-b ALLOW — provision canonical authority (who: external authority owner)

Not sufficient to only create `root.key`. Required (per `authority.py` + B1–B5 impl doc):
1. `HG_AUTHORITY_ROOT_KEY_FILE` (default `/etc/hg/authority/root.key`) provisioned by a
   **principal external** to the process, so provenance = `EXTERNAL_FILE`
   (else `AUTHORITY_ROOT_NOT_EXTERNAL`).
2. `HG_AUTHORITY_REVOCATION_FILE` configured (persistent revocation).
3. A **trusted approval issuer** for `TRUSTED_APPROVAL_ISSUERS` (destructive ops stay blocked
   until this trust boundary is provisioned) and/or a trusted verifier where applicable.
4. Issue a tool-scoped authority token to a file, point `HG_TOOL_AUTHORITY_TOKEN_FILE` at it.

Deep must **not** self-provision authority (governance forbids). After provisioning, Deep
will run the ALLOW E2E and verify: `state=COMPLETED`, valid witness, ledger
`STARTED → COMPLETED`, idempotency, and provenance — saving raw output, exit code and hash.

---

## Status of "cannot bypass"
- Android UID isolation: not attempted (correct).
- Deny-list / fail-closed: preserved; no default write widening.
- No fabricated external authority/provenance.
