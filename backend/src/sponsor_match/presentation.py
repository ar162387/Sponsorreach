"""All recorded contact routes for visible cards; independent of ranking gates."""
from datetime import datetime,UTC
from urllib.parse import urlparse,parse_qs
from .quality import present,channel_shape

LABELS={'website':'Website','email':'Email','phone':'Phone','address':'Address','careers':'Careers','linkedin_company':'LinkedIn company','linkedin_jobs':'LinkedIn jobs','linkedin_person':'LinkedIn profile','job_board':'Job board','search_page':'Search results'}
BOARDS={'indeed.com':'Indeed','totaljobs.com':'Totaljobs','techjobs.co.uk':'Techjobs','bebee.com':'beBee','naukri.com':'Naukri','reed.co.uk':'Reed','cv-library.co.uk':'CV-Library','glassdoor.co.uk':'Glassdoor','glassdoor.com':'Glassdoor','simplyhired.co.uk':'SimplyHired'}


def displayed_channels(employer,at=None):
    at=at or datetime.now(UTC)
    unique={}
    for channel in employer.channels:
        if channel.attribution=='rejected' or not present(channel.value):continue
        c=channel.model_dump(mode='json');value=channel.value.strip();kind=channel.kind
        label=LABELS[kind];display=value;linkable=False
        if kind=='address':
            route=('address',' '.join(value.casefold().split()))
        elif kind in {'email','phone'}:
            linkable=channel_shape(kind,value)
            route=(kind,value.casefold() if kind=='email' else ''.join(x for x in value if x.isdigit()) or value.casefold())
        else:
            try:p=urlparse(value);host=(p.hostname or '').lower()
            except ValueError:continue
            if p.scheme not in {'http','https'} or not host or p.username or p.password:continue
            linkable=True
            bare=host.removeprefix('www.')
            if host=='linkedin.com' or host.endswith('.linkedin.com'):
                kind='linkedin_company' if p.path.startswith('/company/') else 'linkedin_jobs' if p.path.startswith('/jobs/') else 'linkedin_person'
                label=LABELS[kind];bare='linkedin.com'
            else:
                board=next((name for domain,name in BOARDS.items() if host==domain or host.endswith('.'+domain)),None)
                search=bool(any(k in parse_qs(p.query) for k in ['q','query','search','keywords']) or '/search' in p.path.lower() or p.path.startswith('/q-') or (bare=='totaljobs.com' and p.path.startswith('/jobs/')))
                if board:
                    kind='search_page' if search else 'job_board'
                    label=board+(' · search results' if search else ' · job link' if '/viewjob' in p.path or '/job/' in p.path else ' · job board')
                elif kind in {'job_board','search_page'}:label=bare+(' · search results' if search else ' · other link')
            display=p.netloc+p.path+('?' + p.query if p.query else '')
            route=('url',bare,p.path.rstrip('/'),p.query)
        if channel.state=='verified_absent':note='Previously recorded · unavailable at last check';linkable=False
        elif channel.state in {'temporarily_unavailable','blocked','inconclusive'}:note='Recorded route · last check inconclusive'
        elif channel.state=='not_observed':note='Imported · field-state conflict; not rechecked'
        elif channel.source_kind=='provided_csv':note='Provided company contact'
        elif channel.attribution=='accepted':note='Observed on employer source'
        else:note='Imported · not rechecked'
        if channel.observed_at and (at-channel.observed_at).days>90:note+=' · older observation'
        if kind in {'job_board','search_page','linkedin_jobs'}:note+=' · vacancy status unverified'
        c.update(kind=kind,label=label,display_value=display,linkable=linkable,note=note)
        # Collapse the same recorded route, preferring accepted/newer observations.
        preference=(channel.attribution=='accepted',channel.observed_at.timestamp() if channel.observed_at else 0,channel.state=='found')
        if route not in unique or preference>unique[route][0]:unique[route]=(preference,c)
    order={'website':0,'email':1,'phone':2,'address':3,'careers':3,'linkedin_company':4,'linkedin_jobs':5,'linkedin_person':6,'job_board':7,'search_page':8}
    return sorted([c for _,c in unique.values()],key=lambda c:(order[c['kind']],c['label'],c['value']))


def short_match_reason(explanation):
    """A concise display summary; the original supported explanation is retained."""
    import re
    from .taxonomy import Taxonomy,contains
    text=explanation.get('text','')
    if explanation.get('basis')=='activity':
        match=re.search(r'This aligns with your interest in (.+?)\.',text)
        concept=Taxonomy().resolve(match[1]) if match else None
        phrases=[p for p in concept.activities if contains(text.split('This aligns with')[0],p)] if concept else []
        if phrases:
            return 'Its '+ ' and '.join(phrases[:2])+' work aligns with your target role.'
    text=re.sub(r'^(?:Published|Recorded) (?:business activity|professional function):\s*','',text)
    text=text.split(' This aligns with your interest in ')[0].strip()
    if len(text)>170:text=text[:167].rsplit(' ',1)[0]+'…'
    return text
