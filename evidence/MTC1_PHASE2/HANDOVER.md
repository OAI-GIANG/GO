# MISSION B — VPS1/VPS2 Android Owner Handover

Status: **SETUP COMPLETE for both VPS; LIVE OWNER LOGIN VERIFIED for VPS1 (historical),
PENDING for VPS2.** No secret values are stored here.

## Credential / access inventory (measured 2026-10-10T11:31Z)

| Item | VPS1 `160.191.242.198` (vps-hjcscw) | VPS2 `36.50.135.233` (vps-5ku1ry) |
|---|---|---|
| SSH port | 22 | 22 |
| Root login | `PermitRootLogin without-password` | `PermitRootLogin yes` |
| Password auth | `no` | **`yes`** (hardening item) |
| Pubkey auth | yes | yes |
| AllowUsers | `root loveadmin stt-exec` | (default) |
| Admin users | `root`, `loveadmin` (NOPASSWD sudo) | `root` |
| Owner phone key (fp `SHA256:d9Tz…`, comment `love-admin@localhost-20260928`) | **authorized on root** (and historical logins) | **authorized today** (added) |
| Other root keys | `go2LJ…` (love-admin@vps-000071), `9iiP…` (love-production), `xU04…` (LAPTOP-E9FGVI95) | `+ADgN…` (root@vps-hjcscw) + owner key |
| Host keys | DSA + RSA (provider image; no ed25519 host key — hardening item) | (ed25519 .pub absent; provider image) |
| Reachability from workstation | direct | only via VPS1 jump (`hg_vps2_ed25519`) |

### Key attribution evidence
- The owner key fingerprint `SHA256:d9Tz+WxSL8FuCLp0y2tlq2fYiyUKhDhDVp6S1dKxOcU` is on the
  **phone** (`~/.ssh/love_admin_ed25519.pub`, comment `love-admin@localhost-20260928`).
- The **workstation does not hold** `d9Tz` (its keys are `go2LJ…`, `xU04…`, `9iiP…`, `EOEJ…`, `Z9Ht…`).
- VPS1 `/var/log/auth.log` shows **5 accepted root logins using `d9Tz`** on 2026-10-09
  (23:00, 23:43, 23:52) and 2026-10-10T00:11 from `171.255.245.247` (the shared home NAT IP).
  => Owner Android → VPS1 root login demonstrated (VPS1 = `OWNER_ANDROID_ACCESS` historical).

## Owner actions (minimal, on the Android phone / Termux)

VPS1:
```sh
ssh -i ~/.ssh/love_admin_ed25519 root@160.191.242.198 'hostname; id'
```
VPS2:
```sh
ssh -i ~/.ssh/love_admin_ed25519 root@36.50.135.233 'hostname; id'
```
Both hosts are already in the phone's `~/.ssh/known_hosts`. Then **disconnect and reconnect**
once, and view service state/logs, e.g. `systemctl is-active go-runtime hg-edge; journalctl -n 5`.

## Recovery & independence
- Private key lives only on the phone (`~/.ssh/love_admin_ed25519`); back it up to an encrypted
  store the owner controls. Keep the phone screen-lock/biometrics enabled.
- Out-of-band break-glass: the VPS provider control panel (independent of SSH).
- No chat pasting of keys. Use `ssh-keygen -y` to re-derive a public key if needed.
- Deep holds no exclusively-owned credential required for owner access: the owner key is the
  owner's; Deep's key (`xU04…`) is a separate admin credential.

## Hardening (after owner verifies VPS2 key — do NOT lock out first)
- VPS2: set `PermitRootLogin prohibit-password` and `PasswordAuthentication no` (per
  `sshd_config(5)`: `prohibit-password` disables password for root). Backup `sshd_config`,
  `sshd -t`, reload; keep an existing session open while testing.
- Remove legacy DSA host key / generate ed25519 host key (optional, medium risk).

## Handover matrix

| Criterion | VPS1 | VPS2 |
|---|---|---|
| Owner key authorized | PASS | PASS (added 2026-10-10) |
| Key attributed to phone (not Deep) | PASS | PASS |
| Real login from Android | PASS (historical 2026-10-09) | **PENDING (owner login)** |
| Admin privilege | PASS (root) | PASS (root) |
| Reconnect/ recovery path | PASS (provider console) | PASS (provider console) |
| No dependence on Deep credential | PASS | PASS |

`ANDROID_HANDOVER_COMPLETED = FALSE` — VPS2 live owner login not yet demonstrated; VPS1 has
historical evidence (recommend one fresh owner login to re-confirm).
