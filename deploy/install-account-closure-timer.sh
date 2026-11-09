#!/bin/sh
set -eu
cat > /etc/systemd/system/sponsorreach-account-closure.service <<'UNIT'
[Unit]
Description=Process SponsorReach account deletion requests
After=network-online.target sponsorreach-web.service
[Service]
Type=oneshot
User=sponsorreach
Group=sponsorreach
ExecStart=/usr/bin/python3 /opt/sponsorreach/app/deploy/run-account-closure.py
TimeoutStartSec=260
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
UNIT
cat > /etc/systemd/system/sponsorreach-account-closure.timer <<'UNIT'
[Unit]
Description=Retry SponsorReach account closure and purge due accounts
[Timer]
OnBootSec=2min
OnCalendar=*:0/5
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now sponsorreach-account-closure.timer
