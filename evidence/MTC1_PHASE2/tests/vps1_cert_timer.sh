#!/usr/bin/env bash
set -u
cat > /etc/systemd/system/certbot-renew.service <<'EOF'
[Unit]
Description=Certbot renewal (HG edge, webroot)
[Service]
Type=oneshot
ExecStart=/opt/certbot/bin/certbot renew --quiet
EOF
cat > /etc/systemd/system/certbot-renew.timer <<'EOF'
[Unit]
Description=Run certbot renew twice daily (HG edge)
[Timer]
OnCalendar=*-*-* 00,12:17:00
RandomizedDelaySec=3600
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now certbot-renew.timer 2>&1 | tail -2
echo "== timer =="; systemctl list-timers certbot-renew.timer --no-pager 2>&1 | head -4
echo "== manual service run (idempotent) =="; systemctl start certbot-renew.service; sleep 2; systemctl is-active certbot-renew.service; journalctl -u certbot-renew.service -n 8 --no-pager 2>&1 | tail -6
echo "== cert now =="; openssl x509 -in /etc/letsencrypt/live/160.191.242.198/cert.pem -noout -enddate
echo DONE
