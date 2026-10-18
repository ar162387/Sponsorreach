"""Optional verified-open signals require specific, attributable structured adverts."""
from datetime import UTC,datetime
from urllib.parse import urlparse
import json
import httpx
from bs4 import BeautifulSoup
from .models import Vacancy,Claim
from .evidence import fetch_public,page_text
from .ingest import timestamp
from .intelligence import digest
from .taxonomy import key


def json_jobs(html):
    soup=BeautifulSoup(html,"html.parser")
    jobs=[]
    def visit(value):
        if isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,dict):
            types=value.get("@type",[])
            if types=="JobPosting" or isinstance(types,list) and "JobPosting" in types:jobs.append(value)
            if "@graph" in value:visit(value["@graph"])
    for script in soup.select('script[type="application/ld+json"]'):
        try:visit(json.loads(script.string or script.get_text()))
        except ValueError:continue
    return jobs


def verify_vacancy(db,employer_id,url,attribution_reviewed=False):
    employer=db.employer(employer_id)
    if not employer or employer.is_demo or employer.identity_status!="accepted" or not attribution_reviewed:
        raise ValueError("An accepted real employer and reviewed vacancy attribution are required")
    hosts={urlparse(c.value).hostname for c in employer.channels if c.kind=="website" and c.attribution=="accepted"}
    if urlparse(url).hostname not in hosts or url in {c.value for c in employer.channels if c.kind in {"website","careers"}}:
        raise ValueError("Use an individually attributable first-party vacancy URL")
    at=datetime.now(UTC)
    try:data,final,_=fetch_public(url)
    except httpx.HTTPStatusError as e:
        if e.response.status_code not in {404,410}:raise
        for v in employer.vacancies:
            if v.url==url:v.state="closed";v.observed_at=at
        db.save_employer(employer)
        return {"verified_open":False,"state":"closed"}
    if urlparse(final).hostname not in hosts:raise ValueError("Vacancy redirected outside the accepted employer website")
    text=page_text(data)
    jobs=json_jobs(data)
    jobs=[j for j in jobs if key(j.get("hiringOrganization",{}).get("name",""))==key(employer.name)]
    if len(jobs)!=1:raise ValueError("No unique employer-attributed structured vacancy found")
    job=jobs[0]
    title=str(job.get("title") or "").strip()
    closing=timestamp(job.get("validThrough"))
    if not title or not closing:raise ValueError("Title and validThrough date are required for an open badge")
    if any(term in text.casefold() for term in ["successfully recruited","position has been filled","vacancy closed","no longer accepting applications"]):
        state="closed"
    else:state="open" if closing>at else "expired"
    locations=job.get("jobLocation") or []
    if isinstance(locations,dict):locations=[locations]
    places=[str(l.get("address",{}).get("addressLocality") or "") for l in locations if isinstance(l,dict)]
    countries=[]
    for location in locations:
        if not isinstance(location,dict):continue
        country=location.get("address",{}).get("addressCountry","")
        if isinstance(country,dict):country=country.get("name","")
        if isinstance(country,str):countries.append(country.strip())
    country=next((c for c in countries if c.casefold() in {"gb","uk","united kingdom"}),"")
    if state=="open" and not country:state="unverified"
    taxonomy=db.taxonomy()
    concept=taxonomy.resolve(title)
    vacancy=Vacancy(title=title,url=final,provider="first_party_jsonld",concept_ids=[concept.id] if concept else [],observed_at=at,closing_at=closing,verified=state!="unverified",state=state,location=", ".join(filter(None,places)),country=country)
    employer.vacancies=[v for v in employer.vacancies if v.url not in {url,final}]+[vacancy]
    employer.claims.append(Claim(id=digest([employer.id,final,title]),kind="historical_role",text=title,excerpt=title,source_url=final,observed_at=at,source_kind="first_party",attribution="accepted"))
    db.save_employer(employer,taxonomy)
    return {"verified_open":state=="open","state":state}
