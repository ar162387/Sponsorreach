"""Prepare attributable source excerpts for operator review; never auto-publish."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,UTC
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from .evidence import fetch_public,quote_valid
from .taxonomy import key,contains

VERSION='csv-source-pool-2'
STOP={'limited','ltd','company','co','uk','the','and','group','services','international','holdings','llp','plc','trading','as','ta'}


def identity_in_page(name,html):
    soup=BeautifulSoup(html,'html.parser')
    text=key(soup.get_text(' '))
    words=[w for w in key(name).split() if w not in STOP]
    if not words:return False
    # A full distinctive name is preferable. A single title token requires a
    # unique recorded host (enforced in selection), not just a shared group site.
    if ' '.join(words) in text:return True
    title=key(soup.title.get_text(' ') if soup.title else '')
    distinct=[w for w in words if len(w)>=4]
    return bool(distinct and any(contains(title,w) for w in distinct))


def supported_activity_claims(html,phrases):
    soup=BeautifulSoup(html,'html.parser')
    for node in soup(['script','style','nav','footer','header','form']):node.decompose()
    lines=[' '.join(x.split()) for x in soup.get_text('\n').splitlines() if x.strip()]
    source='\n'.join(lines)
    return source,supported_text_claims(source,phrases)


def supported_text_claims(source,phrases):
    lines=source.splitlines()
    claims=[]
    for phrase in sorted(set(phrases),key=lambda s:(-len(s),s)):
        for line in lines:
            if len(line)>800 or re.search(r'cookie|privacy policy|website (?:by|design)|all rights reserved|\b(?:vacanc|apply|job alert|we are hiring)',line,re.I):continue
            found=re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',line,re.I)
            if found and quote_valid(found[0],line,source):
                claims.append({'kind':'activity','text':found[0],'excerpt':line})
                break
        if len(claims)>=8:break
    return claims


def prepare_pool(db,output,per_family=5,workers=6,cache_dir=None):
    taxonomy=db.taxonomy()
    # Only unambiguous current register identities with unique recorded hosts.
    rows=db.rows("""select e.id,e.name,e.payload,r.payload as source from sm.employers e
        join sm.employer_source_keys k on k.employer_id=e.id
        join sm.source_artifacts a on a.namespace=k.namespace and a.kind='historical_csv'
        join sm.source_records r on r.artifact_id=a.id and r.record_key=k.record_key
        where k.namespace='local:nocodb:company-enrichment-v2' and not e.is_demo
        and e.identity_status<>'quarantined' and exists(select 1 from sm.register_entries re
        where re.artifact_id=%s and re.name_key=e.name_key and re.town_key=e.town_key
        and lower(trim(re.route))='skilled worker' and (lower(re.rating) like '%%a rating%%' or lower(re.rating) like '%%a (premium)%%' or lower(re.rating) like '%%a (sme+)%%'))
        and (select count(*) from sm.employers d where d.name_key=e.name_key and d.town_key=e.town_key and not d.is_demo)=1
        order by e.name,e.id""",(db.active_snapshot(),))
    hosts=Counter(urlparse(c['value']).hostname for r in rows for c in r['payload'].get('channels',[]) if c['kind']=='website')
    selected={};families=Counter()
    for concept in [c for c in taxonomy.concepts if c.activities]:
        eligible=[]
        for r in rows:
            if any(contains(r['source'].get('Indicative Tags',''),p) for p in concept.activities):eligible.append(r)
        for r in eligible:
            websites=[c for c in r['payload'].get('channels',[]) if c['kind']=='website' and c.get('state')=='found' and hosts[urlparse(c['value']).hostname]==1]
            if not websites:continue
            id=str(r['id'])
            selected.setdefault(id,{'id':id,'name':r['name'],'url':websites[0]['value'],'phrases':set(),'families':set()})
            selected[id]['phrases'].update(p for p in concept.activities if contains(r['source'].get('Indicative Tags',''),p))
            selected[id]['families'].add(concept.id)
            families[concept.id]+=1
            if families[concept.id]>=per_family:break
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    def prepare(item):
        id,item=item
        target=output/(id+'.json')
        if target.exists():return json.loads(target.read_text())
        cached=Path(cache_dir)/(id+'.json') if cache_dir else None
        if cached and cached.exists():
            result=json.loads(cached.read_text())
            try:
                age=(datetime.now(UTC)-datetime.fromisoformat(result['prepared_at'])).total_seconds()
            except (KeyError,ValueError,TypeError):
                age=float('inf')
            if result.get('requested_url')==item['url'] and 0<=age<=86400:
                if 'source_text' in result:
                    claims=supported_text_claims(result['source_text'],item['phrases'])
                    result.update(claims=claims,status='prepared' if claims else 'no_exact_activity_span')
                result.update(version=VERSION,families=sorted(item['families']),cache_reused=True)
                target.write_text(json.dumps(result,indent=2)+'\n')
                return result
        result={'employer_id':id,'name':item['name'],'requested_url':item['url'],'families':sorted(item['families']),'version':VERSION,'prepared_at':datetime.now(UTC).isoformat(),'review_status':'unreviewed'}
        try:
            data,final,content_type=fetch_public(item['url'])
            if 'html' not in content_type:raise ValueError('non_html_source')
            if urlparse(final).hostname.removeprefix('www.')!=urlparse(item['url']).hostname.removeprefix('www.'):raise ValueError('changed_host_requires_identity_review')
            if not identity_in_page(item['name'],data):raise ValueError('page_identity_not_confirmed')
            text,claims=supported_activity_claims(data,item['phrases'])
            result.update(url=item['url'],resolved_url=final,source_text=text,claims=claims,status='prepared' if claims else 'no_exact_activity_span')
        except Exception as exc:
            result.update(status='source_unavailable' if not isinstance(exc,ValueError) else str(exc),claims=[])
        target.write_text(json.dumps(result,indent=2)+'\n')
        return result
    with ThreadPoolExecutor(max_workers=max(1,min(workers,8))) as executor:
        results=list(executor.map(prepare,selected.items()))
    report={'version':VERSION,'selected':len(results),'statuses':dict(Counter(r['status'] for r in results)),'results':[{k:r[k] for k in ['employer_id','name','status','families','claims']} for r in results]}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
