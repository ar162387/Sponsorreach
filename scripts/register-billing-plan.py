"""Register a new immutable plan version from operator-reviewed provider output."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend/src'))
from sponsor_match.config import Settings
from sponsor_match.db import Database
p=argparse.ArgumentParser();p.add_argument('plan_json',type=Path);args=p.parse_args()
data=json.loads(args.plan_json.read_text());fields=['slug','environment','name','product_id','amount_minor','currency','interval','credits']
assert set(data)<=set(fields)|{'active'} and all(k in data for k in fields),'Provide the documented plan fields'
assert data['environment'] in ('test','live') and data['interval']=='month' and data['currency']=='USD' and data['amount_minor']==2499 and data['credits']==800
assert isinstance(data['credits'],int) and 0<data['credits']<=1000000
assert isinstance(data['amount_minor'],int) and 0<data['amount_minor']<=100000000
assert data['slug'] and data['product_id'] and data['name']
db=Database(Settings.from_env().database_url);db.open()
try:
 with db.transaction() as c:
  old=c.execute('select * from sm_private.billing_plans where slug=%s and environment=%s',(data['slug'],data['environment'])).fetchone()
  if old:
   if any(old[k]!=data[k] for k in fields):raise SystemExit('Existing plan differs: create a new version/slug instead')
   print('Plan already registered; price and allowance unchanged')
  else:
   c.execute('insert into sm_private.billing_plans(slug,environment,name,product_id,amount_minor,currency,interval,credits,active) values(%s,%s,%s,%s,%s,%s,%s,%s,%s)',tuple(data[k] for k in fields)+(bool(data.get('active',False)),))
   print('Plan registered. Checkout independently verifies the provider product before charging.')
  if data.get('active',False):
   c.execute('update sm_private.billing_plans set active=false where environment=%s and slug<>%s and active=true',(data['environment'],data['slug']))
   c.execute('update sm_private.billing_plans set active=true where environment=%s and slug=%s',(data['environment'],data['slug']))
finally:db.close()
