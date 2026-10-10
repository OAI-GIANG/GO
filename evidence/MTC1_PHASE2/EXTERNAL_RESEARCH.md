# External research — verified content and decisions (MTC-1.0 Phase 2)

Only sources actually fetched and read are listed. Quotes are from the fetched page.
"Deep inference" marks my own reasoning, not a source claim.

## 1. OpenAI — GPT Actions

### 1.1 https://developers.openai.com/api/docs/actions/getting-started
Verified content:
- A GPT Action requires an **OpenAPI schema**; the worked example uses `openapi: 3.1.0`.
- The action is defined by its `info` block, `servers.url`, `paths`, `operationId`,
  parameters and responses. ChatGPT uses `info`/descriptions to decide relevance.
- Debugging: each action has a **Test** button showing detailed input/output; the doc
  recommends testing the same call in Postman before wiring into ChatGPT.
- Authentication for actions is either **API Key** (with Bearer/Basic/custom-header) or OAuth.

Decisions affected:
- `HG-CONNECTOR-HEALTH-OPENAPI.yaml` already uses `openapi: 3.1.0`, a single `servers.url`,
  one GET `operationId: hgPhoneHealth`, and a `gateBearer` HTTP bearer scheme → structurally
  conforms. Remains **validated syntactically only**, not imported (see B4).

### 1.2 https://help.openai.com/en/articles/9442513-configuring-actions-in-gpts
Verified content:
- Actions configured in the GPT editor: **Actions → Create new action**, add a schema by
  (a) pasting, (b) importing from a URL, or (c) built-in example; the editor shows detected
  actions and validation errors.
- Authentication options: **None / API key (Basic, Bearer, custom header) / OAuth**.
- **Workspace restriction:** "Admins can allow all domains or restrict actions to approved
  domains"; if the workspace allows zero action domains, actions cannot execute. Action
  **server domains must be allowlisted**.
- **Important lifecycle note (fetched 2026-10-10):** OpenAI states it is *retiring custom
  GPTs* and recommends migrating workflows to **Plugins**; migration flow targeted from
  2026-09-17 and retirement planned for affected Enterprise workspaces **Dec 11, 2026**.
  Existing GPTs remain usable until retirement.

Decisions affected:
- B4 requires: (i) the GPT workspace action-domain allowlist must include `160.191.242.198`;
  (ii) the Bearer secret must be set in the action secret store (never in chat); (iii) because
  custom GPTs are deprecating, this Action is **time-bounded** — a Plugins migration path
  should be planned. Deep cannot perform editor/UI steps → owner action.

## 2. Service supervision — runit `runsv(8)`

### 2.1 http://smarden.org/runit/runsv.8.html  (and runit index http://smarden.org/runit/)
Verified content:
- `runsv` starts `./run`; **"If ./run or ./finish exit immediately, runsv waits a second
  before starting ./finish or restarting ./run."** → supervision includes a minimum delay
  to avoid tight restart loops.
- Status/control live under `service/supervise/` (`status`, `stat`, `pid`, `control`);
  `sv up|down|...` drives it. Starting a service whose `supervise/` state is inconsistent
  yields errors (matches the observed `unable to open supervise/ok`).

Decisions affected (B2):
- Our custom supervisor must be at least as safe as `runsv`: a bounded delay/backoff on
  immediate exits, and no restart when state is ambiguous. The hardened supervisor adds
  exponential backoff (1s→2s→…→cap) and a FAIL-CLOSED path on duplicates.

## 2b. Termux services (runit) — official

### https://raw.githubusercontent.com/termux/termux-services/master/README.md
Verified content: install `termux-services`; restart the shell so the service-daemon
starts; enable with `sv-enable <service>` or simply `sv up <service>`; check problems in
`$PREFIX/var/log/sv/<service>/current`; a service is disabled if
`$PREFIX/var/service/<service>/down` exists.
Decision: matches the measured phone state (`runsvdir` pid 9688 + `runsv go-runtime`). To
diagnose the GO crash loop the owner reads `$PREFIX/var/log/sv/go-runtime/current`; to
(re)start use `sv up go-runtime` — now valid because `runsvdir` is running, so the earlier
`unable to open supervise/ok` should not recur.
Note: `https://wiki.termux.com/wiki/Termux-services` returned an **Anubis bot-challenge**
page and could not be read; the official GitHub README was used instead.

