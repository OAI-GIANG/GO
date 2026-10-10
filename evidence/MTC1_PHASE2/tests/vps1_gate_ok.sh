#!/usr/bin/env bash
set -u
G=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
E=$(grep -m1 '^HG_EDGE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
echo "== gate round-trip (Bearer gate token) =="
curl -s -m 20 -o /tmp/g1 -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $G" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
echo -n "body: "; cat /tmp/g1 2>/dev/null; echo
echo "== gate no-token =="; curl -s -m 8 -o /dev/null -w 'HTTP %{http_code}\n' "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
echo "== queue after =="; curl -s -H "Authorization: Bearer $E" "http://127.0.0.1:8899/edge/tunnel/status?device_id=phone-primary-u0_a460"; echo
rm -f /tmp/g1
echo DONE
