#!/bin/sh
set -eu
cat > /etc/systemd/system/sponsorreach-register-refresh.service <<'EOF'
[Unit]
Description=Refresh the GOV.UK sponsor register used by SponsorReach
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=sponsorreach
Group=sponsorreach
ExecStart=/usr/bin/python3 /opt/sponsorreach/app/deploy/run-service.py register-refresh
StateDirectory=sponsorreach-register
TimeoutStartSec=10min
UMask=0077
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
EOF
cat > /etc/systemd/system/sponsorreach-register-refresh.timer <<'EOF'
[Unit]
Description=Check the SponsorReach register age each day
[Timer]
OnCalendar=*-*-* 05:30:00 Europe/London
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now sponsorreach-register-refresh.timer
