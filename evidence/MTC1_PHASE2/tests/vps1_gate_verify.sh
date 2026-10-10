#!/usr/bin/env bash
set -u
G=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
echo "gate_token_len=${#G}"
echo "== gate WITH valid token (mongoose dispatch to tunnel; expect 504 GATE_TIMEOUT) =="
curl -s -m 20 -o /tmp/mtc_gate -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $G" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
echo -n "body: "; cat /tmp/mtc_gate 2>/dev/null | head -c 200; echo
echo "== gate WITHOUT token (expect 401) =="
curl -s -m 8 -o /tmp/mtc_gate2 -w 'HTTP %{http_code}\n' "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
echo -n "body: "; cat /tmp/mtc_gate2 2>/dev/null | head -c 200; echo
echo "== gate with WRONG token (expect 401) =="
curl -s -m 8 -o /dev/null -w 'HTTP %{http_code}\n' -H "Authorization: Bearer wrong" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
rm -f /tmp/mtc_gate /tmp/mtc_gate2
echo DONE
