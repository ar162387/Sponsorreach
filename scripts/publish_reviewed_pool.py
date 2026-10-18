"""Atomically publish a reviewed CSV starter pool; excludes candidate/demo data.

Run from backend: uv run python ../scripts/publish_reviewed_pool.py ../data/pool/2026-10-14/approved.json
"""
import json
import sys
import gzip
from pathlib import Path
import psycopg
from psycopg import sql
from sponsor_match.config import Settings
from sponsor_match.intelligence import digest


def main():
    manifest_path=Path(sys.argv[1]);manifest=json.loads(manifest_path.read_text())
    ids=[]
    for item in manifest['employers']:
        draft=json.loads((manifest_path.parent/item['source_file']).read_text())
        if draft.get('review_status')!='accepted' or digest(draft)!=item['source_sha256']:raise ValueError('Review manifest hash mismatch')
        ids.append(item['employer_id'])
    if not ids:raise ValueError('Empty pool')
    specs=[('employers',['id']),('observations',['id']),('accepted_claims',['id']),('contact_channels',['id']),('sponsor_memberships',['employer_id','artifact_id','record_key']),('employer_concepts',['employer_id','concept_id','claim_id']),('search_documents',['id'])]
    with psycopg.connect('postgresql://localhost:55432/sponsormatch') as source,psycopg.connect(Settings.from_env().database_url,connect_timeout=15) as target:
        source.execute('set transaction isolation level repeatable read read only')
        target.execute("select pg_advisory_xact_lock(hashtextextended('sponsorreach:reviewed-pool',0))")
        current=target.execute('select id,name,is_demo from sm.employers where id=any(%s::uuid[])',(ids,)).fetchall()
        if len(current)!=len(ids) or any(r[2] for r in current):raise ValueError('Target employer identities differ')
        if target.execute('select exists(select 1 from sm.accepted_claims where employer_id=any(%s::uuid[]))',(ids,)).fetchone()[0]:raise ValueError('Pool already contains accepted evidence; use incremental review')
        if source.execute("select id from sm.source_artifacts where kind='official_register' and metadata->>'active'='true'").fetchone()!=target.execute("select id from sm.source_artifacts where kind='official_register' and metadata->>'active'='true'").fetchone():raise ValueError('Sponsor snapshot mismatch')
        size=target.execute('select pg_database_size(current_database())').fetchone()[0]
        if size>450*1024*1024:raise ValueError('Database is near the free-tier storage envelope; inspect capacity before adding data')
        backup={'employer_ids':ids,'tables':{},'private_rows_copied':0}
        for table,_ in specs:
            field='id' if table=='employers' else 'employer_id'
            query=sql.SQL('select row_to_json(t) from {} t where {}=any(%s::uuid[])').format(sql.Identifier('sm',table),sql.Identifier(field))
            backup['tables'][table]=[r[0] for r in target.execute(query,(ids,))]
        backup_path=manifest_path.parent/'prepublish-live-public.json.gz'
        if backup_path.exists():raise ValueError('Backup already exists; inspect the prior publication before retrying')
        with gzip.open(backup_path,'wt') as f:json.dump(backup,f,default=str)
        if json.loads(gzip.decompress(backup_path.read_bytes()))['employer_ids']!=ids:raise ValueError('Backup verification failed')
        counts={}
        for table,pks in specs:
            columns=[r[0] for r in source.execute("select column_name from information_schema.columns where table_schema='sm' and table_name=%s and is_generated='NEVER' order by ordinal_position",(table,))]
            cols=sql.SQL(',').join(map(sql.Identifier,columns));name=sql.Identifier('sm',table);temp=sql.Identifier('pool_'+table)
            target.execute(sql.SQL('create temp table {} (like {} including defaults) on commit drop').format(temp,name))
            field='id' if table=='employers' else 'employer_id'
            query=sql.SQL('select {} from {} where {}=any({}::uuid[])').format(cols,name,sql.Identifier(field),sql.Literal(ids))
            with source.cursor().copy(sql.SQL('copy ({}) to stdout').format(query)) as reader:
                with target.cursor().copy(sql.SQL('copy {} ({}) from stdin').format(temp,cols)) as writer:
                    buffer=bytearray()
                    for block in reader:buffer.extend(block)
                    if buffer:writer.write(buffer)
            conflict=sql.SQL(',').join(map(sql.Identifier,pks))
            changes=sql.SQL(',').join(sql.SQL('{}=excluded.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in columns if c not in pks)
            action=sql.SQL('do nothing') if table in {'observations','employer_concepts'} else sql.SQL('do update set {}').format(changes)
            target.execute(sql.SQL('insert into {} ({}) select {} from {} where true on conflict ({}) {}').format(name,cols,cols,temp,conflict,action))
            counts[table]=target.execute(sql.SQL('select count(*) from {}').format(temp)).fetchone()[0]
        target.execute('delete from sm.query_cache')
        print(json.dumps({'published_employers':len(ids),'tables':counts,'private_rows_copied':0}),flush=True)


if __name__=='__main__':main()
