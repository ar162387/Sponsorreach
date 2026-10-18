"""Copy only a chosen public CSV catalogue into an empty application schema.

Run from backend with `uv run --no-sync python ../scripts/publish_initial_catalogue.py`.
Credentials come from the application environment, never command arguments.
Future CSV batches use import-csv, not this initial bootstrap operation.
"""
import json
import psycopg
from psycopg import sql
from sponsor_match.config import Settings

NAMESPACE='local:nocodb:company-enrichment-v2'


def main():
    remote_url=Settings.from_env().database_url
    with psycopg.connect('postgresql://localhost:55432/sponsormatch') as source, psycopg.connect(remote_url,connect_timeout=15) as target:
        source.execute('set transaction isolation level repeatable read read only')
        target.execute("select pg_advisory_xact_lock(hashtextextended('sponsorreach:initial-catalogue',0))")
        if target.execute('select exists(select 1 from sm.employers)').fetchone()[0]:
            raise ValueError('Target already contains employers; use the incremental CSV importer')
        selected=sql.SQL("select id from sm.employers where not is_demo and payload->>'source_namespace'={}").format(sql.Literal(NAMESPACE))
        artifacts=sql.SQL("select id from sm.source_artifacts where (kind='historical_csv' and namespace={}) or kind='taxonomy' or (kind='official_register' and metadata->>'active'='true')").format(sql.Literal(NAMESPACE))
        employer_tables=['employer_source_keys','observations','accepted_claims','contact_channels','sponsor_memberships','employer_concepts','search_documents','vacancy_observations']
        tables=[('source_artifacts',sql.SQL('id in ({})').format(artifacts)),('employers',sql.SQL('id in ({})').format(selected)),('source_records',sql.SQL('artifact_id in ({})').format(artifacts)),('register_entries',sql.SQL('artifact_id in ({})').format(artifacts))]
        tables += [(name,sql.SQL('true')) for name in ['concepts','concept_aliases','concept_edges']]
        tables += [(name,sql.SQL('employer_id in ({})').format(selected)) for name in employer_tables]
        counts={}
        for table,where in tables:
            name=sql.Identifier('sm',table)
            # Explicit schema column order protects against accidental layout differences.
            columns=[r[0] for r in source.execute("select column_name from information_schema.columns where table_schema='sm' and table_name=%s and is_generated='NEVER' order by ordinal_position",(table,))]
            identifiers=sql.SQL(',').join(map(sql.Identifier,columns))
            query=sql.SQL('select {} from {} where {}').format(identifiers,name,where)
            count=source.execute(sql.SQL('select count(*) from ({}) selected').format(query)).fetchone()[0]
            with source.cursor().copy(sql.SQL('copy ({}) to stdout').format(query)) as reader:
                with target.cursor().copy(sql.SQL('copy {} ({}) from stdin').format(name,identifiers)) as writer:
                    buffer=bytearray()
                    for block in reader:
                        buffer.extend(block)
                        if len(buffer)>=1024*1024:
                            writer.write(buffer);buffer.clear()
                    if buffer:writer.write(buffer)
            counts[table]=count
            print(json.dumps({'copied':table,'rows':count}),flush=True)
        assert counts['employers']>0
        assert target.execute('select count(*) from sm.employers where is_demo').fetchone()[0]==0
        assert target.execute('select count(*) from sm_private.candidate_profiles').fetchone()[0]==0
        print(json.dumps({'committing_catalogue':counts['employers'],'private_candidate_rows_copied':0}),flush=True)


if __name__=='__main__':main()
