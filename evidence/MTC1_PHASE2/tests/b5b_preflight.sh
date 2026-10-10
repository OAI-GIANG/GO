#!/usr/bin/env bash
set -u
echo "== helper sha256 (not secret) =="; sha256sum /root/OWNER_PROVISION_AUTHORITY.sh
echo "== 1. deployed authority.py =="
sed -n '1,240p' /opt/go/runtime/go_runtime/core/authority.py
echo "== 2. tool_governance imports =="
sed -n '1,15p' /opt/go/runtime/go_runtime/core/tool_governance.py
echo "== 3. Kernel.authorize / execute_external =="
cd /opt/go && PYTHONPATH=/opt/go python3 - <<'PY'
import inspect
import runtime.go_kernel as k
for n in ("authorize","execute_external"):
    f=getattr(k.Kernel,n,None)
    print("---- Kernel.%s ----" % n)
    print(inspect.getsource(f) if f else "MISSING")
PY
echo "== 4. env keys (NAMES ONLY) =="
echo "-- go-runtime.env keys --"; cut -d= -f1 /etc/go/go-runtime.env | grep -v '^#'
echo "-- unit Environment/ExecStart --"; systemctl cat go-runtime 2>/dev/null | grep -E 'Environment|ExecStart'
echo "== 5. authority prerequisites =="
ls -la /etc/hg/authority 2>&1
echo "root_key_env_set=$(grep -c '^HG_AUTHORITY_ROOT_KEY_FILE=' /etc/go/go-runtime.env)"
echo "revocation_env_set=$(grep -c '^HG_AUTHORITY_REVOCATION_FILE=' /etc/go/go-runtime.env)"
echo "approval.py=$([ -f /opt/go/runtime/go_runtime/core/approval.py ] && echo yes || echo no)  governance_source.py=$([ -f /opt/go/runtime/go_runtime/core/governance_source.py ] && echo yes || echo no)"
echo "== 6. contract GO_RUNTIME_AUTHORITY_V1 =="
cat /opt/go/control/GO_RUNTIME_AUTHORITY_V1.md
echo "== 7. GO state + restart policy =="
ls -la /var/lib/go 2>&1
systemctl show -p Restart -p RestartUSec -p MainPID go-runtime
echo "== 8. helper content =="; cat /root/OWNER_PROVISION_AUTHORITY.sh
echo DONE
