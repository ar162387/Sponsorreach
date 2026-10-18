"""Idempotent imports preserve raw records and never promote CSV assertions."""
import csv
import hashlib
import io
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, UTC
from uuid import uuid5, uuid4, NAMESPACE_URL
from urllib.parse import urlparse
from collections import Counter
from psycopg.types.json import Jsonb
from .models import Employer, Claim, Channel, Membership, Vacancy
from .taxonomy import key
from .intelligence import digest
from .quality import should_archive,raw_archive

MISSING = {"", "null", "none", "nan", "n/a", "na", "[]", "{}", "not found"}


def clean(value):
    text = str(value or "").strip()
    return "" if text.casefold() in MISSING else text


def timestamp(value):
    try:
        dt = datetime.fromisoformat(clean(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    except ValueError:
        return None


def canonical_id(db,namespace,record_key):
    existing=db.one("select employer_id from sm.employer_source_keys where namespace=%s and record_key=%s",(namespace,str(record_key)))
    if not existing:existing=db.one('select employer_id from sm.import_dispositions where namespace=%s and record_key=%s',(namespace,str(record_key)))
    return str(existing["employer_id"]) if existing else str(uuid4())


def url_kind(url, website="", default="job_board"):
    parsed=urlparse(url)
    if parsed.scheme not in {"https","http"} or not parsed.hostname or parsed.username:
        return None
    path=parsed.path.casefold()
    if parsed.query or any(x in path for x in ["/search", "/jobs/search"]):
        return "search_page"
    if parsed.hostname.endswith("linkedin.com"):
        return "linkedin_company" if "/company/" in path else "linkedin_jobs" if "/jobs/" in path else "linkedin_person"
    if website and parsed.hostname==urlparse(website).hostname:
        return "careers" if any(s in path for s in ["career","jobs","vacan"]) else "website"
    return default


def artifact(db,path,kind,namespace,url="",publication_date=None,metadata=None):
    data=Path(path).read_bytes()
    checksum=hashlib.sha256(data).hexdigest()
    id=digest([namespace,checksum])
    db.execute("insert into sm.source_artifacts(id,kind,namespace,url,sha256,publication_date,metadata) values(%s,%s,%s,%s,%s,%s,%s) on conflict(id) do nothing",(id,kind,namespace,url,checksum,publication_date,Jsonb(metadata or {"filename":Path(path).name})))
    return id


def preserve_csv_context(db, employer_id, artifact_id, record_key, row):
    """Keep the judge's rationale as context, never as an asserted business activity.

    Reasoning can describe rejected lookalikes and superseded contacts. Preserving
    its exact wording and field references supports attribution review without
    adding those rejected entities to the semantic index.
    """
    reference=f'urn:sponsorreach:csv:{artifact_id}:{record_key}:'
    for column in ('Reasoning', 'Tags', 'Indicative Tags', 'Job Tags', 'Evidence URLs', 'Field States'):
        value=clean(row.get(column))
        if not value:
            continue
        payload={'source_artifact_id':artifact_id,'record_key':record_key,
                 'source_column':column,'raw_value':value,
                 'interpretation':'identity_and_extraction_context' if column=='Reasoning' else 'source_field',
                 'professional_claim':False}
        db.execute("insert into sm.observations values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(id) do nothing",
                   (digest(['csv-context-1',artifact_id,record_key,column,value]),employer_id,
                    'csv_context:'+column,'found',reference+column.replace(' ','_'),
                    timestamp(row.get('Observed At')),Jsonb(payload),'csv-context-1'))


def import_csv(db,path,namespace):
    baseline_enabled=db.one("select exists(select 1 from sm.source_artifacts where namespace=%s and kind='historical_csv' and metadata->>'matching_policy'='provided-csv-baseline-1') enabled",(namespace,))['enabled']
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    required={"Company Name","Company UUID","Source Record ID","Indicative Tags","Field States"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("This is not a Company Enrichment V2 export")
    artifact_id=artifact(db,path,"historical_csv",namespace)
    rejected=[r for r in rows if clean(r.get('Company UUID')) and should_archive(r)]
    archive_path=Path(__file__).resolve().parents[3]/'data/import-archives'/f'{artifact_id}.json.gz'
    archive_sha=raw_archive(rejected,archive_path) if rejected else ''
    duplicates=Counter((key(r.get("Company Name","")),key(r.get("Town",""))) for r in rows if clean(r.get("Company UUID")))
    taxonomy=db.taxonomy()
    imported=conflicts=archived=0
    for row in rows:
        if not clean(row.get("Company UUID")):
            continue
        source_key=clean(row.get("Source Record ID")) or row["Company UUID"]
        id=canonical_id(db,namespace,source_key)
        if should_archive(row) and not db.one('select 1 from sm.employer_source_keys where namespace=%s and record_key=%s',(namespace,source_key)):
            db.execute("insert into sm.import_dispositions(namespace,record_key,employer_id,artifact_id,status,reason,archive_path,archive_sha256,raw_sha256) values(%s,%s,%s,%s,'archived','no_recorded_outreach_route',%s,%s,%s) on conflict(namespace,record_key) do nothing",(namespace,source_key,id,artifact_id,str(archive_path),archive_sha,digest(row)))
            archived+=1
            continue
        dt=timestamp(row.get("Observed At"))
        try:
            states=json.loads(row.get("Field States") or "{}")
            if not isinstance(states,dict):
                states={}
        except ValueError:
            states={}
            conflicts+=1
        claims=[]
        for column,kind in [("Indicative Tags","activity"),("Job Tags","historical_role")]:
            text=clean(row.get(column))
            if text:
                # Preserve the entire rendered field; comma splitting would invent structure.
                claims.append(Claim(id=digest([namespace,source_key,column,text,dt]),kind=kind,text=text,observed_at=dt))
        channels=[]
        website=clean(row.get("Website"))
        fields=[("Website","official_website","website"),("Email","email","email"),("Phone","phone","phone"),("Job Board Page","career_page","careers"),("LinkedIn","linkedin","linkedin_company")]
        for column,field,kind in fields:
            value=clean(row.get(column))
            if not value:
                continue
            state=states.get(field,"not_observed")
            if state not in {"found","verified_absent","not_observed","inconclusive","temporarily_unavailable","blocked"}:
                state="inconclusive"
            if kind not in {"email","phone"}:
                kind=url_kind(value,website,kind)
                if not kind:
                    continue
            if state!="found":
                conflicts+=1
            channels.append(Channel(kind=kind,value=value,source_url="",observed_at=dt,state=state))
        for value in re.findall(r"https?://[^\s\]\[<>]+",clean(row.get("Extras"))):
            kind=url_kind(value,website)
            if kind:
                channels.append(Channel(kind=kind,value=value,observed_at=dt))
        employer=Employer(id=id,name=clean(row["Company Name"]),town=clean(row.get("Town")),county=clean(row.get("County")),claims=claims,channels=channels,source_namespace=namespace,source_key=source_key)
        db.save_employer(employer,taxonomy)
        db.execute("update sm.import_dispositions set status='restored' where namespace=%s and record_key=%s",(namespace,source_key))
        db.execute("insert into sm.source_records values(%s,%s,%s) on conflict do nothing",(artifact_id,source_key,Jsonb(row)))
        preserve_csv_context(db,id,artifact_id,source_key,row)
        imported+=1
    reconcile_memberships(db)
    result={"imported":imported,"archived_no_route":archived,"raw_rows":len(rows),"conflicts":conflicts,"duplicate_identity_groups":sum(v>1 for v in duplicates.values()),"accepted_claims":0,"note":"Historical observations retained; no current vacancies or contacts verified by import."}
    if baseline_enabled:
        from .csv_baseline import apply_baseline
        output=Path(__file__).resolve().parents[3]/'data/baseline-batches'/artifact_id
        result['baseline_activation']=apply_baseline(db,path,namespace,output)
    return result


def import_legacy(db,path,namespace):
    import openpyxl
    workbook=openpyxl.load_workbook(path,read_only=True,data_only=True)
    sheet=workbook.active
    iterator=sheet.iter_rows(values_only=True)
    headers=[str(v or "") for v in next(iterator)]
    aid=artifact(db,path,"legacy_workbook",namespace)
    count=0
    taxonomy=db.taxonomy()
    for number,values in enumerate(iterator,2):
        row=dict(zip(headers,values))
        name=clean(row.get("Organisation Name"))
        if not name:
            continue
        id=canonical_id(db,namespace,str(number))
        tags=clean(row.get("Tags"))
        employer=Employer(id=id,name=name,town=clean(row.get("Town/City")),county=clean(row.get("County")),source_namespace=namespace,source_key=str(number),claims=[Claim(id=digest([id,"tags",tags]),kind="activity",text=tags)] if tags else [])
        for column,kind in [("Email","email"),("Contact","phone"),("Company Career page","careers"),("Linkedin/job","linkedin_company")]:
            value=clean(row.get(column))
            if value:
                resolved=kind if kind in {"email","phone"} else url_kind(value,default=kind)
                if resolved:
                    employer.channels.append(Channel(kind=resolved,value=value))
        db.save_employer(employer,taxonomy)
        db.execute("insert into sm.source_records values(%s,%s,%s) on conflict do nothing",(aid,str(number),Jsonb({k:str(v or "") for k,v in row.items()})))
        count+=1
    workbook.close()
    reconcile_memberships(db)
    return {"imported":count,"accepted_claims":0}


def import_register(db,path,url,publication_date,allow_large_change=False):
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname not in {"assets.publishing.service.gov.uk","www.gov.uk"}:
        raise ValueError("Register provenance must be an official GOV.UK URL")
    date=datetime.fromisoformat(publication_date).date()
    if date>datetime.now(UTC).date():
        raise ValueError("Register publication date is in the future")
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        if not {"Organisation Name","Town/City","County","Type & Rating","Route"}.issubset(reader.fieldnames or []):
            raise ValueError("Official register columns are missing")
        rows=list(reader)
    if len(rows)<1000 or any(not clean(r["Organisation Name"]) or not clean(r["Route"]) for r in rows):
        raise ValueError("Incomplete register snapshot; previous snapshot remains active")
    previous=db.one("select publication_date,metadata from sm.source_artifacts where kind='official_register' and metadata->>'active'='true' order by publication_date desc limit 1")
    if previous and previous["publication_date"]>date:
        raise ValueError("Cannot activate an older register snapshot")
    if previous and len(rows)<previous["metadata"].get("row_count",0)*.9 and not allow_large_change:
        raise ValueError("Register shrank by more than 10%; review before activating")
    aid=artifact(db,path,"official_register","govuk:worker-register",url,publication_date,{"active":False,"row_count":len(rows),"filename":Path(path).name})
    with db.transaction() as c:
        records=[(aid,str(i),key(r["Organisation Name"]),key(r["Town/City"]),r["Route"],r["Type & Rating"],Jsonb(r)) for i,r in enumerate(rows,1)]
        with c.cursor() as cursor:
            cursor.executemany("insert into sm.register_entries values(%s,%s,%s,%s,%s,%s,%s) on conflict do nothing",records)
        c.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{active}','false') where kind='official_register' and id<>%s",(aid,))
        c.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{active}','true') where id=%s",(aid,))
        c.execute("update sm.search_documents d set sponsor_eligible=false from sm.employers e where e.id=d.employer_id and not e.is_demo")
    reconcile_memberships(db)
    return {"artifact_id":aid,"route_rows":len(rows),"skilled_worker_rows":sum(r["Route"]=="Skilled Worker" for r in rows)}


REGISTER_LINKAGE_VERSION='register-linkage-2'


def register_identity_attributable(identity_status,source_county,register_counties,supported_identities):
    # Blank counties are unknown, not contradictory. Several known counties or
    # competing supported identities still require review.
    known={key(clean(value)) for value in register_counties if clean(value)}
    county=key(clean(source_county))
    return identity_status=='accepted' and supported_identities==1 and len(known)<=1 and (not county or not known or county in known)


def reconcile_memberships(db,employer_ids=None):
    snapshot=db.active_snapshot()
    if not snapshot:
        return 0
    artifact_row=db.one("select publication_date,url from sm.source_artifacts where id=%s",(snapshot,))
    date=artifact_row["publication_date"].isoformat()
    selected=" and e.id=any(%s::uuid[])" if employer_ids is not None else ""
    rows=db.rows("""select e.id,e.payload,r.record_key,r.route,r.rating,r.payload as register_payload from sm.employers e join sm.register_entries r on e.name_key=r.name_key and e.town_key=r.town_key where r.artifact_id=%s and not e.is_demo and e.town_key<>''"""+selected,(snapshot,employer_ids) if employer_ids is not None else (snapshot,))
    grouped={}
    for row in rows:
        grouped.setdefault(str(row["id"]),[]).append(row)
    taxonomy=db.taxonomy()
    for id,entries in grouped.items():
        employer=Employer.model_validate(entries[0]["payload"])
        counties={key(clean(r["register_payload"].get("County",""))) for r in entries}
        # An unresolved historical observation is not a second established
        # legal identity. Accepted peers and peers carrying company identifiers
        # remain conflicts; no rows, evidence or source keys are merged here.
        duplicates=db.one("select count(*) as n from sm.employers where name_key=%s and town_key=%s and not is_demo and identity_status<>'quarantined' and (identity_status='accepted' or company_number is not null)",(key(employer.name),key(employer.town)))["n"]
        attributable=register_identity_attributable(employer.identity_status,employer.county,counties,duplicates)
        employer.memberships=[Membership(route=r["route"],rating=r["rating"],snapshot_date=date,snapshot_id=snapshot,attribution="accepted" if attributable else "unverified") for r in entries]
        db.save_employer(employer,taxonomy)
        with db.transaction() as c:
            decision={'policy_version':REGISTER_LINKAGE_VERSION,'snapshot_id':snapshot,'record_keys':sorted(r['record_key'] for r in entries),'source_county':key(clean(employer.county)),'known_register_counties':sorted(counties-{''}),'supported_identity_count':duplicates,'attribution':'accepted' if attributable else 'unverified'}
            c.execute("insert into sm.observations values(%s,%s,'sponsor_linkage',%s,%s,%s,%s,%s) on conflict(id) do nothing",(digest([id,decision]),id,'found' if attributable else 'inconclusive',artifact_row['url'],datetime.now(UTC),Jsonb(decision),REGISTER_LINKAGE_VERSION))
            for r,m in zip(entries,employer.memberships):
                c.execute("insert into sm.sponsor_memberships values(%s,%s,%s,%s,%s,%s,%s) on conflict(employer_id,artifact_id,record_key) do update set attribution=excluded.attribution",(id,snapshot,r["record_key"],m.route,m.rating,m.attribution,date))
    return len(grouped)


def import_ledger(db,path,namespace):
    # Read-only SQLite URI; exporting must never update the running scraper's DB.
    ledger=sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True)
    ledger.row_factory=sqlite3.Row
    tables={r[0] for r in ledger.execute("select name from sqlite_master where type='table'")}
    if not {"companies","field_values","tag_evidence","job_postings"}.issubset(tables):
        raise ValueError("Missing V2 ledger tables")
    taxonomy=db.taxonomy()
    count=0
    for row in ledger.execute("select * from companies"):
        row=dict(row)
        source=json.loads(row.get("source_json") or "{}")
        source_key=str(source.get("Id") or row["company_uuid"])
        id=canonical_id(db,namespace,source_key)
        name=clean(row.get("name") or source.get("name") or source.get("Organisation Name"))
        if not name:
            continue
        employer=Employer(id=id,name=name,town=clean(row.get("town") or source.get("town")),county=clean(row.get("county") or source.get("county")),company_number=clean(row.get("company_number")),source_namespace=namespace,source_key=source_key)
        fields=list(ledger.execute("select * from field_values where company_uuid=? order by observed_at",(row["company_uuid"],)))
        mapping={"official_website":"website","email":"email","phone":"phone","career_page":"careers","linkedin":"linkedin_company"}
        for f in fields:
            if f["field"] not in mapping:
                continue
            value=json.loads(f["value_json"]) if f["value_json"] else ""
            if not isinstance(value,str):
                continue
            kind=mapping[f["field"]]
            if value and kind not in {"email","phone"}:
                kind=url_kind(value,default=kind) or kind
            employer.channels.append(Channel(kind=kind,value=value,source_url=f["evidence_url"] or "",observed_at=timestamp(f["observed_at"]),state=f["state"]))
        for t in ledger.execute("select * from tag_evidence where company_uuid=?",(row["company_uuid"],)):
            employer.claims.append(Claim(id=digest([namespace,dict(t)]),kind="historical_role" if t["kind"]=="hiring" else "activity",text=t["tag"],source_url=t["evidence_ref"] or "",observed_at=timestamp(t["observed_at"])))
        for j in ledger.execute("select * from job_postings where company_uuid=?",(row["company_uuid"],)):
            employer.vacancies.append(Vacancy(title=j["title"],url=j["canonical_url"],provider=j["provider"] or "unknown",observed_at=timestamp(j["observed_at"]),closing_at=timestamp(j["closing_at"]),location=j["location"] or ""))
        # Ledger detail is preserved, but model tags/shared references are not per-claim proof.
        db.save_employer(employer,taxonomy)
        count+=1
    ledger.close()
    reconcile_memberships(db)
    return {"imported":count,"verified_vacancies":0}
