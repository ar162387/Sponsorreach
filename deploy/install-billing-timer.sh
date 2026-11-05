#!/bin/sh
set -eu
cat > /etc/systemd/system/sponsorreach-billing-reconcile.service <<'EOF'
[Unit]
Description=SponsorReach payment and credit reconciliation
After=network-online.target sponsorreach-web.service
[Service]
Type=oneshot
User=sponsorreach
Group=sponsorreach
ExecStart=/usr/bin/python3 /opt/sponsorreach/app/deploy/reconcile-billing.py
TimeoutStartSec=270
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
EOF
cat > /etc/systemd/system/sponsorreach-billing-reconcile.timer <<'EOF'
[Unit]
Description=Reconcile SponsorReach payments every five minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now sponsorreach-billing-reconcile.timer
