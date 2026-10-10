#!/usr/bin/env bash
set -u
echo "== key presence (metadata only, no value) =="
stat -c 'root.key mode=%a size=%s owner=%U:%G' /etc/hg/authority/root.key 2>&1
ls -la /etc/hg/authority 2>&1
echo "== provenance via fresh process using the service EnvironmentFile =="
set -a; . /etc/go/go-runtime.env; set +a
cd /opt/go && PYTHONPATH=/opt/go python3 - <<'PY' 2>&1
from runtime.go_runtime.core.authority import AuthorityRoot
r = AuthorityRoot.instance()
print("provenance =", r.provenance(), "| is_external =", r.is_external())
PY
echo "== B5-b ALLOW E2E (canonical ToolGovernance, task=HG-TOOLPLANE, tool=vps1.edge.health) =="
cat > /tmp/allow_e2e.py <<'PY'
import sys, json
sys.path.insert(0, "/opt/go")
from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
reg = ToolRegistry(); reg.register(VPS1HealthTool())
gov = ToolGovernance(reg)
r = gov.execute("HG-TOOLPLANE", "vps1.edge.health", {}, call_id="CALL-ALLOW-E2E-1")
print("ok =", r.ok)
print("output =", json.dumps(r.output)[:300])
print("witness_keys =", sorted(r.witness.keys()))
print("witness =", json.dumps(r.witness)[:700])
PY
L=/tmp/allow_e2e.jsonl; rm -f "$L"
( cd /opt/go && HG_TOOL_EVENT_LEDGER="$L" PYTHONPATH=/opt/go python3 /tmp/allow_e2e.py ) 2>&1
echo "-- ledger states --"
python3 -c "import json;print([json.loads(l)['state'] for l in open('$L')])" 2>&1
echo "-- ledger COMPLETED event --"
python3 -c "import json;[print(json.dumps(json.loads(l))) for l in open('$L') if json.loads(l)['state']=='COMPLETED']" 2>&1
echo "== idempotency (same semantic call, new call_id) =="
cat > /tmp/allow_idem.py <<'PY'
import sys, json
sys.path.insert(0, "/opt/go")
from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
reg = ToolRegistry(); reg.register(VPS1HealthTool())
gov = ToolGovernance(reg)
r = gov.execute("HG-TOOLPLANE", "vps1.edge.health", {}, call_id="CALL-ALLOW-E2E-2")
print("ok =", r.ok, "| output =", json.dumps(r.output)[:200])
PY
( cd /opt/go && HG_TOOL_EVENT_LEDGER="$L" PYTHONPATH=/opt/go python3 /tmp/allow_idem.py ) 2>&1
rm -f /tmp/allow_e2e.py /tmp/allow_idem.py "$L"
echo DONE
