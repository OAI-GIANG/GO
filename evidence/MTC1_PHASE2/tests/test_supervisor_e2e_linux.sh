#!/usr/bin/env bash
# E2E harness for the hardened supervisor. REQUIRES Linux /proc semantics.
# NOT executed by MTC-1.0 on the Windows host (no Linux /proc); run on Termux/Linux.
#
#   Termux/Linux:  bash evidence/MTC1_PHASE2/tests/test_supervisor_e2e_linux.sh
#
# Cases:
#   A missing config        -> supervisor exits 2, spawns nothing
#   B healthy tunnel        -> exactly 1 tunnel stays up (no restart flap)
#   C crashing tunnel       -> backoff grows, never more than 1 at a time (no tight loop)
#   D duplicate tunnels     -> FAIL-CLOSED, no restart, no kill
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SUP="$HERE/../patch/health-tunnel-supervisor.hardened.sh"
FAKE="$HERE/fake_tunnel_linux.py"
fail=0; msg(){ echo "$1"; [ "$1" = FAIL* ] && fail=1 || true; }

count(){ local n=0 d a0; for d in /proc/[0-9]*; do [ -r "$d/cmdline" ] || continue; a0="$(tr '\0' '\n' < "$d/cmdline" 2>/dev/null | sed -n 1p)"; case "$a0" in *python*) ;; *) continue;; esac; tr '\0' '\n' < "$d/cmdline" 2>/dev/null | grep -q "/health-tunnel.py\$" && n=$((n+1)); done; echo "$n"; }
mkcfg(){ local h="$1"; mkdir -p "$h/.config/hg"; printf 'HG_EDGE_URL=https://edge.example\nHG_EDGE_DEVICE=dev-e2e\n' > "$h/.config/hg/edge.conf"; printf 's3cret' > "$h/.config/hg/edge_token"; chmod 600 "$h/.config/hg/edge_token"; cp "$FAKE" "$h/health-tunnel.py"; }

# A: missing config
H="$(mktemp -d)"; env -i HOME="$H" HG_SUP_TUNNEL="$H/health-tunnel.py" bash "$SUP" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 2 ] && echo "PASS A missing-config exit=2" || msg "FAIL A rc=$rc"

# B: healthy
H="$(mktemp -d)"; mkcfg "$H"
env HOME="$H" HG_FAKE_MODE=healthy HG_FAKE_OUT="$H/out" HG_SUP_TUNNEL="$H/health-tunnel.py" HG_SUP_SLEEP=2 HG_SUP_GRACE=1 HG_SUP_LOG="$H/log" bash "$SUP" >/dev/null 2>&1 & SP=$!
sleep 6; c="$(count)"; kill "$SP" 2>/dev/null; pkill -f "$H/health-tunnel.py" 2>/dev/null; sleep 1
[ "$c" -eq 1 ] && echo "PASS B healthy count=1" || msg "FAIL B count=$c"

# C: crashing -> no tight loop / no accumulation
H="$(mktemp -d)"; mkcfg "$H"
env HOME="$H" HG_FAKE_MODE=crash HG_FAKE_OUT="$H/out" HG_SUP_TUNNEL="$H/health-tunnel.py" HG_SUP_SLEEP=2 HG_SUP_GRACE=1 HG_SUP_MAXBACKOFF=4 HG_SUP_LOG="$H/log" bash "$SUP" >/dev/null 2>&1 & SP=$!
sleep 12; c="$(count)"; kill "$SP" 2>/dev/null; pkill -f "$H/health-tunnel.py" 2>/dev/null; sleep 1
grep -q "backoff" "$H/log" 2>/dev/null && echo "PASS C backoff observed" || msg "FAIL C no backoff log"
[ "$c" -le 1 ] && echo "PASS C no accumulation (c=$c)" || msg "FAIL C accumulated c=$c"

# D: duplicates -> fail-closed
H="$(mktemp -d)"; mkcfg "$H"
env HOME="$H" HG_FAKE_MODE=healthy HG_FAKE_OUT="$H/out" python3 "$H/health-tunnel.py" & D1=$!
python3 "$H/health-tunnel.py" & D2=$!
sleep 1; before="$(count)"
env HOME="$H" HG_FAKE_MODE=healthy HG_FAKE_OUT="$H/out" HG_SUP_TUNNEL="$H/health-tunnel.py" HG_SUP_SLEEP=2 HG_SUP_LOG="$H/log" bash "$SUP" >/dev/null 2>&1 & SP=$!
sleep 5; after="$(count)"; kill "$SP" $D1 $D2 2>/dev/null; pkill -f "$H/health-tunnel.py" 2>/dev/null
grep -q "FAIL-CLOSED" "$H/log" 2>/dev/null && echo "PASS D fail-closed logged" || msg "FAIL D no fail-closed log"
[ "$after" -eq "$before" ] && echo "PASS D no new process (before=$before after=$after)" || msg "FAIL D before=$before after=$after"

echo "---"; [ "$fail" -eq 0 ] && echo "SUPERVISOR_E2E_LINUX: PASS" || echo "SUPERVISOR_E2E_LINUX: FAIL"
exit "$fail"
