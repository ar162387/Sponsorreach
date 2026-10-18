"""Manual local-only download of a versioned public ESCO suggestion snapshot."""
import argparse,gzip,json,math,time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,UTC
from pathlib import Path
import httpx


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
 path=Path(args.output);cache=path.parent/'esco-v1.2.1-pages';cache.mkdir(parents=True,exist_ok=True)
 url='https://ec.europa.eu/esco/api/search'
 params={'text':'','language':'en','type':'occupation','limit':100,'full':'true','selectedVersion':'v1.2.1'}
 def page(offset):
  stored=cache/(str(offset)+'.json')
  if stored.exists():return json.loads(stored.read_text())
  for attempt in range(3):
   try:
    response=httpx.get(url,params={**params,'offset':offset},timeout=90);response.raise_for_status();data=response.json()
    if not isinstance(data,dict) or not data.get('_embedded',{}).get('results'):raise ValueError('Empty ESCO page')
    stored.write_text(json.dumps(data));print(json.dumps({'page':offset,'rows':len(data['_embedded']['results'])}),flush=True);return data
   except (httpx.HTTPError,ValueError):
    if attempt==2:raise
    time.sleep(2**attempt)
 first=page(0);pages=[first]
 # The API offset is a page index, not a record offset.
 with ThreadPoolExecutor(max_workers=2) as pool:pages.extend(pool.map(page,range(1,math.ceil(first['total']/100))))
 rows=[r for data in pages for r in data['_embedded']['results']]
 if len(rows)!=first['total'] or len({r['uri'] for r in rows})!=len(rows):raise ValueError('Incomplete or duplicated ESCO snapshot')
 payload={'source_url':url,'requested_version':'v1.2.1','parameters':params,'fetched_at':datetime.now(UTC).isoformat(),'occupations':rows}
 with gzip.open(path,'wt') as f:json.dump(payload,f)
 print(json.dumps({'occupations':len(rows),'output':str(path)}))

if __name__=='__main__':main()
