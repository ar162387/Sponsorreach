"""Conservative screening: missing information is not proof of unreachability."""
import gzip
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse,parse_qs

DIGITAL_FIELDS=['Website','Email','Phone','Job Board Page','LinkedIn','Extras']
MISSING={'','null','none','nan','n/a','na','[]','{}','not found','not available','unavailable','unknown','not provided'}


def present(value):return str(value or '').strip().casefold() not in MISSING


def channel_shape(kind,value):
    value=str(value or '').strip()
    if not present(value):return False
    if kind=='address':
        return len(value)>=8 and bool(re.search(r'[a-zA-Z]',value))
    if kind=='email':
        return bool(re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[a-zA-Z]{2,}',value))
    if kind=='phone':
        base=re.sub(r'(?:ext\.?|extension|x|#)\s*\d+\s*$','',value,flags=re.I)
        digits=re.sub(r'\D','',base)
        return 7<=len(digits)<=15 and len(set(digits))>1
    try:p=urlparse(value)
    except ValueError:return False
    host=(p.hostname or '').lower()
    if p.scheme not in {'http','https'} or not host or p.username or p.password:return False
    if host in {'google.com','www.google.com','bing.com','www.bing.com','duckduckgo.com','www.duckduckgo.com'}:return False
    if host=='linkedin.com' or host.endswith('.linkedin.com'):
        parts=p.path.strip('/').split('/')
        return len(parts)>=2 and parts[0]=='company' and bool(parts[1])
    query=parse_qs(p.query)
    if any(k in query for k in ['q','query','search','keywords']) and any(t in p.path.lower() for t in ['search','jobs']):return False
    if kind in {'search_page','linkedin_person'}:return False
    return True


def assess_row(row):
    routes=[]
    for field,kind in [('Website','website'),('Email','email'),('Phone','phone'),('Job Board Page','careers'),('LinkedIn','linkedin_company')]:
        if channel_shape(kind,row.get(field,'')):routes.append(field)
    extras=re.findall(r'https?://[^\s\]\[<>]+',row.get('Extras') or '')
    if any(channel_shape('job_board',u) for u in extras):routes.append('Extras')
    has_raw=any(present(row.get(field)) for field in DIGITAL_FIELDS)
    address=present(row.get('Address'))
    return {'candidate_routes':routes,'status':'potential_digital_route' if routes else 'review_unusable_or_ambiguous_channels' if has_raw else 'postal_only_review' if address else 'archive_no_recorded_route',
            'missing_fields':[f for f in DIGITAL_FIELDS if not present(row.get(f))]}


def should_archive(row):return assess_row(row)['status']=='archive_no_recorded_route'


def raw_archive(rows,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    expected=json.loads(json.dumps(rows,default=str))
    if path.exists():
        with gzip.open(path,'rt',encoding='utf-8') as f:
            if json.load(f)!=expected:raise ValueError('Existing immutable archive differs')
        return hashlib.sha256(path.read_bytes()).hexdigest()
    temporary=path.with_suffix(path.suffix+'.tmp')
    # JSON is an exact backup, not a cleaned replacement for the source CSV.
    with gzip.open(temporary,'wt',encoding='utf-8') as f:
        json.dump(rows,f,ensure_ascii=False,default=str)
    with gzip.open(temporary,'rt',encoding='utf-8') as f:
        if json.load(f)!=expected:raise ValueError('Archive verification failed')
    temporary.replace(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()
