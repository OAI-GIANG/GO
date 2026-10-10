#!/usr/bin/env bash
set -u
# Use the EXISTING, owner-provisioned tool authority (EnvironmentFile), not a self-created one.
set -a; . /etc/go/go-runtime.env; set +a
echo "authority configured: provenance_set=$([ -n "${HG_TOOL_AUTHORITY_PROVENANCE:-}" ] && echo yes) expected_match=$([ "${HG_TOOL_AUTHORITY_PROVENANCE:-}" = "${HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED:-}" ] && echo yes) subject_prefix=${HG_TOOL_AUTHORITY_SUBJECT%%_*}"
cat > /tmp/cangov_allow.py <<'PY'
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
L=/tmp/mtc1_allow.jsonl; rm -f "$L"
echo "== ALLOW E2E (canonical ToolGovernance, provisioned authority) =="
( cd /opt/go && HG_TOOL_EVENT_LEDGER="$L" PYTHONPATH=/opt/go python3 /tmp/cangov_allow.py vps1.edge.health "CALL-MTC1-ALLOW-1" '{}' ) 2>&1
echo "== ledger states =="; cat "$L" 2>/dev/null | python3 -c "import sys,json;[print(json.loads(l).get('state'), json.loads(l).get('reason','')) for l in sys.stdin]" 2>/dev/null
echo "== idempotency (same call, new call_id) =="
( cd /opt/go && HG_TOOL_EVENT_LEDGER="$L" PYTHONPATH=/opt/go python3 /tmp/cangov_allow.py vps1.edge.health "CALL-MTC1-ALLOW-2" '{}' ) 2>&1
rm -f /tmp/cangov_allow.py "$L"
echo DONE
