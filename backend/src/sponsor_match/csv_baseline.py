"""Explicitly operator-authorized full CSV baseline, not website corroboration."""
from collections import Counter
import csv
import hashlib
import json
import re
from pathlib import Path
from .ingest import clean,timestamp,reconcile_memberships,url_kind,preserve_csv_context
from .intelligence import digest
from .models import Claim,Channel
from .quality import present,channel_shape

VERSION='provided-csv-baseline-1'


def recorded_channels(row,reference,at):
    result=[];website=clean(row.get('Website'))
    for field,default in [('Website','website'),('Email','email'),('Phone','phone'),('Job Board Page','careers'),('LinkedIn','linkedin_company')]:
        value=clean(row.get(field))
        if not value:continue
        values=re.findall(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}',value) if default=='email' else [value]
        for item in values:
            kind=default if default in {'email','phone'} else url_kind(item,website,default)
            if kind:result.append(Channel(kind=kind,value=item,observed_at=at,source_url=reference+field.replace(' ','_')))
    for value in re.findall(r'https?://[^\s\]\[<>]+',clean(row.get('Extras'))):
        value=value.rstrip('.,;');kind=url_kind(value,website)
        if kind:result.append(Channel(kind=kind,value=value,observed_at=at,source_url=reference+'Extras'))
    return result


def apply_baseline(db,path,namespace,output):
    path=Path(path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    artifact=db.one("select id from sm.source_artifacts where namespace=%s and sha256=%s and kind='historical_csv'",(namespace,sha))
    if not artifact:raise ValueError('Import this CSV before activating its matching baseline')
    mappings={r['record_key']:str(r['employer_id']) for r in db.rows('select record_key,employer_id from sm.employer_source_keys where namespace=%s',(namespace,))}
    employers={e.id:e for e in db.employers(list(mappings.values()))}
    taxonomy=db.taxonomy();outcomes=[];totals=Counter()
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    for row in rows:
        record=clean(row.get('Source Record ID')) or clean(row.get('Company UUID'))
        if not record:continue
        eid=mappings.get(record)
        if not eid:totals['archived_no_route']+=1;continue
        employer=employers[eid]
        if employer.is_demo:raise ValueError('Cannot activate demo employers as CSV data')
        preserve_csv_context(db,eid,artifact['id'],record,row)
        if employer.identity_status=='quarantined':totals['quarantined']+=1;continue
        employer.identity_status='accepted';employer.matching_basis='provided_csv'
        at=timestamp(row.get('Observed At'))
        reference='urn:sponsorreach:csv:'+artifact['id']+':'+record+':'
        added=[]
        for column,kind in [('Indicative Tags','activity'),('Job Tags','historical_role')]:
            value=clean(row.get(column))
            if not present(value) or value.strip() in {'-','—'}:continue
            if kind=='historical_role' and value.casefold() in {'careers','join our team','jobs','no jobs found','no vacancies','current opportunities'}:continue
            added.append(Claim(id=digest([VERSION,namespace,record,column,value]),kind=kind,text=value,excerpt=value,source_url=reference+column.replace(' ','_'),observed_at=at,source_kind='provided_csv',attribution='accepted'))
        employer.claims+=added
        channels=[]
        rejected={(c.kind,c.value) for c in employer.channels if c.attribution=='rejected' or c.state=='verified_absent'}
        for channel in employer.channels+recorded_channels(row,reference,at):
            if (channel.kind,channel.value) in rejected and channel not in employer.channels:continue
            if channel.attribution=='rejected' or channel.state=='verified_absent':channels.append(channel);continue
            if channel.attribution=='accepted' and channel.source_kind!='provided_csv':channels.append(channel);continue
            if channel_shape(channel.kind,channel.value):
                channels.append(channel.model_copy(update={'attribution':'accepted','state':'found','source_kind':'provided_csv','source_url':reference+'contact'}))
            else:channels.append(channel)
        address=clean(row.get('Address'))
        if channel_shape('address',address) and not any(c.kind=='address' and c.value==address for c in channels):
            channels.append(Channel(kind='address',value=address,source_url=reference+'Address',observed_at=at,attribution='accepted',source_kind='provided_csv'))
        employer.channels=channels
        db.save_employer(employer,taxonomy)
        totals['onboarded']+=1;totals['with_professional_descriptors' if added else 'identity_only']+=1;totals['baseline_claims']+=len(added)
        outcomes.append({'employer_id':eid,'record_key':record,'professional_descriptors':bool(added)})
    reconcile_memberships(db,list(employers))
    db.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{matching_policy}','\"provided-csv-baseline-1\"'::jsonb) where id=%s",(artifact['id'],))
    report={'policy':VERSION,'csv_sha256':sha,'artifact_id':artifact['id'],'counts':dict(totals),'outcomes':outcomes}
    (output/'baseline-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return {k:v for k,v in report.items() if k!='outcomes'}
