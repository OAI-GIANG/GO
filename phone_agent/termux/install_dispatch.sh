#!/data/data/com.termux/files/usr/bin/bash
# Install the fixed Phone Agent v2 dispatcher and isolated repository workspace.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
EXPECTED_BRANCH="feature/phone-agent-v2-fileops"
EXPECTED_ORIGIN="https://github.com/OAI-GIANG/GO.git"
TARGET_DIR="$HOME/hg-agent"
TARGET="$TARGET_DIR/dispatch.sh"
WORKSPACE="$HOME/.cache/hg-phone-agent/workspaces/GO"
STATE_DIR="$HOME/.cache/hg-phone-agent/state"

[ -f "$REPO_ROOT/runtime/go_runtime/core/phone_fileops.py" ] || { echo '{"ok":false,"error":{"code":"PHONE_FILEOPS_SOURCE_MISSING"}}'; exit 2; }
[ -f "$REPO_ROOT/phone_agent/termux/dispatch_v2.sh" ] || { echo '{"ok":false,"error":{"code":"DISPATCH_SOURCE_MISSING"}}'; exit 2; }
BRANCH="$(git -C "$REPO_ROOT" branch --show-current)"
[ "$BRANCH" = "$EXPECTED_BRANCH" ] || { echo '{"ok":false,"error":{"code":"UNEXPECTED_BRANCH"}}'; exit 3; }
ORIGIN="$(git -C "$REPO_ROOT" remote get-url origin)"
[ "$ORIGIN" = "$EXPECTED_ORIGIN" ] || { echo '{"ok":false,"error":{"code":"UNEXPECTED_ORIGIN"}}'; exit 3; }

mkdir -p "$TARGET_DIR" "$(dirname "$WORKSPACE")" "$STATE_DIR"
if [ -e "$WORKSPACE" ]; then
  [ "$(git -C "$WORKSPACE" rev-parse --show-toplevel 2>/dev/null)" = "$WORKSPACE" ] || {
    echo '{"ok":false,"error":{"code":"WORKSPACE_PATH_EXISTS_NOT_GIT_WORKTREE"}}'; exit 5;
  }
  [ "$(git -C "$WORKSPACE" remote get-url origin 2>/dev/null)" = "$EXPECTED_ORIGIN" ] || {
    echo '{"ok":false,"error":{"code":"WORKSPACE_ORIGIN_MISMATCH"}}'; exit 5;
  }
else
  git -C "$REPO_ROOT" worktree add --detach "$WORKSPACE" HEAD >/dev/null
fi

if [ -e "$TARGET" ] && ! grep -q 'HG_PHONE_AGENT_V2_DISPATCH_WRAPPER_V1' "$TARGET"; then
  echo '{"ok":false,"error":{"code":"TARGET_EXISTS_NOT_OWNED_BY_INSTALLER"}}'; exit 4
fi
TMP="$(mktemp "$TARGET_DIR/.dispatch.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
cat > "$TMP" <<'WRAPPER'
#!/data/data/com.termux/files/usr/bin/bash
# HG_PHONE_AGENT_V2_DISPATCH_WRAPPER_V1
set -euo pipefail
REPO_ROOT="@@{HG_PHONE_REPO_ROOT:-$HOME/GO-pa2}"
SOURCE="$REPO_ROOT/phone_agent/termux/dispatch_v2.sh"
CORE_DIR="$REPO_ROOT/runtime/go_runtime/core"
WORKSPACE="@@{HG_PHONE_SANDBOX:-$HOME/.cache/hg-phone-agent/workspaces/GO}"
REPLAY_LOG="@@{HG_PHONE_REPLAY_LOG:-$HOME/.cache/hg-phone-agent/state/replay.jsonl}"
REQ="@@{1:-}"
if [ -z "$REQ" ]; then
  printf '%s\n' '{"ok":false,"error":{"code":"MISSING_REQUEST"}}'
  exit 2
fi
if [ ! -f "$SOURCE" ] || [ ! -f "$CORE_DIR/phone_fileops.py" ] || [ ! -d "$WORKSPACE" ]; then
  printf '%s\n' '{"ok":false,"error":{"code":"DISPATCH_DEPENDENCY_MISSING"}}'
  exit 2
fi
mkdir -p "$(dirname "$REPLAY_LOG")"
printf '%s\n' "$REQ" | HG_PHONE_CORE_DIR="$CORE_DIR" HG_PHONE_SANDBOX="$WORKSPACE" HG_PHONE_REPLAY_LOG="$REPLAY_LOG" /data/data/com.termux/files/usr/bin/bash "$SOURCE"
WRAPPER
python - "$TMP" <<'PY2'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
s=s.replace("@@{", "$" + "{")
p.write_text(s)
PY2
chmod 700 "$TMP"
mv -f "$TMP" "$TARGET"
trap - EXIT
printf '{"ok":true,"target":"%s","workspace":"%s","branch":"%s"}\n' "$TARGET" "$WORKSPACE" "$BRANCH"
