#!/usr/bin/env bash
set -u
echo "== VPS2: preflight =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@36.50.135.233 'bash -s' 2>&1 <<'EOS'
set -u
echo "BEFORE:"; sshd -T | grep -iE '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication) ' | sed 's/^/  /'
TS=$(date -u +%Y%m%dT%H%M%SZ)
cp -a /etc/ssh/sshd_config /etc/ssh/sshd_config.bak-$TS
cp -a /etc/ssh/sshd_config.d/50-cloud-init.conf /etc/ssh/sshd_config.d/50-cloud-init.conf.bak-$TS 2>/dev/null || true
echo "backup: sshd_config.bak-$TS"
# 00- sorts before 50-cloud-init.conf, so first-obtained-value wins => our values apply.
cat > /etc/ssh/sshd_config.d/00-hg-hardening.conf <<'EOF'
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
chmod 644 /etc/ssh/sshd_config.d/00-hg-hardening.conf
if ! sshd -t; then echo "SYNTAX_FAIL -> ROLLBACK"; rm -f /etc/ssh/sshd_config.d/00-hg-hardening.conf; exit 2; fi
systemctl reload ssh && echo "reloaded"
sleep 1
echo "AFTER:"; sshd -T | grep -iE '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication) ' | sed 's/^/  /'
EOS
echo "== VPS2: fresh key login test (new connection from VPS1) =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@36.50.135.233 'echo KEYLOGIN_OK; hostname; id -un' 2>&1
echo "== VPS2: owner login records (d9Tz) =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o ConnectTimeout=10 root@36.50.135.233 'grep -h d9Tz /var/log/auth.log | tail -2' 2>&1
echo DONE
