#!/data/data/com.termux/files/usr/bin/bash
# HG health-tunnel supervisor (HARDENED) — MTC-1.0 B2
# ---------------------------------------------------------------------------
# Fixes the observed restart loop. Root cause: the previous supervisor launched
# `python3 health-tunnel.py` WITHOUT exporting HG_EDGE_URL / HG_EDGE_DEVICE /
# HG_EDGE_TOKEN_FILE. health-tunnel.py is fail-closed and exits immediately with
# BLOCKED_DEVICE_ID_UNSET / BLOCKED_EDGE_OR_TOKEN_ABSENT, so the supervisor span
# a broken process every 30s (no tunnel ever stayed up; last served request
# 2026-10-10T00:38:59Z despite the supervisor running).
#
# Changes:
#   1. Load edge config from ~/.config/hg/edge.conf + edge_token (parsed as DATA,
#      never sourced/eval'd) and EXPORT the three required variables to the child.
#   2. Fail-closed at startup (exit 2) with a clear message if config is missing,
#      instead of respawning a process that cannot start.
#   3. Crash-loop backoff (mirrors runit runsv "wait a second on immediate exit"
#      semantics, with exponential growth up to HG_SUP_MAXBACKOFF). Bounded, no
#      tight loop.
#   4. Keep PID hygiene via /proc/<pid>/cmdline exact argv match; more than one
#      match => FAIL-CLOSED (no restart, no kill). Never creates duplicates.
#
# Environment overrides (all optional):
#   HG_SUP_TUNNEL, HG_SUP_LOG, HG_SUP_SLEEP, HG_SUP_GRACE,
#   HG_SUP_MAXBACKOFF, HG_EDGE_CONF, HG_EDGE_TOKEN_FILE
#   HG_SUPERVISOR_LIB_ONLY=1  -> source-only mode for isolated unit tests
# No token value is ever written to the log. No token inline in code.
set -uo pipefail

TUN="${HG_SUP_TUNNEL:-${1:-/sdcard/HG-GO-DEPLOY/health-tunnel.py}}"
CONF="${HG_EDGE_CONF:-$HOME/.config/hg/edge.conf}"
TOKF="${HG_EDGE_TOKEN_FILE:-$HOME/.config/hg/edge_token}"
LOG="${HG_SUP_LOG:-$HOME/health-tunnel.log}"
SLEEP="${HG_SUP_SLEEP:-30}"
GRACE="${HG_SUP_GRACE:-3}"
MAXBACKOFF="${HG_SUP_MAXBACKOFF:-300}"

log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$1" >> "$LOG" 2>/dev/null; }

getdata(){ grep -m1 "^$1=" "$CONF" 2>/dev/null | cut -d= -f2- | tr -d '\r'; }

# Prints "OK <url> <dev> <tokfile>" or "FAIL <reason>"; returns 2 on FAIL.
load_config(){
  [ -f "$CONF" ] || { echo "FAIL missing $CONF"; return 2; }
  local url dev m
  url="$(getdata HG_EDGE_URL)"; dev="$(getdata HG_EDGE_DEVICE)"
  [ -n "$url" ] || { echo "FAIL HG_EDGE_URL empty in $CONF"; return 2; }
  [ -n "$dev" ] || { echo "FAIL HG_EDGE_DEVICE empty in $CONF"; return 2; }
  [ -f "$TOKF" ] || { echo "FAIL missing $TOKF"; return 2; }
  m="$(stat -c %a "$TOKF" 2>/dev/null || true)"
  case "$m" in 600|400) ;; *) echo "FAIL $TOKF mode=$m (need 600)"; return 2;; esac
  [ -s "$TOKF" ] || { echo "FAIL $TOKF empty"; return 2; }
  echo "OK $url $dev $TOKF"
}

# Count python processes whose argv0 mentions python and whose argv ends with /<name>.
scan_matches(){
  local name="$1" n=0 d p a0
  for d in /proc/[0-9]*; do
    [ -r "$d/cmdline" ] || continue
    p="${d#/proc/}"; [ "$p" = "$$" ] && continue
    a0="$(tr '\0' '\n' < "$d/cmdline" 2>/dev/null | sed -n 1p)"
    case "$a0" in *python*) ;; *) continue;; esac
    if tr '\0' '\n' < "$d/cmdline" 2>/dev/null | grep -q "/$name\$"; then n=$((n+1)); fi
  done
  echo "$n"
}

classify(){ case "$1" in 0) echo START;; 1) echo OK;; *) echo FAILCLOSED;; esac; }

next_backoff(){ # $1=prev $2=died_fast(0/1) -> new backoff seconds
  if [ "$2" -eq 1 ]; then
    local n=$(( $1 > 0 ? $1 * 2 : 1 ))
    [ "$n" -gt "$MAXBACKOFF" ] && n="$MAXBACKOFF"
    echo "$n"
  else echo 0; fi
}

start_tunnel(){ # url dev tokfile -> pid
  export HG_EDGE_URL="$1" HG_EDGE_DEVICE="$2" HG_EDGE_TOKEN_FILE="$3"
  nohup python3 "$TUN" >> "$LOG" 2>&1 &
  echo $!
}

main(){
  local cfg rc n pid backoff=0
  cfg="$(load_config)"; rc=$?
  if [ "$rc" -ne 0 ]; then
    log "[sup] FAIL-CLOSED config: ${cfg#FAIL }"
    echo "ABORT: ${cfg#FAIL }" >&2
    exit 2
  fi
  # shellcheck disable=SC2086
  set -- $cfg   # -> $1=OK $2=url $3=dev $4=tokfile
  local URL="$2" DEV="$3" TOKEN="$4"
  command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
  log "[sup] start tunnel=$TUN device=$DEV"
  while true; do
    n="$(scan_matches health-tunnel.py)"
    case "$(classify "$n")" in
      FAILCLOSED) log "[sup] FAIL-CLOSED $n matches -> no restart, no kill";;
      OK) backoff=0;;
      START)
        pid="$(start_tunnel "$URL" "$DEV" "$TOKEN")"
        log "[sup] started pid=$pid backoff=${backoff}s"
        sleep "$GRACE"
        if kill -0 "$pid" 2>/dev/null; then
          backoff=0
          log "[sup] tunnel alive pid=$pid"
        else
          backoff="$(next_backoff "$backoff" 1)"
          [ "$backoff" -eq "$MAXBACKOFF" ] && log "[sup] CRASH_LOOP backoff capped ${backoff}s"
          log "[sup] tunnel died fast -> backoff ${backoff}s"
          sleep "$backoff"
        fi
        ;;
    esac
    sleep "$SLEEP"
  done
}

if [ "${HG_SUPERVISOR_LIB_ONLY:-0}" = "1" ]; then
  return 0 2>/dev/null || exit 0
fi
main
