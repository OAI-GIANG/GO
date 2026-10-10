#!/data/data/com.termux/files/usr/bin/bash
# Phone Agent v2 dispatcher — CHỈ định tuyến tới capability allowlist qua module canonical.
# KHÔNG arbitrary shell. Đầu vào: JSON 1 dòng trên stdin. Đầu ra: JSON 1 dòng.
set -uo pipefail
CORE_DIR="${HG_PHONE_CORE_DIR:-$HOME/GO-pa2/runtime/go_runtime/core}"
SANDBOX="${HG_PHONE_SANDBOX:-$HOME/.cache/hg-phone-agent/sandbox}"
REQ="$(cat)"
[ -z "$REQ" ] && { echo '{"ok":false,"error":{"code":"EMPTY_REQUEST"}}'; exit 2; }
HG_PHONE_SANDBOX="$SANDBOX" python3 - "$CORE_DIR" "$REQ" <<'PY'
import json, sys, pathlib
core, raw = sys.argv[1], sys.argv[2]
sys.path.insert(0, core)
try:
    from phone_fileops import PhoneFileOps
except Exception as e:
    print(json.dumps({"ok": False, "error": {"code": "CORE_IMPORT_FAILED", "detail": type(e).__name__}})); raise SystemExit(0)
try:
    req = json.loads(raw)
except Exception:
    print(json.dumps({"ok": False, "error": {"code": "INVALID_JSON"}})); raise SystemExit(0)
ops = PhoneFileOps()
print(json.dumps(ops.handle(req), ensure_ascii=False))
PY
