#!/usr/bin/env bash
set -u
F=/etc/go/go-runtime.env
TS=$(date -u +%Y%m%dT%H%M%SZ)
cp -a "$F" "$F.bak-$TS"; echo "backup: $F.bak-$TS"
python3 - "$F" <<'PY'
import sys, re, secrets
p = sys.argv[1]
s = open(p).read()
new = secrets.token_hex(32)
s2, n = re.subn(r'(?m)^GO_API_TOKEN=.*$', 'GO_API_TOKEN=' + new, s)
assert n == 1, f"lines matched={n}"
open(p, 'w').write(s2)
print("rotated: GO_API_TOKEN replaced (value not printed)")
PY
chmod 600 "$F"
systemctl restart go-runtime
sleep 3
echo -n "service: "; systemctl is-active go-runtime
echo -n "healthz: "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8877/healthz
NEW=$(grep -m1 '^GO_API_TOKEN=' "$F" | cut -d= -f2-)
echo -n "status(new token): "; curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $NEW" http://127.0.0.1:8877/v1/status
echo -n "status(no token): "; curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8877/v1/status
echo -n "status(exposed old token now invalid): "; curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer e1439fc4e65625248d2c9e9db289b172a31f6caf97cf97ac" http://127.0.0.1:8877/v1/status
echo DONE
