"""Archive only records with neither a digital contact field nor a postal address."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from .quality import assess_row,should_archive,raw_archive,present
from .intelligence import digest
from .taxonomy import key


def inspect_csv(path):
    rows=[r for r in csv.DictReader(Path(path).open(encoding='utf-8-sig',newline='')) if r.get('Company UUID','').strip()]
    details=[{'source_key':r['Source Record ID'] or r['Company UUID'],'name':r['Company Name'],**assess_row(r)} for r in rows]
    groups=defaultdict(list)
    for r in rows:groups[(key(r['Company Name']),key(r.get('Town','')))].append(r['Source Record ID'] or r['Company UUID'])
    return rows,{'total':len(rows),'statuses':dict(Counter(d['status'] for d in details)),
                 'duplicate_source_keys':len(details)-len({d['source_key'] for d in details}),
                 'possible_name_town_duplicate_groups':[{'name_key':n,'town_key':t,'source_keys':ids} for (n,t),ids in groups.items() if len(ids)>1],
                 'records':details,'note':'Contact syntax only; no website availability, employer attribution or email deliverability has been established.'}


def cleanup_catalogue(db,path,namespace,output):
    rows,report=inspect_csv(path)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    by_key={(r['Source Record ID'] or r['Company UUID']):r for r in rows if should_archive(r)}
    mappings=db.rows('select record_key,employer_id from sm.employer_source_keys where namespace=%s and record_key=any(%s)',(namespace,list(by_key)))
    ids=[str(r['employer_id']) for r in mappings]
    report['archived_from_database']=0
    if ids:
        with db.transaction() as c:
            locked=c.execute('select id,payload from sm.employers where id=any(%s::uuid[]) order by id for update',(ids,)).fetchall()
            if any(any(present(ch.get('value')) for ch in r['payload'].get('channels',[])) for r in locked):
                raise ValueError('A selected employer has contact information beyond this CSV')
            if c.execute('select 1 from sm.employer_source_keys where employer_id=any(%s::uuid[]) and namespace<>%s limit 1',(ids,namespace)).fetchone():
                raise ValueError('A selected employer has another source identity; review required')
            history=c.execute('select r.payload from sm.source_records r join sm.source_artifacts a on a.id=r.artifact_id where a.namespace=%s and r.record_key=any(%s)',(namespace,list(by_key))).fetchall()
            if any(not r['payload'].get('archived') and not should_archive(r['payload']) for r in history):
                raise ValueError('A selected employer has a recorded outreach route in another import')
            for table,column in [('accepted_claims','employer_id'),('search_index_documents','employer_id'),('evaluation_labels','employer_id')]:
                if c.execute(f'select 1 from sm.{table} where {column}=any(%s::uuid[]) limit 1',(ids,)).fetchone():
                    raise ValueError('Selected rows have reviewed/indexed evidence; operator review required')
            if c.execute('select 1 from sm_private.match_results where employer_id=any(%s::uuid[]) limit 1',(ids,)).fetchone():raise ValueError('Selected rows have saved results')
            if c.execute('select 1 from sm.employer_relationships where parent_id=any(%s::uuid[]) or child_id=any(%s::uuid[]) limit 1',(ids,ids)).fetchone():raise ValueError('Selected rows have reviewed identity relationships')
            tables=['employer_concepts','accepted_claims','search_documents','vacancy_observations','sponsor_memberships','contact_channels','observations','employer_source_keys']
            backup={'namespace':namespace,'policy':'no-recorded-route-v1','source_rows':list(by_key.values()),'tables':{}}
            backup['tables']['employers']=c.execute('select * from sm.employers where id=any(%s::uuid[])',(ids,)).fetchall()
            for table in tables:backup['tables'][table]=c.execute(f'select * from sm.{table} where employer_id=any(%s::uuid[])',(ids,)).fetchall()
            backup['tables']['source_records']=c.execute('select r.* from sm.source_records r join sm.source_artifacts a on a.id=r.artifact_id where a.namespace=%s and r.record_key=any(%s)',(namespace,list(by_key))).fetchall()
            connection=conninfo_to_dict(db.pool.conninfo)
            target=digest([connection.get('host'),connection.get('dbname'),namespace,sorted(ids)])[:20]
            # A content-derived filename makes archive verification replayable.
            archive=output/f'no-recorded-route-{target}.json.gz'
            archive_sha=raw_archive(backup,archive)
            artifact=c.execute("select id from sm.source_artifacts where namespace=%s and kind='historical_csv' order by imported_at desc limit 1",(namespace,)).fetchone()['id']
            with c.cursor() as cursor:
                cursor.executemany("insert into sm.import_dispositions(namespace,record_key,employer_id,artifact_id,status,reason,archive_path,archive_sha256,raw_sha256) values(%s,%s,%s,%s,'archived','no_recorded_outreach_route',%s,%s,%s) on conflict(namespace,record_key) do update set status='archived',archive_path=excluded.archive_path,archive_sha256=excluded.archive_sha256,raw_sha256=excluded.raw_sha256",[(namespace,r['record_key'],str(r['employer_id']),artifact,str(archive.resolve()),archive_sha,digest(by_key[r['record_key']])) for r in mappings])
            for table in tables:c.execute(f'delete from sm.{table} where employer_id=any(%s::uuid[])',(ids,))
            c.execute('delete from sm.employers where id=any(%s::uuid[])',(ids,))
            c.execute("update sm.source_records r set payload=%s from sm.source_artifacts a where a.id=r.artifact_id and a.namespace=%s and r.record_key=any(%s)",(Jsonb({'archived':True,'archive_sha256':archive_sha}),namespace,list(by_key)))
            c.execute('delete from sm.query_cache')
            report.update({'archived_from_database':len(locked),'archive_path':str(archive.resolve()),'archive_sha256':archive_sha})
    (output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    return {k:v for k,v in report.items() if k not in {'records','possible_name_town_duplicate_groups'}} | {'possible_duplicate_groups':len(report['possible_name_town_duplicate_groups'])}
