#!/usr/bin/env bash
# Start only after install-london.sh succeeds; ingress remains separately controlled.
set -eu
aws ssm get-parameter --region eu-west-2 --name /sponsorreach/london/runtime --with-decryption --query Parameter.Value --output text > /etc/sponsorreach/runtime.json
chown root:sponsorreach /etc/sponsorreach/runtime.json
chmod 640 /etc/sponsorreach/runtime.json
sudo -u sponsorreach /opt/sponsorreach/app/backend/.venv/bin/python /opt/sponsorreach/app/deploy/preflight.py
systemctl enable --now sponsorreach-api sponsorreach-worker sponsorreach-web
python3 - <<'PY'
import json
from pathlib import Path
from urllib.parse import urlparse
origin = json.loads(Path('/etc/sponsorreach/runtime.json').read_text())['APP_ORIGIN']
host = urlparse(origin).hostname
assert host and all(c.isalnum() or c in '.-' for c in host)
private_preview = ' header X-Robots-Tag \"noindex, nofollow\"\n' if host.endswith('.sslip.io') else ''
Path('/etc/caddy/Caddyfile').write_text(host + ' {\n encode gzip\n' + private_preview + ' reverse_proxy 127.0.0.1:3000\n}\n')
PY
caddy validate --config /etc/caddy/Caddyfile
systemctl enable caddy
systemctl restart caddy
echo 'Services started; verify private readiness before opening HTTP/HTTPS ingress.'
