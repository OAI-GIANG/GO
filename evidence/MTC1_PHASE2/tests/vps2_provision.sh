#!/usr/bin/env bash
set -u
echo "== VPS1: identify the owner (phone) key already authorized =="
PHONE=$(grep 'love-admin@localhost-20260928' /root/.ssh/authorized_keys | head -1)
if [ -z "$PHONE" ]; then echo "PHONE_KEY_NOT_FOUND_ON_VPS1"; exit 3; fi
printf 'phone key fingerprint: '; printf '%s\n' "$PHONE" | ssh-keygen -lf -
printf '%s\n' "$PHONE" > /tmp/ownerkey.pub

echo "== VPS2: provision owner key (backup + append if absent) =="
cat > /tmp/vps2_prov.sh <<'EOS'
set -u
KEY=$(cat /tmp/ownerkey.pub)
AK=/root/.ssh/authorized_keys
mkdir -p /root/.ssh; chmod 700 /root/.ssh; touch "$AK"; chmod 600 "$AK"
cp -a "$AK" "$AK.bak-$(date -u +%Y%m%dT%H%M%SZ)"
if grep -qF "$KEY" "$AK"; then echo "owner key already present on VPS2"; else printf '%s\n' "$KEY" >> "$AK"; echo "owner key ADDED to VPS2"; fi
echo "VPS2 hostname: $(hostname)"
echo "VPS2 root authorized_keys fingerprints:"; ssh-keygen -lf "$AK"
echo "VPS2 users:"; awk -F: '$1=="root"||$3>=1000{print "  "$1" uid="$3" shell="$7}' /etc/passwd
echo "VPS2 sshd:"; sshd -T 2>/dev/null | grep -iE '^(passwordauthentication|permitrootlogin|pubkeyauthentication|allowusers|port) ' | sed 's/^/  /'
echo "VPS2 authority/GO dirs:"; ls -d /etc/hg/authority /opt/go /opt/hg-authority 2>/dev/null | sed 's/^/  /'
echo "VPS2 listeners:"; ss -ltnp 2>/dev/null | grep -E ':9098|:9099|:8877|:443|:8888' | sed 's/^/  /'
EOS

scp -q -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new /tmp/ownerkey.pub /tmp/vps2_prov.sh root@36.50.135.233:/tmp/ 2>&1 || { echo "SCP_TO_VPS2_FAILED"; exit 4; }
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o ConnectTimeout=10 root@36.50.135.233 'bash /tmp/vps2_prov.sh; rm -f /tmp/vps2_prov.sh /tmp/ownerkey.pub' 2>&1
rm -f /tmp/ownerkey.pub /tmp/vps2_prov.sh
echo DONE
