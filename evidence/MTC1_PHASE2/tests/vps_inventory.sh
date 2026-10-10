#!/usr/bin/env bash
set -u
echo "======== VPS1 ($(hostname)) ========"
echo "== users (uid>=1000 or root) =="; awk -F: '$1=="root"||$3>=1000{print $1" uid="$3" shell="$7}' /etc/passwd
echo "== sudoers (NOPASSWD/sudo lines) =="; grep -rhE '^[^#]*(NOPASSWD|ALL=)' /etc/sudoers /etc/sudoers.d/* 2>/dev/null | head
echo "== sshd effective =="; sshd -T 2>/dev/null | grep -iE '^(passwordauthentication|permitrootlogin|pubkeyauthentication|allowusers|authorizedkeysfile|port) '
echo "== root authorized_keys (fingerprints) =="; [ -f /root/.ssh/authorized_keys ] && ssh-keygen -lf /root/.ssh/authorized_keys 2>/dev/null; echo "count=$(grep -c . /root/.ssh/authorized_keys 2>/dev/null)"
echo "== ssh keys under /root/.ssh =="; ls -la /root/.ssh 2>/dev/null
echo "== can we reach VPS2 from VPS1? =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 root@36.50.135.233 'echo VPS2_OK; hostname; whoami' 2>&1 | head -5
echo "======== VPS2 inventory (via VPS1 jump) ========"
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 root@36.50.135.233 'bash -s' <<'EOS' 2>&1
set -u
echo "hostname: $(hostname)"
awk -F: '$1=="root"||$3>=1000{print "user "$1" uid="$3" shell="$7}' /etc/passwd
echo "sshd: $(sshd -T 2>/dev/null | grep -iE '^(passwordauthentication|permitrootlogin|pubkeyauthentication) ' | tr '\n' ';')"
echo "root authorized_keys fingerprints:"; [ -f /root/.ssh/authorized_keys ] && ssh-keygen -lf /root/.ssh/authorized_keys 2>/dev/null; echo "count=$(grep -c . /root/.ssh/authorized_keys 2>/dev/null)"
echo "authority dirs:"; ls -la /etc/hg/authority 2>&1; ls -la /etc/hg-authority 2>&1
echo "go authority key files:"; find /etc /opt -maxdepth 3 -name 'root.key' -o -maxdepth 3 -name '*authority*key*' 2>/dev/null | head
echo "services:"; systemctl list-units --type=service --no-legend 2>/dev/null | grep -iE 'authority|go-runtime|edge|ops' | head
echo "listeners:"; ss -ltnp 2>/dev/null | grep -E ':9098|:9099|:8877|:443|:8888' | head
EOS
echo DONE
