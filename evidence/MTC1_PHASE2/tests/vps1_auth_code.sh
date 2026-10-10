#!/usr/bin/env bash
set -u
echo "== deployed tool_governance._authority (VPS1) =="
python3 - <<'PY'
import inspect
import sys; sys.path.insert(0,"/opt/go")
from runtime.go_runtime.core import tool_governance as tg
src = inspect.getsource(tg.ToolGovernance._authority)
print(src)
PY
echo "== deployed authority._load / issue =="
python3 - <<'PY'
import inspect, sys; sys.path.insert(0,"/opt/go")
from runtime.go_runtime.core import authority as a
print(inspect.getsource(a.AuthorityRoot._load))
print(inspect.getsource(a.AuthorityRoot.issue))
PY
echo "== who uses GO_API_TOKEN / root.key =="
grep -rslE 'GO_API_TOKEN' /etc/systemd /opt /usr/local 2>/dev/null | head
grep -rslE 'HG_AUTHORITY_ROOT_KEY_FILE|/etc/hg/authority/root.key' /opt /etc 2>/dev/null | head
echo "== /etc/hg/authority present? =="; ls -la /etc/hg/authority 2>&1
echo DONE
