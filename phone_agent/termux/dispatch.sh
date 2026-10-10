#!/data/data/com.termux/files/usr/bin/bash
set -eu
op="${1:-}"
case "$op" in
  health) printf '%s\\n' '{"ok":true,"operation":"health"}' ;;
  runtime_status) printf '%s\\n' '{"ok":true,"operation":"runtime_status"}' ;;
  *) printf '%s\\n' '{"ok":false,"error":"CAPABILITY_DENIED"}' >&2; exit 126 ;;
esac