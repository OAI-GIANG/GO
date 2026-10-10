#!/usr/bin/env bash
set -u
E=$(grep -m1 '^HG_EDGE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
G=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
echo "== FINAL B2/B4 check =="
echo -n "edge queue: "; curl -s -H "Authorization: Bearer $E" "http://127.0.0.1:8899/edge/tunnel/status?device_id=phone-primary-u0_a460"; echo
echo -n "gate 200: "; curl -s -m 15 -o /tmp/fg -w '%{http_code}' -H "Authorization: Bearer $G" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"; echo -n "  body: "; head -c 160 /tmp/fg; echo
echo -n "cert notAfter: "; openssl x509 -in /etc/letsencrypt/live/160.191.242.198/cert.pem -noout -enddate
echo -n "timer: "; systemctl is-active certbot-renew.timer
rm -f /tmp/fg
echo DONE
