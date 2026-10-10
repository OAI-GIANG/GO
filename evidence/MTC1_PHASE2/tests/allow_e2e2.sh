#!/usr/bin/env bash
set -u
# Reproduce the service environment exactly for the tool call.
set -a; . /etc/go/go-runtime.env; set +a
export HG_EDGE_URL=https://160.191.242.198          # unit drop-in Environment=
export HG_EDGE_TOKEN_CREDENTIAL_FILE=/etc/hg-edge/edge.env
cd /opt/go || exit 3

echo "== provenance =="
PYTHONPATH=/opt/go python3 - <<'PY'
from runtime.go_runtime.core.authority import AuthorityRoot
r=AuthorityRoot.instance(); print("provenance =", r.provenance(), "| is_external =", r.is_external())
PY

cat > /tmp/allow_e2e.py <<'PY'
import sys, json
sys.path.insert(0, "/opt/go")
from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
reg = ToolRegistry(); reg.register(VPS1HealthTool())
gov = ToolGovernance(reg)
r = gov.execute("HG-TOOLPLANE", "vps1.edge.health", {}, call_id="CALL-ALLOW-E2E-1")
print("ok =", r.ok)
print("output =", json.dumps(r.output)[:400])
print("witness_keys =", sorted(r.witness.keys()))
print("witness =", json.dumps(r.witness)[:900])
PY

cat > /tmp/allow_idem.py <<'PY'
import sys, json
sys.path.insert(0, "/opt/go")
from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
reg = ToolRegistry(); reg.register(VPS1HealthTool())
gov = ToolGovernance(reg)
# same task/tool/arguments as the successful call, new call_id
r = gov.execute("HG-TOOLPLANE", "vps1.edge.health", {}, call_id="CALL-ALLOW-E2E-2")
print("idem ok =", r.ok, "| output =", json.dumps(r.output)[:200], "| witness_status =", r.witness.get("status"))
PY

L=/tmp/allow_e2e.jsonl; rm -f "$L"
echo "== ALLOW E2E =="
HG_TOOL_EVENT_LEDGER="$L" PYTHONPATH=/opt/go python3 /tmp/allow_e2e.py 2>&1
echo "-- ledger states --"
python3 -c "import json;print([json.loads(l)['state'] for l in open('$L')])" 2>&1
echo "-- ledger COMPLETED event --"
python3 -c "import json;[print(l.strip()) for l in open('$L') if json.loads(l)['state']=='COMPLETED']" 2>&1
echo "== idempotency (same semantic call, new call_id) =="
HG_TOOL_EVENT_LEDGER="$L" PYTHONPATH=/opt/go python3 /tmp/allow_idem.py 2>&1
rm -f /tmp/allow_e2e.py /tmp/allow_idem.py "$L"
echo DONE
