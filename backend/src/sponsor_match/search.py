from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
from psycopg.types.json import Jsonb
from .models import Profile
from .providers import embedding_provider, ProviderUnavailable
from .config import embedding_column
from .intelligence import digest
from .ranking import rank, rrf, Ranked, RANKING_VERSION, interleave_intents, distinctive_modifiers


class Matcher:
    def __init__(self, db, settings):
        self.db,self.settings = db,settings
        self.provider = embedding_provider(settings)

    def search(self, profile, progress=lambda _: None):
        taxonomy = self.db.taxonomy()
        context=self.db.one("""select
            (select max(updated_at) from sm.employers) revision,
            (select to_jsonb(i) from (select id,model,dimensions from sm.search_index_versions where active) i) active_index,
            (select id from sm.source_artifacts where kind='official_register' and metadata->>'active'='true' order by publication_date desc,imported_at desc limit 1) snapshot,
            (select id from sm.source_artifacts where kind='demo_register' and metadata->>'active'='true' order by publication_date desc,imported_at desc limit 1) demo_snapshot""")
        revision = str(context['revision'])
        column=embedding_column(self.settings)
        active_index=context['active_index']
        versions = {"ranking":RANKING_VERSION,"taxonomy":taxonomy.version,"catalogue":revision,"snapshot":context["snapshot"] or "","demo_snapshot":context["demo_snapshot"] or "","embedding":self.settings.embedding_model,"index":str(active_index['id']) if active_index else None}
        index_ready=bool(active_index and active_index['model']==self.settings.embedding_model and active_index['dimensions']==self.settings.dimensions and self.db.one(f"select exists(select 1 from sm.search_index_documents e join sm.search_documents d on d.id=e.document_id and d.content_hash=e.content_hash where e.index_id=%s and d.published and d.sponsor_eligible and e.{column} is not null) ready",(active_index['id'],))['ready'])
        cache_key = digest([profile.model_dump(),versions,bool(self.settings.openai_api_key),index_ready,self.settings.environment])
        cached = self.db.one("select payload from sm.query_cache where cache_key=%s and expires_at>now()",(cache_key,))
        if cached:
            return [Ranked(**r) for r in cached["payload"]["results"]],cached["payload"]["mode"],versions
        branches, similarities = [],{}
        def retrieval_label(intent):
            concept=taxonomy.resolve(intent.raw_label)
            return concept.label if concept and concept.id.startswith('bootstrap:') and not distinctive_modifiers(intent,concept,taxonomy) else intent.raw_label
        queries = [profile.model_copy(update={"role_intents":[intent.model_copy(update={'raw_label':retrieval_label(intent)})]}).search_text() for intent in profile.role_intents]
        mode = "hybrid"
        try:
            if not index_ready:
                raise ProviderUnavailable("semantic_index_not_ready")
            vectors = self.provider.embeddings(queries)
        except ProviderUnavailable:
            vectors = []
            mode = "lexical_concept_fallback"
        progress("Finding relevant sponsor employers")
        def retrieve(task):
            i,kind=task
            intent=profile.role_intents[i]
            concept = taxonomy.resolve(intent.raw_label)
            aliases = [retrieval_label(intent)] + (concept.aliases if concept else [])
            lexical_text = " OR ".join('"'+a.replace('"','')+'"' for a in aliases)
            if kind=="lexical":
                rows = self.db.rows("select employer_id,max(ts_rank_cd(fts,websearch_to_tsquery('english',%s))+ts_rank_cd(specialist_fts,websearch_to_tsquery('simple',%s))) as score from sm.search_documents where published and sponsor_eligible and (fts @@ websearch_to_tsquery('english',%s) or specialist_fts @@ websearch_to_tsquery('simple',%s)) group by employer_id order by score desc,employer_id limit 100",(lexical_text,lexical_text,lexical_text,lexical_text))
            elif kind in {"concept","related_concept"}:
                ids = [concept.id] if kind=='concept' else concept.related
                rows = self.db.rows("select distinct ec.employer_id from sm.employer_concepts ec where concept_id=any(%s) and exists(select 1 from sm.search_documents d where d.employer_id=ec.employer_id and d.published and d.sponsor_eligible) order by employer_id limit 100",(ids,))
            else:
                vector = json.dumps(vectors[i])
                with self.db.transaction() as c:
                    # pgvector>=0.8; extension version is checked at deployment.
                    c.execute("set local hnsw.iterative_scan='strict_order'; set local hnsw.ef_search=200")
                    rows = c.execute(f"select e.employer_id,e.{column} operator(extensions.<=>) %s::extensions.vector as distance from sm.search_index_documents e join sm.search_documents d on d.id=e.document_id and d.content_hash=e.content_hash where e.index_id=%s and d.published and d.sponsor_eligible and e.{column} is not null and e.facet=%s order by e.{column} operator(extensions.<=>) %s::extensions.vector limit 200",(vector,active_index['id'],kind,vector)).fetchall()
            return i,kind,rows
        tasks=[]
        for i,intent in enumerate(profile.role_intents):
            tasks.append((i,"lexical"))
            if taxonomy.resolve(intent.raw_label):tasks.append((i,"concept"))
            if profile.related_roles_enabled and taxonomy.resolve(intent.raw_label) and taxonomy.resolve(intent.raw_label).related:tasks.append((i,'related_concept'))
            if vectors:tasks.extend([(i,"function"),(i,"activity")])
        # Independent branches run concurrently; the database pool bounds connections.
        with ThreadPoolExecutor(max_workers=min(4,len(tasks))) as executor:
            for i,kind,rows in executor.map(retrieve,tasks):
                branches.append(('concept' if kind=='related_concept' else kind,[str(r["employer_id"]) for r in rows]))
                if kind in {"function","activity"}:
                    for row in rows:
                        intent_similarities=similarities.setdefault(str(row["employer_id"]),{})
                        label=profile.role_intents[i].raw_label
                        intent_similarities[label]=max(intent_similarities.get(label,0.),1-row["distance"])
        progress("Checking professional relevance")
        candidates=self.db.employers(rrf(branches))
        results=[]
        for employer in candidates:
            if employer.is_demo and self.settings.environment=="production":
                continue
            snapshot=versions["demo_snapshot"] if employer.is_demo else versions["snapshot"]
            result=rank(employer,profile,taxonomy,snapshot,similarities.get(employer.id,{}))
            if result:
                results.append(result)
        progress("Ranking your shortlist")
        direct=interleave_intents([r for r in results if r.group=="direct"],profile.role_intents,100)
        related=sorted([r for r in results if r.group=="related"],key=lambda r:(-r.score,r.employer_id))[:50]
        results=direct+related
        ttl=300 if mode=="lexical_concept_fallback" else 86400
        self.db.execute("insert into sm.query_cache values(%s,%s,now()+(%s*interval '1 second')) on conflict(cache_key) do update set payload=excluded.payload,expires_at=excluded.expires_at",(cache_key,Jsonb({"results":[asdict(r) for r in results],"mode":mode}),ttl))
        return results,mode,versions

    def process_session(self,id):
        row=self.db.one("select s.status,p.profile from sm_private.match_sessions s join sm_private.candidate_profiles p on p.id=s.profile_id where s.id=%s and s.expires_at>now()",(id,))
        if not row or row["status"]=="ready":
            return
        self.db.execute("update sm_private.match_sessions set status='processing' where id=%s",(id,))
        profile=Profile.model_validate(row["profile"])
        results,mode,versions=self.search(profile,lambda stage:self.db.execute("update sm_private.match_sessions set stage=%s where id=%s",(stage,id)))
        versions=dict(versions)
        if self.settings.embedding_provider=='local':
            from .prospects import ProspectLibrary,COHORT_VERSION
            try:
                if not hasattr(self,'prospect_library'):self.prospect_library=ProspectLibrary(self.settings)
                versions['prospect_cohorts']=self.prospect_library.associate(profile)
            except (OSError,ValueError,KeyError,ProviderUnavailable):
                # Optional analysis must not prevent delivery of a valid shortlist.
                versions['prospect_cohorts']={'available':False,'algorithm':COHORT_VERSION,'assignments':[]}
        self.db.save_results(id,results,mode,versions)
