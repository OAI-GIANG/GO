#!/usr/bin/env bash
set -u
echo "== canonical GO data dir =="; ls -la /opt/go/data/ /var/lib/go/ 2>&1
echo "== canonical tool ledger =="
for f in /opt/go/data/tool-events.jsonl /var/lib/go/tool-events.jsonl; do
  if [ -f "$f" ]; then echo "$f lines=$(wc -l < "$f")"; tail -2 "$f"; else echo "$f absent"; fi
done
echo "== TLS cert (public, via 127.0.0.1:443) =="
echo | openssl s_client -connect 127.0.0.1:443 -servername 160.191.242.198 2>/dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName 2>&1
echo "== letsencrypt live =="; ls -la /etc/letsencrypt/live/ 2>&1
echo "== certbot renew dry-run (no changes) =="; command -v certbot >/dev/null && certbot renew --dry-run 2>&1 | tail -15 || echo "certbot not installed"
echo "== certbot timers =="; systemctl list-timers --all 2>/dev/null | grep -iE 'certbot|letsencrypt' || echo "no certbot timer"
echo "== authority services (9097/9098) =="; ss -ltnp 2>/dev/null | grep -E ':9097|:9098|:8888'; systemctl list-units --type=service --no-legend 2>/dev/null | grep -iE 'authority|ops' | head
echo DONE
