#!/usr/bin/env bash
set -u
echo "== VPS1 readiness =="
echo "date_utc=$(date -u +%FT%TZ)"
echo "hostkey_fp: $(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub 2>/dev/null)"
echo "loveadmin key:"; ls -la /home/loveadmin/.ssh 2>/dev/null; ssh-keygen -lf /home/loveadmin/.ssh/authorized_keys 2>/dev/null
echo "recent accepted logins (auth.log):"; grep -hE 'Accepted (publickey|password)' /var/log/auth.log 2>/dev/null | tail -8
echo "== VPS2 readiness (via VPS1 jump) =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@36.50.135.233 'bash -s' 2>&1 <<'EOS'
set -u
echo "date_utc=$(date -u +%FT%TZ)"
echo "hostname=$(hostname)"
echo "hostkey_fp: $(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub 2>/dev/null)"
echo "recent accepted logins (auth.log):"; grep -hE 'Accepted (publickey|password)' /var/log/auth.log 2>/dev/null | tail -8
echo "root authorized_keys fingerprints:"; ssh-keygen -lf /root/.ssh/authorized_keys 2>/dev/null
EOS
echo DONE
