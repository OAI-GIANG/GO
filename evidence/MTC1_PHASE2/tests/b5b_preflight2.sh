#!/usr/bin/env bash
set -u
cd /opt/go && PYTHONPATH=/opt/go python3 - <<'PY'
import inspect, sys
import runtime.go_kernel as k
for name in ("Authority","Authorization","Execution"):
    obj=getattr(k,name,None)
    print("==== %s ====" % name)
    if obj is None: print("MISSING"); continue
    print(inspect.getsource(obj))
PY
echo "== py version + module path =="
python3 -c "import sys; print(sys.version)"
echo "== does server/tool_governance reference governance_source or token file? =="
grep -rn "governance_source\|HG_TOOL_AUTHORITY_TOKEN_FILE\|HG_AUTHORITY_REVOCATION_FILE\|verify_governance_source" /opt/go/runtime/go_runtime/core/ 2>/dev/null | head
echo "== is the running service able to import authority + tool_governance? =="
cd /opt/go && PYTHONPATH=/opt/go python3 -c "
from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError
from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
print('imports OK')
" 2>&1
echo DONE
