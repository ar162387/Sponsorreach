#!/usr/bin/env bash
# Run only on the isolated SponsorReach instance after uploading its release.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl unzip ca-certificates caddy
if ! command -v aws >/dev/null; then
  curl --fail --silent --show-error https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip -o /tmp/awscli.zip
  unzip -q /tmp/awscli.zip -d /tmp/awscli-install
  /tmp/awscli-install/aws/install
  rm -rf /tmp/awscli.zip /tmp/awscli-install
fi
if ! test -x /usr/local/bin/node; then
  curl --fail --silent --show-error https://nodejs.org/dist/v22.15.0/node-v22.15.0-linux-arm64.tar.xz -o /tmp/node.tar.xz
  tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1
  rm /tmp/node.tar.xz
fi
install -d -m 0750 -o root -g sponsorreach /etc/sponsorreach
aws ssm get-parameter --region eu-west-2 --name /sponsorreach/london/runtime --with-decryption --query Parameter.Value --output text > /etc/sponsorreach/runtime.json
chown root:sponsorreach /etc/sponsorreach/runtime.json
chmod 640 /etc/sponsorreach/runtime.json
cd /opt/sponsorreach/app/backend
python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check --no-cache-dir 'torch==2.14.1' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install --disable-pip-version-check --no-cache-dir --no-deps -r ../deploy/requirements-cpu.txt
.venv/bin/pip install --disable-pip-version-check --no-cache-dir --no-deps .
.venv/bin/pip check
cd /opt/sponsorreach/app/web
npm ci --no-audit --no-fund
NODE_OPTIONS=--max-old-space-size=640 NEXT_TELEMETRY_DISABLED=1 npm run build
mkdir -p .next/standalone/.next
cp -r public .next/standalone/
cp -r .next/static .next/standalone/.next/
chown -R sponsorreach:sponsorreach /opt/sponsorreach/app
for kind in api worker web; do
  cat > /etc/systemd/system/sponsorreach-$kind.service <<EOF
[Unit]
Description=SponsorReach $kind
After=network-online.target
Wants=network-online.target
[Service]
User=sponsorreach
Group=sponsorreach
ExecStart=/usr/bin/python3 /opt/sponsorreach/app/deploy/run-service.py $kind
Restart=on-failure
RestartSec=10
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/sponsorreach/app
TasksMax=128
MemoryHigh=700M
MemoryMax=900M
[Install]
WantedBy=multi-user.target
EOF
done
systemctl daemon-reload
# Model/index verification must pass separately before services are enabled.
echo 'Dependencies installed. Awaiting model/index preflight.'
