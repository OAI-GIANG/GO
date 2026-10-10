#!/usr/bin/env bash
# Generate MANIFEST.sha256 for this directory and verify the governance patch
# transforms the deployed file into the hardened file byte-exactly.
# (Git's default core.autocrlf can rewrite line endings on apply, so we pin it off.)
set -uo pipefail
E="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python || command -v python3)"

find "$E" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
cd "$E" || exit 9
find . -type f ! -name MANIFEST.sha256 | sort | xargs sha256sum > MANIFEST.sha256
echo "MANIFEST.sha256 written ($(wc -l < MANIFEST.sha256) files)"

V="$(mktemp -d)"; mkdir -p "$V/runtime/go_runtime/toolplane"
cp "$E/patch/hg_tool_plane.original.py" "$V/runtime/go_runtime/toolplane/hg_tool_plane.py"
cd "$V" || exit 9
git init -q .; git config core.autocrlf false
cp "$E/patch/hg_tool_plane.governance.patch" .

git apply --check hg_tool_plane.governance.patch && echo "PATCH_APPLIES=OK" || echo "PATCH_APPLIES=FAIL"
git apply hg_tool_plane.governance.patch
if cmp -s "$V/runtime/go_runtime/toolplane/hg_tool_plane.py" "$E/patch/hg_tool_plane.hardened.py"; then
  echo "PATCH_RESULT_MATCHES_HARDENED=OK"
else
  echo "PATCH_RESULT_MATCHES_HARDENED=FAIL"
fi
