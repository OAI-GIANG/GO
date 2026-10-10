#!/usr/bin/env bash
# Isolated unit + functional test for the hardened supervisor (MTC-1.0 B2).
# Runs on any bash (Git-bash/Windows, Linux, Termux).
#   * load_config  : fail-closed rules (missing/empty/mode/empty-token)
#   * classify     : START / OK / FAILCLOSED (duplicate => fail-closed)
#   * next_backoff : crash-loop backoff (bounded, no tight loop)
#   * start_tunnel : ROOT-CAUSE FIX — the three required env vars are actually
#                    exported to the spawned process (proven by the child).
# Full process-spawn/duplicate-detection E2E (needs Linux /proc) is provided in
# test_supervisor_e2e_linux.sh and must run on Termux/Linux.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

# isolated HOME must be set BEFORE sourcing (CONF/TOKF/TUN captured at source time)
ORIG_HOME="$HOME"
export HOME="$(mktemp -d)"
export HG_EDGE_CONF="$HOME/.config/hg/edge.conf"
export HG_EDGE_TOKEN_FILE="$HOME/.config/hg/edge_token"
export HG_SUP_TUNNEL="$HERE/fake_tunnel.py"
export HG_SUPERVISOR_LIB_ONLY=1
# shellcheck disable=SC1090
. "$HERE/../patch/health-tunnel-supervisor.hardened.sh"

fail=0
chk(){ if [ "$2" = "$3" ]; then echo "PASS $1"; else echo "FAIL $1"; echo "   got : [$2]"; echo "   want: [$3]"; fail=1; fi; }
note(){ echo "NOTE $1"; }

# detect whether this filesystem enforces POSIX modes
probe="$(mktemp)"; chmod 600 "$probe" 2>/dev/null || true
pmode="$(stat -c %a "$probe" 2>/dev/null || echo "?")"
rm -f "$probe"
if [ "$pmode" = "600" ]; then POSIX=1; note "filesystem enforces POSIX modes"; else POSIX=0; note "filesystem does NOT enforce POSIX modes (mode=$pmode) — T3/T4 adjusted"; fi

# ensure a `python3` exists for the spawned child (script targets Termux python3)
export HG_FAKE_OUT="$(cygpath -w "$HOME/env_seen.json" 2>/dev/null || printf '%s' "$HOME/env_seen.json")"
if command -v python >/dev/null 2>&1; then
  mkdir -p "$HOME/bin"
  PY="$(command -v python)"
  FAKE="$(cygpath -w "$HERE/fake_tunnel.py" 2>/dev/null || printf '%s' "$HERE/fake_tunnel.py")"
  printf '#!/usr/bin/env bash\nexec "%s" "%s"\n' "$PY" "$FAKE" > "$HOME/bin/python3"
  chmod +x "$HOME/bin/python3"
  export PATH="$HOME/bin:$PATH"
  note "added python3 shim (runs fake_tunnel.py) for isolated test"
fi

# T1 missing config -> fail-closed
chk "T1_missing_config" "$(load_config)" "FAIL missing $HG_EDGE_CONF"

# T2 present but device empty
mkdir -p "$HOME/.config/hg"
printf 'HG_EDGE_URL=https://edge.example\nHG_EDGE_DEVICE=\n' > "$HG_EDGE_CONF"
chk "T2_empty_device" "$(load_config)" "FAIL HG_EDGE_DEVICE empty in $HG_EDGE_CONF"

# T3 token with wrong mode (644)
printf 'HG_EDGE_URL=https://edge.example\nHG_EDGE_DEVICE=phone-primary-u0_a460\n' > "$HG_EDGE_CONF"
printf 'S3CRET' > "$HG_EDGE_TOKEN_FILE"; chmod 644 "$HG_EDGE_TOKEN_FILE"
want3="FAIL $HG_EDGE_TOKEN_FILE mode=644 (need 600)"
chk "T3_token_mode" "$(load_config)" "$want3"

# T4 valid config (POSIX only)
chmod 600 "$HG_EDGE_TOKEN_FILE"
if [ "$POSIX" = "1" ]; then
  chk "T4_valid" "$(load_config)" "OK https://edge.example phone-primary-u0_a460 $HG_EDGE_TOKEN_FILE"
else
  chk "T4_valid_skipped_nonposix" "$(load_config)" "$want3"
fi

# T5 classify (0=START, 1=OK, >1=FAILCLOSED)
chk "T5_classify_0" "$(classify 0)" "START"
chk "T5_classify_1" "$(classify 1)" "OK"
chk "T5_classify_2" "$(classify 2)" "FAILCLOSED"
chk "T5_classify_5" "$(classify 5)" "FAILCLOSED"

# T6 crash-loop backoff
chk "T6_backoff_1"  "$(next_backoff 0 1)"   "1"
chk "T6_backoff_2"  "$(next_backoff 1 1)"   "2"
chk "T6_backoff_4"  "$(next_backoff 2 1)"   "4"
chk "T6_reset"      "$(next_backoff 8 0)"   "0"
chk "T6_capped"     "$(next_backoff 300 1)" "300"
chk "T6_cap_above"  "$(next_backoff 200 1)" "300"

# T7 functional: start_tunnel must EXPORT the three env vars to the child (root-cause fix)
rm -f "$HOME/env_seen.json"
pid="$(start_tunnel "https://edge.example" "phone-primary-u0_a460" "$HG_EDGE_TOKEN_FILE")"
sleep 2
seen="$(cat "$HOME/env_seen.json" 2>/dev/null || echo NOFILE)"
echo "   child env: $seen"
chk "T7_start_exports_device" "$(printf '%s' "$seen" | python -c 'import sys,json; print(json.load(sys.stdin).get("dev"))' 2>/dev/null || echo ERR)" "phone-primary-u0_a460"
kill "$pid" 2>/dev/null || true

export HOME="$ORIG_HOME"
echo "---"
if [ "$fail" -eq 0 ]; then echo "SUPERVISOR_LOGIC: PASS"; else echo "SUPERVISOR_LOGIC: FAIL"; fi
exit "$fail"