### http://smarden.org/runit/runsvdir.8.html
Verified content: `runsvdir` starts a `runsv` per service subdir, rescans the dir at least
every 5s, up to 1000 subdirs, and restarts a runsv if it terminates; TERM stops monitoring.
Decision: a registered service whose `run` exits immediately is restarted by runsv →
explains the measured GO "<2s process churn".

## 3. Linux `/proc` — process identity

### 3.1 https://www.kernel.org/doc/html/latest/filesystems/proc.html
Verified content:
- One directory per process `/proc/<pid>` with `cmdline`, `stat`, `status`, `exe`, etc.;
  `ps` reads from `/proc`.
- **PID reuse:** "an open file descriptor to /proc/<pid> … does not prevent <pid> from being
  reused"; operations on a dead PID's `/proc` entries fail with `ESRCH`. Reading another
  process's `/proc/<pid>/*` needs `CAP_SYS_PTRACE`/`CAP_PERFMON` (self-reads are free).

Decisions affected (B2 PID hygiene):
- PID identity via `/proc/<pid>/cmdline` is **best-effort** and subject to PID reuse; exact
  argv matching (already used) is stronger than `pgrep -f`, but the supervisor must also
  gate on "is my child still alive" (`kill -0 $pid`) and must never kill on ambiguity.
  Third-party supervision (runit) is the robust alternative where available.

## 4. Canonical GO source (repository, not a doc)
Read directly from `OAI-GIANG/GO` (branch `feature/stt-b1-b5-reconciliation-20261010`):
- `runtime/go_runtime/core/authority.py` — single authority root; `_require_external()`
  raises `AUTHORITY_ROOT_NOT_EXTERNAL` for `SELF_PROVISIONED`/`EPHEMERAL`; external key file
  `/etc/hg/authority/root.key` (env `HG_AUTHORITY_ROOT_KEY_FILE`); revocation via
  `HG_AUTHORITY_REVOCATION_FILE`.
- `evidence/B1_B5_RECONCILIATION_IMPLEMENTATION_20261010.md` — B3: `TRUSTED_APPROVAL_ISSUERS`
  intentionally empty; missing root ⇒ `AUTHORITY_ROOT_NOT_PROVISIONED`; no silent self-trust.
- `tests/test_b1_b5_contracts.py` — string `"approved"` is not approval evidence;
  destructive tool denied **before** dispatch if a token file is absent/rejected.

Decisions affected (B5-b): provisioning `root.key` is necessary but **not sufficient**;
trusted approval issuers/verifier must also be provisioned by an external principal. No
fabricated external provenance is permitted.

## 5. TLS / certificates (B4)

### https://eff-certbot.readthedocs.io/en/stable/using.html
Verified content: `certbot renew` re-checks installed certificates and renews those near
expiry; automated renewal is a scheduled task (cron line or a **systemd timer**, visible via
`systemctl list-timers`); `certbot certificates` lists expiry and paths; certificates created
with `--manual` do **not** auto-renew without auth hooks; wildcard certs require DNS-01.
Decision: VPS1 serves the edge certificate from `/etc/letsencrypt/live/160.191.242.198`
(Let's Encrypt, IP SAN, `notAfter 2026-10-13T01:54:10Z`). Measured: **certbot is NOT
installed and there is no renewal timer**, so issuance was manual/other. B4 needs a working
renewal path before expiry: install an ACME client (e.g. certbot) + HTTP-01/webroot or DNS-01
and add a timer/cron, **or** reissue by the same manual method — an owner/authority action.
Deep deliberately did not install or modify TLS (production change requiring authority).
Note: `https://letsencrypt.org/docs/renewal/` returned 404; the EFF certbot guide was used.
