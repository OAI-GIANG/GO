#!/usr/bin/env bash
set -u
echo "== VPS2 authority/GO deep inventory (via VPS1) =="
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@36.50.135.233 'bash -s' 2>&1 <<'EOS'
set -u
echo "host: $(hostname)"
echo "-- /etc/hg tree --"; find /etc/hg /etc/hg-authority -maxdepth 2 2>/dev/null
echo "-- authority/root key files --"; find / -maxdepth 4 \( -name 'root.key' -o -iname '*authority*key*' \) 2>/dev/null | grep -vE '/proc|/sys|/usr/|/etc/ssl|snap' | head
echo "-- /opt/hg-authority --"; ls -la /opt/hg-authority 2>/dev/null
echo "-- authority.env keys --"; grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' /etc/hg-authority/authority.env 2>/dev/null
echo "-- services --"; systemctl list-units --type=service --no-legend 2>/dev/null | grep -iE 'authority|go|edge|ops|hg' | head
echo "-- listeners --"; ss -ltnp 2>/dev/null | grep -E ':9098|:9099|:8877|:443|:8888'
echo "-- /opt/hg-authority/authority.py head --"; sed -n '1,30p' /opt/hg-authority/authority.py 2>/dev/null
echo "-- GO runtime present? --"; ls -d /opt/go 2>&1
EOS
echo DONE
