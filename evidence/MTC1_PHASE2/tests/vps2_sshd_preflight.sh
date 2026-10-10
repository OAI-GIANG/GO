#!/usr/bin/env bash
set -u
echo "== VPS2 sshd preflight (via jump) =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@36.50.135.233 'bash -s' 2>&1 <<'EOS'
set -u
echo "unit candidates:"; systemctl list-units --type=service --no-legend 2>/dev/null | grep -iE 'ssh' || true
echo "sshd -t: "; sshd -t && echo "SYNTAX_OK" || echo "SYNTAX_FAIL rc=$?"
echo "main config relevant lines:"; grep -nE 'Include|PasswordAuthentication|PermitRootLogin|PubkeyAuthentication|KbdInteractive' /etc/ssh/sshd_config 2>/dev/null
echo "drop-in dir:"; ls -la /etc/ssh/sshd_config.d/ 2>/dev/null
echo "drop-in contents:"; grep -rn . /etc/ssh/sshd_config.d/ 2>/dev/null | head -20
echo "effective now:"; sshd -T 2>/dev/null | grep -iE '^(permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication) ' | sed 's/^/  /'
echo "backups present:"; ls -la /etc/ssh/sshd_config.bak-* 2>/dev/null | tail -3
EOS
echo DONE
