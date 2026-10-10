#!/usr/bin/env bash
set -u
E=$(grep -m1 '^HG_EDGE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
G=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
echo "== edge tunnel status =="
curl -s -H "Authorization: Bearer $E" "http://127.0.0.1:8899/edge/tunnel/status?device_id=phone-primary-u0_a460"; echo
echo "== edge device last_seen =="
curl -s -H "Authorization: Bearer $E" "http://127.0.0.1:8899/edge/status" | python3 -c "import sys,json;d=json.load(sys.stdin);print({x['device_id']:x.get('last_seen') for x in d['devices']})" 2>&1
echo "== authenticated gate (fresh request) =="
curl -s -m 15 -o /tmp/g -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $G" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
cat /tmp/g 2>/dev/null; echo; rm -f /tmp/g
echo "== hg-edge recent log =="
journalctl -u hg-edge --no-pager -n 5 | tail -4
echo DONE
