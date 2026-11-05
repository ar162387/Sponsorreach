"""Timer entry point. Read secrets from the existing private runtime file; never log them."""
import json
import urllib.request
from pathlib import Path
settings=json.loads(Path('/etc/sponsorreach/runtime.json').read_text())
secret=settings.get('BILLING_RECONCILE_SECRET','')
if len(secret)<32:raise SystemExit('Billing reconciliation secret not configured')
request=urllib.request.Request('http://127.0.0.1:3000/api/internal/billing/reconcile',method='POST',data=b'{}',headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(request,timeout=240) as response:result=json.load(response)
    if result.get('errors'):raise SystemExit('Billing reconciliation has pending items; review administrator status')
    print('Billing reconciliation complete')
except Exception as exc:raise SystemExit('Billing reconciliation failed: '+type(exc).__name__) from None
