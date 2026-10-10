#!/usr/bin/env bash
set -u
TS=$(date -u +%Y%m%dT%H%M%SZ)
CFG=/etc/nginx/sites-available/hg-edge
cp -a "$CFG" "$CFG.bak-$TS"
echo "backup: $CFG.bak-$TS"
python3 - "$CFG" <<'PY'
import sys
p=sys.argv[1]
s=open(p).read()
old="server { listen 80; listen [::]:80; server_name 160.191.242.198; return 301 https://$host$request_uri; }"
new="""server {
    listen 80; listen [::]:80; server_name 160.191.242.198;
    location ^~ /.well-known/acme-challenge/ { root /var/www/acme; default_type text/plain; }
    location / { return 301 https://$host$request_uri; }
}"""
if old not in s:
    print("PATTERN_NOT_FOUND"); sys.exit(3)
open(p,"w").write(s.replace(old,new,1))
print("patched")
PY
rc=$?
if [ $rc -ne 0 ]; then echo "PATCH_FAILED rc=$rc"; exit $rc; fi
echo "== nginx -t =="
if ! nginx -t; then echo "NGINX_TEST_FAILED -> restoring"; cp -a "$CFG.bak-$TS" "$CFG"; nginx -t; exit 4; fi
systemctl reload nginx && echo "reloaded"
mkdir -p /var/www/acme/.well-known/acme-challenge
echo "acme-probe-ok" > /var/www/acme/.well-known/acme-challenge/probe
echo "== challenge fetch (http) =="
curl -s -o /dev/null -w 'HTTP /var/www/acme probe: %{http_code}\n' http://160.191.242.198/.well-known/acme-challenge/probe
curl -s -m5 http://160.191.242.198/.well-known/acme-challenge/probe; echo
echo "== redirect still works =="
curl -s -o /dev/null -w 'HTTP /: %{http_code}\n' http://160.191.242.198/
rm -f /var/www/acme/.well-known/acme-challenge/probe
echo DONE
