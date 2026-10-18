#!/usr/bin/env bash
set -eu
cat > /etc/systemd/system/sponsorreach-retention.service <<'EOF'
[Unit]
Description=Remove expired SponsorReach profiles and match sessions
After=network-online.target
[Service]
Type=oneshot
User=sponsorreach
Group=sponsorreach
ExecStart=/usr/bin/python3 /opt/sponsorreach/app/deploy/run-service.py purge
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
EOF
cat > /etc/systemd/system/sponsorreach-retention.timer <<'EOF'
[Unit]
Description=Daily SponsorReach retention maintenance
[Timer]
OnCalendar=daily
RandomizedDelaySec=30m
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now sponsorreach-retention.timer
