#!/usr/bin/env bash
set -u
G=$(grep -m1 '^HG_GATE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
E=$(grep -m1 '^HG_EDGE_TOKEN=' /etc/hg-edge/edge.env | cut -d= -f2- | tr -d '"')
T=$(grep -m1 '^GO_API_TOKEN=' /etc/go/go-runtime.env | cut -d= -f2- | tr -d '"')
echo "== B1 =="
echo -n "go-runtime=$(systemctl is-active go-runtime) healthz="; curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8877/healthz
echo -n " status(auth)="; curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $T" http://127.0.0.1:8877/v1/status
echo -n " status(no token)="; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8877/v1/status
echo "== B2 =="
echo -n "edge queue: "; curl -s -H "Authorization: Bearer $E" "http://127.0.0.1:8899/edge/tunnel/status?device_id=phone-primary-u0_a460"; echo
echo -n "gate(auth)="; curl -s -m15 -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $G" "https://160.191.242.198/h/phone-primary-u0_a460/api/health"
echo "== TLS =="
echo -n "cert: "; openssl x509 -in /etc/letsencrypt/live/160.191.242.198/cert.pem -noout -enddate
echo -n "renew timer: "; systemctl is-active certbot-renew.timer
echo "== B5-b DENY (no env) still fail-closed =="
cd /opt/go && PYTHONPATH=/opt/go env -u HG_TOOL_AUTHORITY_PROVENANCE -u HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED python3 -c "
from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
r=ToolRegistry(); r.register(VPS1HealthTool())
res=ToolGovernance(r).execute('HG-TOOLPLANE','vps1.edge.health',{},call_id='CALL-DENY-REG')
print('deny ok=',res.ok,' output=',res.output)
" 2>&1
echo DONE
