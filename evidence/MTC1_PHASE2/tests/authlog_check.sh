#!/usr/bin/env bash
set -u
echo "== VPS1: any login using the phone key fingerprint d9Tz =="
{ grep -h 'd9Tz' /var/log/auth.log 2>/dev/null; zcat /var/log/auth.log.*.gz 2>/dev/null | grep 'd9Tz'; } | tail -10
echo "count_d9Tz=$( { grep -h 'd9Tz' /var/log/auth.log 2>/dev/null; zcat /var/log/auth.log.*.gz 2>/dev/null | grep -c 'd9Tz'; } | grep -c 'd9Tz')"
echo "== VPS1: distinct source IPs of accepted publickey logins =="
grep -hE 'Accepted publickey' /var/log/auth.log 2>/dev/null | grep -oE 'from [0-9.]+' | sort | uniq -c | sort -rn | head
echo "== VPS1 host keys =="; ls -la /etc/ssh/ssh_host_*_key.pub 2>/dev/null; for f in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$f" 2>/dev/null; done
echo "== VPS2: any login using the phone key d9Tz =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o ConnectTimeout=10 root@36.50.135.233 'grep -h d9Tz /var/log/auth.log 2>/dev/null | tail -5; echo vps2_d9Tz_count=$(grep -c d9Tz /var/log/auth.log 2>/dev/null); echo vps2_hostkey=$(ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub 2>/dev/null)' 2>&1
echo DONE
