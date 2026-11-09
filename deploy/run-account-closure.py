"""Run the private account-closure queue through the existing web service."""
import json
from pathlib import Path
import urllib.request

runtime = json.loads(Path('/etc/sponsorreach/runtime.json').read_text())
secret = runtime.get('SPONSORREACH_CLOSURE_JOB_SECRET', '')
if len(secret) < 32:
    raise SystemExit('Account closure job secret is not configured')
request = urllib.request.Request(
    'http://127.0.0.1:3000/api/internal/account-closure',
    data=b'{}', method='POST', headers={'Authorization': 'Bearer ' + secret},
)
try:
    with urllib.request.urlopen(request, timeout=245) as response:
        result = json.load(response)
except Exception as exc:
    raise SystemExit('Account closure processing failed: ' + type(exc).__name__) from None
if result['pending']:
    raise SystemExit('Account closure processing has retryable work')
print('Account closure processing complete')
