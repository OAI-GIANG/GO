#!/usr/bin/env bash
set -u
# Place owner-run helper scripts on VPS1 and VPS2 (NOT executed by Deep).
echo "== VPS1: write owner helper scripts =="
cat > /root/OWNER_PROVISION_AUTHORITY.sh <<'EOS'
#!/usr/bin/env bash
# OWNER-RUN. Provisions the EXTERNAL authority root key for the GO runtime.
# Run this ONLY as the owner, from the owner's own session. Deep must not run it.
set -euo pipefail
D=/etc/hg/authority
install -d -m 700 "$D"
if [ -s "$D/root.key" ]; then echo "root.key already exists (mode $(stat -c %a "$D/root.key")); not overwriting"; exit 0; fi
umask 077
head -c 32 /dev/urandom > "$D/root.key"
chmod 600 "$D/root.key"
systemctl restart go-runtime
sleep 3
echo "provisioned: $D/root.key mode=$(stat -c %a "$D/root.key") size=$(stat -c %s "$D/root.key")"
echo "go-runtime: $(systemctl is-active go-runtime)"
echo "next: Deep runs the ALLOW E2E"
EOS
chmod 700 /root/OWNER_PROVISION_AUTHORITY.sh
cat > /root/OWNER_HANDOVER.md <<'EOS'
# Owner runbook (VPS1)
1) Android access: ssh -i ~/.ssh/love_admin_ed25519 root@160.191.242.198
2) Close Phase 2 (B5-b ALLOW): run /root/OWNER_PROVISION_AUTHORITY.sh
   (creates the external authority root key + restarts go-runtime)
3) Verify services: systemctl is-active go-runtime hg-edge ; ss -ltnp | grep 8877
EOS
echo "vps1 helpers written"
echo "== VPS2: write owner hardening helper (do NOT run until key login verified) =="
cat > /tmp/vps2_owner.sh <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
SSHD=/etc/ssh/sshd_config
cp -a "$SSHD" "$SSHD.bak-$(date -u +%Y%m%dT%H%M%SZ)"
sed -ri 's/^#?\s*PermitRootLogin\s+.*/PermitRootLogin prohibit-password/' "$SSHD"
sed -ri 's/^#?\s*PasswordAuthentication\s+.*/PasswordAuthentication no/' "$SSHD"
sshd -t
systemctl reload ssh 2>/dev/null || systemctl reload sshd
echo "hardened: $(sshd -T | grep -iE '^(permitrootlogin|passwordauthentication) ' | tr '\n' ';')"
EOS
scp -q -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=accept-new /tmp/vps2_owner.sh root@36.50.135.233:/root/OWNER_HARDEN_SSHD.sh
ssh -i /root/.ssh/hg_vps2_ed25519 -o BatchMode=yes -o ConnectTimeout=10 root@36.50.135.233 'chmod 700 /root/OWNER_HARDEN_SSHD.sh; ls -la /root/OWNER_HARDEN_SSHD.sh' 2>&1
rm -f /tmp/vps2_owner.sh
echo DONE
