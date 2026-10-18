"""Fetch optional board icons from official websites; run with backend dependencies."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin,urlparse
import httpx,json,re
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parents[1]/'web/public/brand/job-boards';root.mkdir(parents=True,exist_ok=True)
boards={'Indeed':'https://www.indeed.com','Totaljobs':'https://www.totaljobs.com','Techjobs':'https://www.techjobs.co.uk','Naukri':'https://www.naukri.com','beBee':'https://www.bebee.com','LinkedIn':'https://www.linkedin.com'}
def download(item):
 name,origin=item
 try:
  with httpx.Client(timeout=6,follow_redirects=True,max_redirects=4) as client:
   response=client.get(origin+'/favicon.ico')
   if response.status_code!=200 or not response.headers.get('content-type','').startswith('image/'):
    page=client.get(origin);soup=BeautifulSoup(page.text,'html.parser');icon=soup.find('link',rel=lambda value:value and 'icon' in value.lower())
    if not icon or not icon.get('href'):return name,None
    response=client.get(urljoin(str(page.url),icon['href']))
   mime=response.headers.get('content-type','').split(';')[0]
   if response.status_code!=200 or not mime.startswith('image/') or len(response.content)>150000:return name,None
   extension={'image/png':'png','image/svg+xml':'svg','image/jpeg':'jpg','image/webp':'webp'}.get(mime,'ico')
   filename=re.sub(r'[^a-z0-9]','',name.lower())+'.'+extension;(root/filename).write_bytes(response.content)
   return name,'/brand/job-boards/'+filename
 except Exception:return name,None
with ThreadPoolExecutor(6) as pool:results=dict(pool.map(download,boards.items()))
manifest={k:v for k,v in results.items() if v}
Path(root.parent.parent.parent/'lib/job-board-icons.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(results))
