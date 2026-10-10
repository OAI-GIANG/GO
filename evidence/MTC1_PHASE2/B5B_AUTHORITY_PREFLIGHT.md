# B5-b Authority Preflight (read-only) — VPS1 — 2026-10-10T11:4xZ

Purpose: determine whether the owner can safely provision the external authority root and
unblock B5-b ALLOW. **Deep ran no provisioning and changed no runtime state.**

Helper audited: `/root/OWNER_PROVISION_AUTHORITY.sh` (root:root, mode 700,
sha256 `c79f622b83cda3c9f58e79555f2bc5b7c53864b5ed19b3f7449f665ae4a5ea78`).

## 1. How the runtime determines "external authority" (deployed code, verbatim behaviour)
`/opt/go/runtime/go_runtime/core/authority.py` (V2, single root):
- `AuthorityRoot._load()`: reads `HG_AUTHORITY_ROOT_KEY_FILE` (default `/etc/hg/authority/root.key`)
  **as bytes**; if the file is readable and `strip()` is non-empty → constructs the root with that
  secret and sets `_provenance = "EXTERNAL_FILE"`; otherwise `_provenance = "SELF_PROVISIONED"`.
- `AuthorityRoot.issue()` → `_require_external()`: raises `AUTHORITY_ROOT_NOT_EXTERNAL` when
  provenance ∈ {`SELF_PROVISIONED`, `EPHEMERAL`}. So a file **is** the switch — but see §3.
- `verify()`: HMAC-SHA256 signature, in-memory `_revoked` set, expiry, action/audience/scope-subset.

`ToolGovernance._authority()` (deployed):
- requires `HG_TOOL_AUTHORITY_PROVENANCE == HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED` and
  `HG_TOOL_AUTHORITY_SUBJECT` starting `HG_SESSION_`; then `root.issue(...)` + `root.verify(...)`,
  returning an `Authority` bound to `tool:<name>` / `task_id`.
- `Kernel.authorize()` → `Authority.permits()` (status ACTIVE, matching subject/action/scope/context,
  time window, non-empty provenance); `Kernel.execute_external()` (fresh auth, subject/action/scope
  match, non-empty `result_witness`, not reused). With a valid authority the read-only tool
  `vps1.edge.health` dispatches → 200 → `COMPLETED` + witness.

**Important (not "file is enough"):** `AuthorityRoot` is a **process singleton**; the running
`go-runtime` has already instantiated it as `SELF_PROVISIONED`. Creating the file alone does **not**
change the live root — a **service restart is required** to re-run `_load()`.

## 2. Prerequisite status (measured; no secret values printed)
| Prerequisite | Status | Notes |
|---|---|---|
| `HG_TOOL_AUTHORITY_PROVENANCE` == `…_EXPECTED` | **yes** | booleans only: `provenance_match=yes` |
| `HG_TOOL_AUTHORITY_SUBJECT` prefix `HG_SESSION_` | **yes** | `subject_prefix_ok=yes` |
| `HG_AUTHORITY_ROOT_KEY_FILE` set | no | not set → default path used |
| `/etc/hg/authority/root.key` | **absent** | **the only missing item** |
| `HG_AUTHORITY_REVOCATION_FILE` | **not required** | deployed `authority.py` has **no revocation-file support** (in-memory only) |
| trusted approval issuers / `approval.py` | **not required here** | `approval.py` absent; only destructive tools need it; `vps1.edge.health` is read-only |
| scoped token file (`HG_TOOL_AUTHORITY_TOKEN_FILE`) | **not required** | this build mints the token internally from the env provenance |
| `governance_source.py` / `verify_governance_source` | not used | absent on VPS1; not referenced by the deployed code |
| service imports (`authority`, `tool_governance`) | OK | imports succeed; python 3.12.3 |

## 3. Restart impact / persistence / backup / rollback
- Restart: `systemctl restart go-runtime` (unit `Restart=always`, `RestartSec=2s`). Downtime ~1–2 s
  for `127.0.0.1:8877` (`/healthz`, `/v1/status`). Edge (nginx), ops-agent, and the phone
  health-tunnel are unaffected.
- Persistence: runtime state is in `/var/lib/go/go_runtime.sqlite3` (durable); a restart does not
  lose state. The authority root is intentionally in-process and re-derived from the key file.
- Backup: there is **no existing `root.key`** to overwrite; the helper refuses to overwrite if one
  appears (`[ -s "$D/root.key" ]` ⇒ exits 0).
- Rollback (trivial, no data loss): `rm -f /etc/hg/authority/root.key && systemctl restart go-runtime`
  → back to `SELF_PROVISIONED` (DENY again).

## 4. Conclusion: **SAFE_FOR_OWNER_PROVISION**

The only missing prerequisite is the external root key; the helper creates it `mode 600` under
`/etc/hg/authority/` (owner-owned, external to the runtime process) and restarts the service.
No other REQUIRED prerequisite is unmet for the read-only tool.

**Exact owner command (run as root on VPS1, from the owner's session):**
```sh
bash /root/OWNER_PROVISION_AUTHORITY.sh
```

After it reports `provisioned` + `go-runtime: active`, Deep runs the ALLOW E2E on the real runtime
and verifies `COMPLETED`, witness, ledger `STARTED → COMPLETED`, and idempotency.

Minor optional hardening of the helper (not required): generate the key as hex to avoid the
`bytes.strip()` edge case, e.g. `openssl rand -hex 32 > "$D/root.key"` instead of
`head -c 32 /dev/urandom` (32 random bytes already work: non-empty ⇒ `EXTERNAL_FILE`).

## 5. Guardrails honoured
- Deep did not run the helper, did not create any authority root, and changed no runtime state.
- `PHASE2_COMPLETED` remains **FALSE** until B5-b ALLOW is verified with runtime evidence.
