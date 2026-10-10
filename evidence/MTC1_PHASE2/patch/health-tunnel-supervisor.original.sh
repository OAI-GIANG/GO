#!/data/data/com.termux/files/usr/bin/bash
# Supervisor health-only tunnel: wake-lock + phát hiện chết + restart. KHÔNG phải tunnel quyền rộng:
# chỉ chạy health-tunnel.py (allowlist đúng 1 endpoint /api/health). PID hygiene bằng /proc/cmdline.
set -uo pipefail
TUN="${1:-/sdcard/HG-GO-DEPLOY/health-tunnel.py}"
LOG="$HOME/health-tunnel.log"
hg_scan() {
  HG_N=0
  for d in /proc/[0-9]*; do
    [ -r "$d/cmdline" ] || continue
    _p=${d#/proc/}; [ "$_p" = "$$" ] && continue
    _a0=$(tr '\0' '\n' < "$d/cmdline" 2>/dev/null | sed -n 1p)
    case "$_a0" in *python*) ;; *) continue ;; esac
    if tr '\0' '\n' < "$d/cmdline" 2>/dev/null | grep -q "/$1\$"; then HG_N=$((HG_N+1)); fi
  done
}
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock && echo "[sup] wake-lock ON"
echo "[sup] start $(date -u +%FT%TZ) tunnel=$TUN" >> "$LOG"
while true; do
  hg_scan health-tunnel.py
  if [ "$HG_N" -eq 0 ]; then
    echo "[sup] $(date -u +%FT%TZ) tunnel chết → restart" >> "$LOG"
    nohup python3 "$TUN" >> "$LOG" 2>&1 &
  elif [ "$HG_N" -gt 1 ]; then
    echo "[sup] $(date -u +%FT%TZ) ⚠ $HG_N tiến trình khớp → FAIL-CLOSED, không restart" >> "$LOG"
  fi
  sleep 30
done
