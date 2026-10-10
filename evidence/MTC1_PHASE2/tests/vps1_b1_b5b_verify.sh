#!/usr/bin/env bash
set -u
LED="/tmp/mtc1_tool_events_$$.jsonl"
echo "== B1: GO identity =="
tr '\0' ' ' < /proc/$(pgrep -f 'go_runtime.core.server' | head -1)/cmdline 2>/dev/null; echo
systemctl show -p ActiveState -p SubState -p MainPID go-runtime 2>&1
grep -E '^(GO_COMMIT|GO_TREE_SHA|GO_ENV|GO_HOST|GO_PORT)=' /etc/go/go-runtime.env 2>/dev/null
echo "== B1: /healthz =="
curl -s -m5 http://127.0.0.1:8877/healthz; echo
echo "== B1: /v1/status (auth) HTTP + first 200 bytes =="
T=$(grep -m1 '^GO_API_TOKEN=' /etc/go/go-runtime.env | cut -d= -f2- | tr -d '"')
curl -s -m5 -w '\nHTTP %{http_code}\n' -H "Authorization: Bearer $T" http://127.0.0.1:8877/v1/status | head -c 400; echo
echo "== B1: /v1/status WITHOUT token =="
curl -s -m5 -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8877/v1/status
echo "== B5-b: canonical ToolGovernance DENY (no authority env) on vps1.edge.health =="
cat > /tmp/mtc1_cangov.py <<'PY'
import sys, os, json
sys.path.insert(0, "/opt/go")
from runtime.go_runtime.core.tool_governance import ToolGovernance, ToolGovernanceError
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
tool, call_id, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3] or "{}")
reg = ToolRegistry(); reg.register(VPS1HealthTool()); gov = ToolGovernance(reg)
try:
    r = gov.execute("HG-TOOLPLANE", tool, args, call_id=call_id)
    print(json.dumps({"ok": bool(r.ok), "output": r.output, "witness": r.witness}))
except ToolGovernanceError as e:
    print(json.dumps({"denied": e.code}))
except Exception as e:
    print(json.dumps({"error": type(e).__name__ + ": " + str(e)[:160]}))
PY
( cd /opt/go && HG_TOOL_EVENT_LEDGER="$LED" PYTHONPATH=/opt/go python3 /tmp/mtc1_cangov.py vps1.edge.health "CALL-MTC1-DENY-1" '{}' ) 2>&1
echo "-- ledger events written --"; cat "$LED" 2>/dev/null | head
echo "== B2/B4: edge tunnel + gate =="
curl -s -m5 http://127.0.0.1:8899/edge/health 2>&1 | head -c 200; echo
curl -s -m5 "http://127.0.0.1:8899/edge/tunnel/status" 2>&1 | head -c 200; echo
echo "== 8899 owner service =="
ss -ltnp 2>/dev/null | grep ':8899'
rm -f "$LED" /tmp/mtc1_cangov.py
echo DONE
