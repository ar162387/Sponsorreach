"""Public-page reads with bounded redirects, IP pinning and no private networks."""
from datetime import UTC, datetime
import ipaddress
import socket
import re
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from .models import Claim, Channel
from .intelligence import digest
from .taxonomy import contains, key
from .ingest import reconcile_memberships


def public_addresses(host):
    addresses=sorted({info[4][0] for info in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("Source URL resolves to a non-public address")
    return addresses


def fetch_public(url,limit=2_000_000):
    with httpx.Client(timeout=20,follow_redirects=False) as client:
        for _ in range(5):
            parsed=urlparse(url)
            if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password or parsed.port not in {None,80,443}:
                raise ValueError("Source must be a public HTTP(S) URL")
            address=public_addresses(parsed.hostname)[0]
            # Pin the checked IP. The original hostname supplies HTTP Host and TLS SNI.
            pinned=httpx.URL(url).copy_with(host=address)
            headers={"Host":parsed.netloc,"User-Agent":"SponsorReachEvidence/0.1 (+employer information validation)"}
            with client.stream("GET",pinned,headers=headers,extensions={"sni_hostname":parsed.hostname}) as response:
                if response.status_code in {301,302,303,307,308}:
                    url=urljoin(url,response.headers.get("location",""))
                    continue
                response.raise_for_status()
                data=bytearray()
                for part in response.iter_bytes():
                    data.extend(part)
                    if len(data)>limit:
                        raise ValueError("Source exceeds the download limit")
                return bytes(data),url,response.headers.get("content-type","")
    raise ValueError("Too many source redirects")


def page_text(html):
    soup=BeautifulSoup(html,"html.parser")
    for node in soup(["script","style","nav"]):
        node.decompose()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def quote_valid(text,excerpt,source):
    return bool(text.strip() and excerpt in source and text in excerpt and not re.search(r"\b(?:not|never|no longer|do not|don't|without)\b",excerpt,re.I))


def review_source(db,employer_id,url,text,claims,identity_confirmed=False):
    employer=db.employer(employer_id)
    if not employer or employer.is_demo:
        raise ValueError("Choose a real imported employer")
    parsed=urlparse(url)
    if parsed.scheme not in {"https","http"} or not parsed.hostname or parsed.username:
        raise ValueError("Invalid evidence URL")
    source_hosts={urlparse(c.value).hostname for c in employer.channels if c.kind=="website"}
    if parsed.hostname not in source_hosts:
        raise ValueError("Evidence must come from the employer's recorded website; review identity first if it changed")
    if not identity_confirmed:
        raise ValueError("An operator must confirm employer attribution before publishing claims")
    at=datetime.now(UTC)
    accepted_claims=[]
    taxonomy=db.taxonomy()
    for item in claims:
        if not quote_valid(item["text"],item["excerpt"],text):
            raise ValueError("Claim is unsupported or includes a negation; inspect the source")
        claim=Claim(id=digest([employer.id,url,item["kind"],item["text"]]),kind=item["kind"],text=item["text"],excerpt=item["excerpt"],source_url=url,source_kind="first_party",observed_at=at,attribution="accepted")
        claim.concept_ids=taxonomy.inferred_concepts(claim.text,"activity" if claim.kind=="activity" else "function")
        accepted_claims.append(claim)
    employer.identity_status="accepted"
    employer.claims=accepted_claims
    # Only values actually present on this source are corroborated. No SMTP guarantees.
    validated=[]
    for channel in employer.channels:
        supported=channel.value in text
        if channel.kind=="website":
            supported=urlparse(channel.value).hostname==parsed.hostname
        if channel.kind=="phone":
            supported=re.sub(r"\D","",channel.value) in re.sub(r"\D","",text)
        if supported:
            validated.append(channel.model_copy(update={"attribution":"accepted","state":"found","observed_at":at,"source_url":url}))
    employer.channels=validated
    employer=db.save_employer(employer,taxonomy)
    reconcile_memberships(db,[employer_id])
    return {"employer_id":employer_id,"accepted_claims":len(accepted_claims),"corroborated_channels":len(validated)}


def refresh_channel(db,employer_id,kind,value):
    employer=db.employer(employer_id)
    if not employer:
        return
    channel=next((c for c in employer.channels if c.kind==kind and c.value==value),None)
    if not channel:
        return
    url=value if kind not in {"email","phone"} else channel.source_url
    if not url:
        return
    def observe(state,source_url=url):
        employer.channels=[channel.model_copy(update={"state":state,"observed_at":datetime.now(UTC),"source_url":source_url})]
        db.save_employer(employer)
    try:
        data,final,_=fetch_public(url)
        text=page_text(data)
        corroborated=kind not in {"email","phone"} or value in text
        if kind=="phone":corroborated=bool(re.sub(r"\D","",value)) and re.sub(r"\D","",value) in re.sub(r"\D","",text)
        if corroborated and urlparse(final).hostname==urlparse(url).hostname:
            observe("found",final)
        else:
            observe("not_observed",final)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in {404,410}:
            # A removed source page does not prove its email/phone is absent.
            observe("inconclusive" if kind in {"email","phone"} else "verified_absent")
        else:
            observe("blocked" if e.response.status_code in {401,403,429} else "temporarily_unavailable")
            raise
    except httpx.TransportError:
        observe("temporarily_unavailable")
        raise
    except ValueError:
        observe("inconclusive")
        raise
