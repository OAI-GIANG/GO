#!/usr/bin/env bash
set -u
echo "== authority artifacts on VPS1 =="
find / -maxdepth 5 \( -iname '*authority*' -o -name 'root.key' -o -iname '*issuer*' \) 2>/dev/null | grep -vE '^/proc|^/sys|/usr/lib|/usr/share/doc' | head -40
echo "== /etc/hg* =="; ls -la /etc/hg /etc/hg-authority /etc/hg-edge 2>/dev/null
echo "== go-runtime.env authority vars (names+emptiness) =="
grep -nE 'AUTHORITY|PROVENANCE|ISSUER|VERIFIER|TOKEN' /etc/go/go-runtime.env 2>/dev/null | sed -E 's/=(.*)$/=<len:\1>/'
echo "== /opt/hg-authority/authority.py (head) =="; sed -n '1,60p' /opt/hg-authority/authority.py
echo "== /authority/health + op surface =="; curl -s -m5 http://127.0.0.1:9098/authority/health; echo
echo "== ledger sample: does it bind governance_source_sha256? =="
grep -c 'governance_source_sha256' /opt/go/data/tool-events.jsonl 2>/dev/null
tail -1 /opt/go/data/tool-events.jsonl 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print(sorted(d.keys()))" 2>/dev/null
echo "== any token/authority files under /root /etc =="
find /root /etc -maxdepth 3 -type f \( -iname '*token*' -o -iname '*authority*' -o -iname '*.key' \) 2>/dev/null | head -20
echo DONE
