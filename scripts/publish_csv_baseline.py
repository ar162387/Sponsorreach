"""Atomic public-only activation of a staged, operator-authorized CSV catalogue.

No candidate/account/feedback tables are read or copied. The prior live public
rows are backed up; optimistic version checks prevent overwriting newer imports.
Run from backend with the release folder argument.
"""
import gzip
import json
from pathlib import Path
import sys
import secrets
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from sponsor_match.config import Settings

SPECS=[('employers',['id']),('observations',['id']),('accepted_claims',['id']),('contact_channels',['id']),('sponsor_memberships',['employer_id','artifact_id','record_key']),('employer_concepts',['employer_id','concept_id','claim_id']),('search_documents',['id'])]


def main():
    folder=Path(sys.argv[1]);expected=json.loads((folder/'live-before.json').read_text());ids=list(expected)
    report=json.loads((folder/'baseline-report.json').read_text())
    if len(ids)!=report['counts']['onboarded']:raise ValueError('Staged catalogue count differs from the live baseline')
    with psycopg.connect('postgresql://localhost:55432/sponsormatch') as source,psycopg.connect(Settings.from_env().database_url,connect_timeout=15) as target:
        source.execute('set transaction isolation level repeatable read read only')
        transport_key=secrets.token_hex(16)
        target.execute("set local statement_timeout='10min'")
        target.execute("select pg_advisory_xact_lock(hashtextextended('sponsorreach:csv-baseline-publication',0))")
        live={str(r[0]):r[1] for r in target.execute('select id,version from sm.employers where id=any(%s::uuid[]) for update',(ids,))}
        if not (folder/'committed-employers.json').exists() and live!=expected:raise ValueError('Live employer data changed; refresh staging before publication')
        if source.execute("select count(*) from sm.employers where id=any(%s::uuid[]) and not is_demo and payload->>'matching_basis'='provided_csv'",(ids,)).fetchone()[0]!=len(ids):raise ValueError('Incomplete CSV activation')
        if source.execute("select id from sm.source_artifacts where kind='official_register' and metadata->>'active'='true'").fetchone()!=target.execute("select id from sm.source_artifacts where kind='official_register' and metadata->>'active'='true'").fetchone():raise ValueError('Sponsor snapshots differ')
        if target.execute('select pg_database_size(current_database())').fetchone()[0]>400*1024*1024:raise ValueError('Inspect free-tier capacity before proceeding')
        backup_path=folder/'live-public-before.json.gz'
        if backup_path.exists():
            with gzip.open(backup_path,'rt') as f:backup=json.load(f)
            if backup['employer_ids']!=ids or {r['id']:r['version'] for r in backup['tables']['employers']}!=expected:raise ValueError('Existing backup does not match the unchanged live baseline')
        else:
            backup={'employer_ids':ids,'tables':{},'private_rows_copied':0}
            for table,_ in SPECS:
                field='id' if table=='employers' else 'employer_id'
                query=sql.SQL('select row_to_json(t) from {} t where {}=any(%s::uuid[])').format(sql.Identifier('sm',table),sql.Identifier(field))
                backup['tables'][table]=[r[0] for r in target.execute(query,(ids,))]
            with gzip.open(backup_path,'wt') as f:json.dump(backup,f,default=str)
            with gzip.open(backup_path,'rt') as f:
                if json.load(f)['employer_ids']!=ids:raise ValueError('Backup verification failed')
        # Commit bounded, internally consistent employer batches. Long free-tier
        # connections may be recycled; checkpoints make this transfer replayable.
        target.commit()
        records={};columns_by_table={};counts={}
        for table,pks in SPECS:
            columns=[r[0] for r in source.execute("select column_name from information_schema.columns where table_schema='sm' and table_name=%s and is_generated='NEVER' order by ordinal_position",(table,))]
            columns_by_table[table]=columns;records[table]={}
            field='id' if table=='employers' else 'employer_id'
            cols=sql.SQL(',').join(map(sql.Identifier,columns))
            for row in source.execute(sql.SQL('select {} from {} where {}=any(%s::uuid[])').format(cols,sql.Identifier('sm',table),sql.Identifier(field)),(ids,)):
                value=dict(zip(columns,row));records[table].setdefault(str(value[field]),[]).append(value)
            counts[table]=sum(len(v) for v in records[table].values())
        staged_versions={eid:records['employers'][eid][0]['version'] for eid in ids}
        ctes=[sql.SQL('payload as materialized (select extensions.pgp_sym_decrypt(%s,%s)::jsonb data)')]
        dependencies={'observations':'employers','accepted_claims':'observations','contact_channels':'employers','sponsor_memberships':'employers','employer_concepts':'accepted_claims','search_documents':'employers'}
        for table,pks in SPECS:
            cols=sql.SQL(',').join(map(sql.Identifier,columns_by_table[table]));name=sql.Identifier('sm',table)
            conflict=sql.SQL(',').join(map(sql.Identifier,pks))
            changes=sql.SQL(',').join(sql.SQL('{}=excluded.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in columns_by_table[table] if c not in pks)
            action=sql.SQL('do nothing') if table=='observations' or all(c in pks for c in columns_by_table[table]) else sql.SQL('do update set {}').format(changes)
            dependency=sql.SQL('') if table not in dependencies else sql.SQL(' cross join (select count(*) from {}) ready').format(sql.Identifier('w_'+dependencies[table]))
            ctes.append(sql.SQL('{} as (insert into {} ({}) select {} from jsonb_populate_recordset(null::{},(select data->{} from payload)){} where true on conflict ({}) {} returning 1)').format(sql.Identifier('w_'+table),name,cols,cols,name,sql.Literal(table),dependency,conflict,action))
        statement=sql.SQL('with {} select 1').format(sql.SQL(',').join(ctes))
        checkpoint=folder/'committed-employers.json'
        committed=set(json.loads(checkpoint.read_text())) if checkpoint.exists() else set()
        from time import sleep
        for offset in range(0,len(ids),64):
            selected=ids[offset:offset+64]
            if all(eid in committed for eid in selected):continue
            values={table:[row for eid in selected for row in records[table].get(eid,[])] for table,_ in SPECS}
            packed=source.execute("select extensions.pgp_sym_encrypt(%s,%s,'compress-algo=1,compress-level=6,cipher-algo=aes128,unicode-mode=1')",(json.dumps(values,default=str),transport_key)).fetchone()[0]
            for attempt in range(4):
                try:
                    with target.transaction():
                        live_batch={str(r[0]):r[1] for r in target.execute('select id,version from sm.employers where id=any(%s::uuid[]) for update',(selected,))}
                        if any(live_batch.get(eid) not in {expected[eid],staged_versions[eid]} for eid in selected):raise ValueError('A live employer changed during import')
                        target.execute(statement,(packed,transport_key))
                    target.commit()
                    break
                except psycopg.OperationalError:
                    target.close()
                    if attempt==3:raise
                    sleep(.5*(attempt+1))
                    target=psycopg.connect(Settings.from_env().database_url,connect_timeout=15)
            committed.update(selected)
            temporary=checkpoint.with_suffix('.tmp');temporary.write_text(json.dumps(sorted(committed)));temporary.replace(checkpoint)
            if offset%512==0:print(json.dumps({'committed_employers':len(committed),'total':len(ids)}),flush=True)
        target.execute('delete from sm.query_cache')
        target.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{matching_policy}','\"provided-csv-baseline-1\"'::jsonb) where id=%s",(report['artifact_id'],))
        target.commit()
        result={'published_employers':len(ids),'tables':counts,'private_rows_copied':0,'backup':str(backup_path)}
    (folder/'publication.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
