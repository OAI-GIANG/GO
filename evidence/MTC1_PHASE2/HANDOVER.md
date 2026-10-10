# MISSION B — VPS1/VPS2 Android Owner Handover

Status: **VPS1 verified (historical) · VPS2 verified (live) + hardened.**
`ANDROID_HANDOVER_COMPLETED = TRUE` (evidence below). No secret values stored here.

## Credential / access inventory (2026-10-10)

| Item | VPS1 `160.191.242.198` (vps-hjcscw) | VPS2 `36.50.135.233` (vps-5ku1ry) |
|---|---|---|
| SSH port | 22 | 22 |
| Root login | `PermitRootLogin without-password` | `PermitRootLogin without-password` (hardened) |
| Password auth | `no` | **`no`** (hardened 2026-10-10) |
| Admin users | `root`, `loveadmin` (NOPASSWD sudo) | `root` |
| Owner phone key `SHA256:d9Tz…` | authorized on root; **5 logins 2026-10-09/10** | authorized; **login 2026-10-10T11:35:42Z** |
| Other root keys | `go2LJ…`, `9iiP…`, `xU04…` (Deep) | `+ADgN…` (VPS1 jump) + owner key |
| Reachability | direct | via VPS1 jump (Deep) / direct (owner) |

### Verification evidence
- **VPS2 live login:** `/var/log/auth.log` → `Accepted publickey for root from 171.255.245.247 …
  SHA256:d9Tz…` at 2026-10-10T11:35:42Z. The workstation holds no `d9Tz` key and reaches VPS2
  only via the VPS1 jump (source `160.191.242.198`), so this login came from the **phone**.
- **VPS1 login:** same key, 5 accepted logins on 2026-10-09 (23:00/23:43/23:52) and 2026-10-10T00:11.
- Hardening verified: fresh key login `KEYLOGIN_OK` after `PasswordAuthentication no`.

## Hardening applied (VPS2)
- Drop-in `/etc/ssh/sshd_config.d/00-hg-hardening.conf` (sorts before `50-cloud-init.conf`,
  which is why a main-config edit would be ineffective — Include is first-value-wins).
  `PermitRootLogin prohibit-password`; `PasswordAuthentication no`; `KbdInteractiveAuthentication no`.
- `sshd -t` OK; `systemctl reload ssh`; backups `sshd_config.bak-20261010T113658Z`.
- Rollback: `rm -f /etc/ssh/sshd_config.d/00-hg-hardening.conf && systemctl reload ssh`.

## Handover matrix

| Criterion | VPS1 | VPS2 |
|---|---|---|
| Owner key authorized | PASS | PASS |
| Key attributed to phone (not Deep) | PASS | PASS |
| Real login from Android | **PASS** (historical 2026-10-09) | **PASS** (2026-10-10T11:35:42Z) |
| Admin privilege (root) | PASS | PASS |
| Owner controls auth method (own key) | PASS | PASS |
| Reconnect / recovery path | PASS (provider console) | PASS (provider console) |
| No dependence on Deep credential | PASS | PASS |

## Remaining / recommendations
- Optional: a fresh VPS1 login for the current period (historical evidence already exists).
- Optional: rotate Deep's admin key (`xU04…`) off when the owner no longer needs it.
- Break-glass: VPS provider control panel (independent of SSH); keep the owner private key
  backed up in an encrypted store.
