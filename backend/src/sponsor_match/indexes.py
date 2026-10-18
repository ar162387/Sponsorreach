"""Immutable semantic snapshots; publish only complete builds and retain rollback versions."""
import json
from uuid import UUID,uuid4
from .providers import embedding_provider
from .config import embedding_column
from types import SimpleNamespace


def publish_index(db,index_id):
    with db.transaction() as c:
        c.execute("select pg_advisory_xact_lock(hashtextextended('sponsormatch:index-publication',0))")
        version=c.execute("select * from sm.search_index_versions where id=%s for update",(index_id,)).fetchone()
        if not version:raise ValueError('Unknown index')
        column=embedding_column(SimpleNamespace(dimensions=version['dimensions']))
        counts=c.execute(f"select count(*) total,count(*) filter(where {column} is null) missing from sm.search_index_documents where index_id=%s",(index_id,)).fetchone()
        if not version or not counts['total'] or counts['missing']:
            raise ValueError("Only a complete nonempty index can be published")
        c.execute("update sm.search_index_versions set active=false where active")
        c.execute("update sm.search_index_versions set status='published',active=true,published_at=coalesce(published_at,now()) where id=%s",(index_id,))
        c.execute("delete from sm.query_cache")
    return {"published_index":str(index_id),"model":version['model'],"documents":counts['total']}


def build_index(db,settings,batch_size=32,resume=None,provider=None):
    provider=provider or embedding_provider(settings)
    column=embedding_column(settings)
    index_id=str(UUID(resume)) if resume else str(uuid4())
    if resume:
        version=db.one("select * from sm.search_index_versions where id=%s",(index_id,))
        if not version or version['status']!='building' or version['model']!=settings.embedding_model or version['dimensions']!=settings.dimensions:
            raise ValueError("Resume a building index with the same embedding model")
    else:
        with db.transaction() as c:
            c.execute("insert into sm.search_index_versions(id,model,dimensions,taxonomy_version,status) values(%s,%s,%s,%s,'building')",(index_id,settings.embedding_model,settings.dimensions,db.taxonomy().version))
            # Freeze the facet contents in one statement. Phone-only updates reuse vectors.
            c.execute(f"""insert into sm.search_index_documents(index_id,document_id,employer_id,content_hash,facet,content,claim_ids,template_version,{column})
                select %s,d.id,d.employer_id,d.content_hash,d.facet,d.content,d.claim_ids,d.template_version,reused.{column}
                from sm.search_documents d left join lateral (
                  select e.{column} from sm.search_index_documents e join sm.search_index_versions v on v.id=e.index_id
                  where e.document_id=d.id and e.content_hash=d.content_hash and e.{column} is not null and v.model=%s limit 1
                ) reused on true where d.published and (%s or not exists(select 1 from sm.employers e where e.id=d.employer_id and e.is_demo))""",(index_id,settings.embedding_model,settings.environment!='production'))
    generated=0
    while True:
        rows=db.rows(f"select document_id,content from sm.search_index_documents where index_id=%s and {column} is null order by document_id limit %s",(index_id,min(64,max(1,batch_size))))
        if not rows:break
        vectors=provider.embeddings([r['content'] for r in rows])
        if len(vectors)!=len(rows):
            raise ValueError('Embedding batch is incomplete')
        with db.transaction() as c:
            with c.cursor() as cursor:
                cursor.executemany(f"update sm.search_index_documents set {column}=%s::extensions.vector where index_id=%s and document_id=%s and {column} is null",[(json.dumps(vector),index_id,row['document_id']) for row,vector in zip(rows,vectors)])
        generated+=len(rows)
    result=publish_index(db,index_id)
    return {**result,"generated_documents":generated}
