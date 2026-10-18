"""Resume compressed batches of a completed local embedding index; validate and publish atomically."""
import json
import secrets
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from sponsor_match.config import Settings,embedding_column
from types import SimpleNamespace


def main():
    with psycopg.connect('postgresql://localhost:55432/sponsormatch') as source,psycopg.connect(Settings.from_env().database_url,connect_timeout=15) as target:
        source.execute('set transaction isolation level repeatable read read only')
        transport_key=secrets.token_hex(16)
        target.execute("set local statement_timeout='10min'")
        version=source.execute('select id,model,dimensions,taxonomy_version from sm.search_index_versions where active').fetchone()
        if not version:raise ValueError('No active staged index')
        index_id,model,dimensions,taxonomy=version
        column=embedding_column(SimpleNamespace(dimensions=dimensions))
        target.execute("select pg_advisory_xact_lock(hashtextextended('sponsormatch:index-publication',0))")
        existing=target.execute('select status,active from sm.search_index_versions where id=%s',(index_id,)).fetchone()
        if existing and existing[1]:
            print(json.dumps({'published_index':str(index_id),'already_active':True}),flush=True);return
        if not existing:target.execute("insert into sm.search_index_versions(id,model,dimensions,taxonomy_version,status) values(%s,%s,%s,%s,'building')",(index_id,model,dimensions,taxonomy))
        target.commit()
        columns=[r[0] for r in source.execute("select column_name from information_schema.columns where table_schema='sm' and table_name='search_index_documents' order by ordinal_position")]
        cols=sql.SQL(',').join(map(sql.Identifier,columns))
        query=sql.SQL('select {} from sm.search_index_documents where index_id={}').format(cols,sql.Literal(index_id))
        insert=sql.SQL('insert into sm.search_index_documents ({}) select {} from jsonb_populate_recordset(null::sm.search_index_documents,extensions.pgp_sym_decrypt(%s,%s)::jsonb) on conflict(index_id,document_id) do nothing').format(cols,cols)
        existing_docs={r[0] for r in target.execute('select document_id from sm.search_index_documents where index_id=%s',(index_id,))};target.commit()
        rows=source.execute(query);count=len(existing_docs)
        from time import sleep
        while batch:=rows.fetchmany(64):
            values=[dict(zip(columns,row)) for row in batch if dict(zip(columns,row))['document_id'] not in existing_docs]
            if not values:continue
            packed=source.execute("select extensions.pgp_sym_encrypt(%s,%s,'compress-algo=1,compress-level=6,cipher-algo=aes128,unicode-mode=1')",(json.dumps(values,default=str),transport_key)).fetchone()[0]
            for attempt in range(4):
                try:
                    target.execute(insert,(packed,transport_key));target.commit();break
                except psycopg.OperationalError:
                    target.close()
                    if attempt==3:raise
                    sleep(.5*(attempt+1));target=psycopg.connect(Settings.from_env().database_url,connect_timeout=15)
            count+=len(values)
            if count%1024==0:print(json.dumps({'staged_embeddings':count}),flush=True)
        query=sql.SQL('''select count(*),count(distinct i.employer_id),count(*) filter(where i.{} is null or d.id is null or d.content_hash<>i.content_hash or not d.published or e.is_demo or e.payload->>'matching_basis'<>'provided_csv') from sm.search_index_documents i left join sm.search_documents d on d.id=i.document_id left join sm.employers e on e.id=i.employer_id where i.index_id=%s''').format(sql.Identifier(column))
        documents,employers,invalid=target.execute(query,(index_id,)).fetchone()
        expected=source.execute('select count(distinct employer_id) from sm.search_index_documents where index_id=%s',(index_id,)).fetchone()[0]
        if not documents or invalid or employers!=expected:raise ValueError('Incomplete or mismatched live index; previous index stays active')
        target.execute("select pg_advisory_xact_lock(hashtextextended('sponsormatch:index-publication',0))")
        target.execute('update sm.search_index_versions set active=false where active')
        target.execute("update sm.search_index_versions set active=true,status='published',published_at=now() where id=%s",(index_id,))
        target.execute('delete from sm.query_cache');target.commit()
    print(json.dumps({'published_index':str(index_id),'employers':employers,'documents':documents,'dimensions':dimensions,'model':model,'invalid_documents':invalid}),flush=True)


if __name__=='__main__':main()
