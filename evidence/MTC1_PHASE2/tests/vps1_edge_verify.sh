#!/usr/bin/env bash
set -u
echo "== /etc/hg-edge/edge.env keys (names only) =="
grep -o '^[A-Za-z_][A-Za-z0-9_]*=' /etc/hg-edge/edge.env 2>/dev/null
EDGE=$(grep -m1 '^HG_EDGE_TOKEN=' /etc/hg-edge/edge.env 2>/dev/null | cut -d= -f2- | tr -d '"'"'"'')
GATE=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env 2>/dev/null | cut -d= -f2- | tr -d '"'"'"'')
echo "edge_token_len=${#EDGE} gate_token_len=${#GATE}"
echo "== /edge/status (auth) =="
curl -s -m5 -H "Authorization: Bearer $EDGE" http://127.0.0.1:8899/edge/status 2>&1 | head -c 800; echo
echo "== /edge/tunnel/status phone-primary-u0_a460 =="
curl -s -m5 -H "Authorization: Bearer $EDGE" "http://127.0.0.1:8899/edge/tunnel/status?device_id=phone-primary-u0_a460" 2>&1 | head -c 400; echo
echo "== gate endpoint WITH token (server-side) =="
curl -s -m8 -o /tmp/gate_out -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $GATE" "https://160.191.242.198/h/phone-primary-u0_a460/api/health" 2>&1
head -c 300 /tmp/gate_out; echo
echo "== gate endpoint WITHOUT token =="
curl -s -m8 -o /dev/null -w 'HTTP %{http_code}\n' "https://160.191.242.198/h/phone-primary-u0_a460/api/health" 2>&1
echo "== edge service (8899) =="
systemctl status $(systemctl list-units --type=service --no-legend | awk '{print $1}' | grep -iE 'edge|tunnel' | head -1) --no-pager 2>&1 | head -8
ps -o pid,ppid,args -p 42908 2>&1
echo "== devices known to edge =="
curl -s -m5 -H "Authorization: Bearer $EDGE" "http://127.0.0.1:8899/edge/status" 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin);print('devices:',[x.get('device_id') for x in d.get('devices',[])])" 2>&1
rm -f /tmp/gate_out
echo DONE
