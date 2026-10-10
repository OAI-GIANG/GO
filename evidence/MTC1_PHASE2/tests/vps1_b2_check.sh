#!/usr/bin/env bash
set -u
E=$(grep -m1 '^HG_EDGE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
G=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
echo "== tunnel status (3 samples, 4s apart) =="
for i in 1 2 3; do curl -s -m5 -H "Authorization: Bearer $E" "http://127.0.0.1:8899/edge/tunnel/status?device_id=phone-primary-u0_a460"; echo; sleep 4; done
echo "== gate round-trip WITH token (expect 200 if tunnel works) =="
curl -s -m 25 -o /tmp/mg -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $G" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
echo -n "body: "; cat /tmp/mg 2>/dev/null | head -c 400; echo
rm -f /tmp/mg
echo "== recent edge log =="
journalctl -u hg-edge --no-pager -n 6 | tail -5
echo DONE
