"""Load the private runtime JSON without evaluating shell expressions."""
import json
import os
from pathlib import Path
import sys

os.environ.update(json.loads(Path('/etc/sponsorreach/runtime.json').read_text()))
commands = {
    'api': ['/opt/sponsorreach/app/backend/.venv/bin/uvicorn', 'sponsor_match.api:app', '--host', '127.0.0.1', '--port', '8001', '--workers', '1'],
    'worker': ['/opt/sponsorreach/app/backend/.venv/bin/sponsormatch', 'worker', '--concurrency', '1'],
    'web': ['/usr/local/bin/node', '/opt/sponsorreach/app/web/.next/standalone/server.js'],
}
os.chdir('/opt/sponsorreach/app/backend' if sys.argv[1] != 'web' else '/opt/sponsorreach/app/web')
os.execv(commands[sys.argv[1]][0], commands[sys.argv[1]])
