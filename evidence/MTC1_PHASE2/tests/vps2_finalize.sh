#!/usr/bin/env bash
set -u
echo "== VPS1: ALLOW prerequisite state =="
ls -la /etc/hg/authority 2>&1
echo "go-runtime: $(systemctl is-active go-runtime)"
echo "== VPS2: owner login evidence + refresh helper artifact =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@36.50.135.233 'bash -s' 2>&1 <<'EOS'
set -u
echo "-- d9Tz logins on VPS2 --"; grep -h d9Tz /var/log/auth.log | tail -3
echo "-- effective sshd --"; sshd -T | grep -iE '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication) '
cat > /root/OWNER_HARDEN_SSHD.sh <<'EOF'
#!/usr/bin/env bash
# OWNER-RUN hardening for VPS2 sshd (idempotent). Already applied 2026-10-10.
# Correct approach: a 00- drop-in wins over 50-cloud-init.conf (Include is first-value-wins).
set -euo pipefail
D=/etc/ssh/sshd_config.d/00-hg-hardening.conf
TS=$(date -u +%Y%m%dT%H%M%SZ)
[ -f /etc/ssh/sshd_config ] && cp -a /etc/ssh/sshd_config "/etc/ssh/sshd_config.bak-$TS"
cat > "$D" <<'CONF'
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
CONF
chmod 644 "$D"
sshd -t
systemctl reload ssh
sshd -T | grep -iE '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication) '
# Rollback: rm -f "$D"; systemctl reload ssh
EOF
chmod 700 /root/OWNER_HARDEN_SSHD.sh
cat > /root/OWNER_HANDOVER_STATUS.md <<'EOF'
# Owner status (VPS2) — 2026-10-10
- Owner Android key login VERIFIED: auth.log "Accepted publickey ... SHA256:d9Tz..." from the phone.
- sshd hardened: PermitRootLogin prohibit-password; PasswordAuthentication no (drop-in 00-hg-hardening.conf).
- Re-run hardening (idempotent): /root/OWNER_HARDEN_SSHD.sh
- Rollback: rm -f /etc/ssh/sshd_config.d/00-hg-hardening.conf && systemctl reload ssh
# Owner status (VPS1)
- Close Phase 2 (B5-b ALLOW): run /root/OWNER_PROVISION_AUTHORITY.sh (external authority root).
EOF
echo "helper/status files updated"
EOS
echo DONE
