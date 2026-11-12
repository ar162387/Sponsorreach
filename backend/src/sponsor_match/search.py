from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from time import monotonic
import logging
from datetime import UTC, datetime
import json
from psycopg.types.json import Jsonb
from .models import Profile
from .providers import embedding_provider, ProviderUnavailable
from .config import embedding_column
from .intelligence import digest
from .ranking import rank, rrf, Ranked, RANKING_VERSION, interleave_intents, distinctive_modifiers, result_order
from .match_rules import ALIAS_VERSION, EXPLANATION_VERSION, LOCATION_VERSION, PROFESSION_VERSION


log = logging.getLogger(__name__)


class RegisterUnavailable(RuntimeError):
    pass


def order_group(results, intents, limit, group):
    ordered = []
    for matches_area in (True, False):
        bucket = [r for r in results if r.group == group and
                  (r.features['location_status'] == 'match') == matches_area]
        ordered.extend(interleave_intents(bucket, intents, limit - len(ordered))
                       if group == 'direct' else sorted(bucket, key=result_order)[:limit - len(ordered)])
        if len(ordered) >= limit:
            break
    return ordered


class Matcher:
    def __init__(self, db, settings):
        self.db,self.settings = db,settings
        self.provider = embedding_provider(settings)
        self.query_embeddings = OrderedDict()

    def embeddings(self, texts):
        now = monotonic()
        config = (self.settings.embedding_provider, self.settings.embedding_model,
                  self.settings.dimensions, PROFESSION_VERSION, ALIAS_VERSION)
        keys = [digest([config, text]) for text in texts]
        values, missing = {}, {}
        for cache_key, query in zip(keys, texts):
            cached = self.query_embeddings.get(cache_key)
            if cached and cached[0] > now:
                self.query_embeddings.move_to_end(cache_key)
                values[cache_key] = cached[1]
            else:
                self.query_embeddings.pop(cache_key, None)
                missing[cache_key] = query
        if missing:
            vectors = self.provider.embeddings(list(missing.values()))
            for cache_key, vector in zip(missing, vectors, strict=True):
                values[cache_key] = vector
                self.query_embeddings[cache_key] = (monotonic() + 86400, vector)
            while len(self.query_embeddings) > 512:
                self.query_embeddings.popitem(last=False)
        return [values[cache_key] for cache_key in keys]

    def search(self, profile, progress=lambda _: None):
        started = monotonic()
        taxonomy = self.db.taxonomy()
        context=self.db.one("""select
            (select max(updated_at) from sm.employers) revision,
            (select to_jsonb(i) from (select id,model,dimensions from sm.search_index_versions where active) i) active_index,
            (select id from sm.source_artifacts where kind='official_register' and metadata->>'active'='true' order by publication_date desc,imported_at desc limit 1) snapshot,
            (select publication_date from sm.source_artifacts where kind='official_register' and metadata->>'active'='true' order by publication_date desc,imported_at desc limit 1) publication,
            (select id from sm.source_artifacts where kind='demo_register' and metadata->>'active'='true' order by publication_date desc,imported_at desc limit 1) demo_snapshot""")
        publication = context.get('publication')
        if self.settings.environment == 'production' and (
            not publication or not 0 <= (datetime.now(UTC).date() - publication).days <= 7
        ):
            raise RegisterUnavailable('register_unavailable')
        revision = str(context['revision'])
        column=embedding_column(self.settings)
        active_index=context['active_index']
        versions = {"ranking":RANKING_VERSION,"taxonomy":taxonomy.version,"catalogue":revision,"snapshot":context["snapshot"] or "","demo_snapshot":context["demo_snapshot"] or "","embedding":self.settings.embedding_model,"index":str(active_index['id']) if active_index else None}
        versions.update(profession=PROFESSION_VERSION, aliases=ALIAS_VERSION,
                        location=LOCATION_VERSION, explanation=EXPLANATION_VERSION)
        index_ready=bool(active_index and active_index['model']==self.settings.embedding_model and active_index['dimensions']==self.settings.dimensions and self.db.one(f"select exists(select 1 from sm.search_index_documents e join sm.search_documents d on d.id=e.document_id and d.content_hash=e.content_hash where e.index_id=%s and d.published and d.sponsor_eligible and e.{column} is not null) ready",(active_index['id'],))['ready'])
        cache_key = digest([profile.model_dump(),versions,bool(self.settings.openai_api_key),index_ready,self.settings.environment])
        cached = self.db.one("select payload from sm.query_cache where cache_key=%s and expires_at>now()",(cache_key,))
        if cached:
            versions['diagnostics'] = cached['payload'].get('diagnostics', {})
            versions['timing_ms'] = {'result_cache': round((monotonic() - started) * 1000)}
            return [Ranked(**r) for r in cached["payload"]["results"]],cached["payload"]["mode"],versions
        branches, similarities = [],{}
        concept_candidates = set()
        targets = [taxonomy.intent_target(intent, profile) for intent in profile.role_intents]
        def retrieval_label(intent, concept):
            if concept and concept.metadata.get('architect_family'):
                return concept.label
            return concept.label if concept and concept.id.startswith('bootstrap:') and not distinctive_modifiers(intent,concept,taxonomy) else intent.raw_label
        queries = [profile.model_copy(update={"role_intents":[intent.model_copy(update={'raw_label':retrieval_label(intent, target)})]}).search_text() for intent, target in zip(profile.role_intents, targets)]
        embedding_started = monotonic()
        mode = "hybrid"
        try:
            if not index_ready:
                raise ProviderUnavailable("semantic_index_not_ready")
            vectors = self.embeddings(queries)
        except ProviderUnavailable:
            vectors = []
            mode = "lexical_concept_fallback"
        retrieval_started = monotonic()
        progress("Finding relevant sponsor employers")
        def retrieve(task):
            i,kind=task
            intent=profile.role_intents[i]
            concept = targets[i]
            aliases = [retrieval_label(intent, concept)] + (concept.aliases if concept else [])
            lexical_text = " OR ".join('"'+a.replace('"','')+'"' for a in aliases)
            if kind=="lexical":
                rows = self.db.rows("select employer_id,max(ts_rank_cd(fts,websearch_to_tsquery('english',%s))+ts_rank_cd(specialist_fts,websearch_to_tsquery('simple',%s))) as score from sm.search_documents where published and sponsor_eligible and (fts @@ websearch_to_tsquery('english',%s) or specialist_fts @@ websearch_to_tsquery('simple',%s)) group by employer_id order by score desc,employer_id limit 100",(lexical_text,lexical_text,lexical_text,lexical_text))
            elif kind in {"concept","related_concept"}:
                ids = [concept.id] if kind=='concept' else concept.related
                rows = self.db.rows("select distinct ec.employer_id from sm.employer_concepts ec where concept_id=any(%s) and exists(select 1 from sm.search_documents d where d.employer_id=ec.employer_id and d.published and d.sponsor_eligible)",(ids,))
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
            if targets[i]:
                tasks.append((i, "concept"))
                if profile.related_roles_enabled and targets[i].related:
                    tasks.append((i, 'related_concept'))
            if vectors:tasks.extend([(i,"function"),(i,"activity")])
        # Independent branches run concurrently; the database pool bounds connections.
        branch_capped = False
        with ThreadPoolExecutor(max_workers=max(1,min(4,len(tasks)))) as executor:
            for i,kind,rows in executor.map(retrieve,tasks):
                ids = [str(row['employer_id']) for row in rows]
                if kind in {'concept', 'related_concept'}:
                    concept_candidates.update(ids)
                else:
                    branches.append((kind, ids))
                    branch_capped |= len(rows) == (100 if kind == 'lexical' else 200)
                if kind in {"function","activity"}:
                    for row in rows:
                        intent_similarities=similarities.setdefault(str(row["employer_id"]),{})
                        label=profile.role_intents[i].raw_label
                        intent_similarities[label]=max(intent_similarities.get(label,0.),1-row["distance"])
        ranking_started = monotonic()
        progress("Checking professional relevance")
        candidates = sorted(set(rrf(branches)) | concept_candidates)
        diagnostics = dict(retrieved=len(candidates), eligible=0, profession_compatible=0,
                           match=0, out_of_area=0, unknown=0, unrestricted=0,
                           retrieval_capped=branch_capped, semantic_fallback=not bool(vectors))
        ranked = []
        for offset in range(0, len(candidates), 250):
            for employer in self.db.employers(candidates[offset:offset + 250]):
                if employer.is_demo and self.settings.environment == "production":
                    continue
                snapshot = versions["demo_snapshot"] if employer.is_demo else versions["snapshot"]
                result = rank(employer, profile, taxonomy, snapshot, similarities.get(employer.id, {}),
                              diagnostics=diagnostics)
                if result:
                    ranked.append(result)
        progress("Ranking your shortlist")
        main = [r for r in ranked if r.features['location_section'] == 'main']
        unknown = [r for r in ranked if r.features['location_section'] == 'unknown']
        direct = order_group(main, profile.role_intents, 100, 'direct')
        related = order_group(main, profile.role_intents, 50, 'related')
        extra = order_group(unknown, profile.role_intents, 20, 'direct')
        extra += order_group(unknown, profile.role_intents, 20 - len(extra), 'related')
        related = related[:150 - len(direct) - len(extra)]
        results = direct + related + extra
        diagnostics.update(returned_direct=len(direct), returned_related=len(related),
                           returned_unknown=len(extra))
        versions['diagnostics'] = diagnostics
        versions['timing_ms'] = {
            'setup': round((embedding_started - started) * 1000),
            'embedding': round((retrieval_started - embedding_started) * 1000),
            'retrieval': round((ranking_started - retrieval_started) * 1000),
            'hydration_ranking': round((monotonic() - ranking_started) * 1000),
        }
        ttl=300 if mode=="lexical_concept_fallback" else 86400
        self.db.execute("insert into sm.query_cache values(%s,%s,now()+(%s*interval '1 second')) on conflict(cache_key) do update set payload=excluded.payload,expires_at=excluded.expires_at",(cache_key,Jsonb({"results":[asdict(r) for r in results],"mode":mode,"diagnostics":diagnostics}),ttl))
        return results,mode,versions

    def process_session(self,id,revision=0):
        row=self.db.one("select s.status,s.revision,s.updated_at,p.profile from sm_private.match_sessions s join sm_private.candidate_profiles p on p.id=s.profile_id where s.id=%s and (s.expires_at is null or s.expires_at>now())",(id,))
        if not row or row["status"]=="ready" or row["revision"]!=revision:
            return
        queue_ms = max(0, round((datetime.now(UTC) - row['updated_at']).total_seconds() * 1000))
        self.db.execute("update sm_private.match_sessions set status='processing' where id=%s and revision=%s",(id,revision))
        profile=Profile.model_validate(row["profile"])
        results,mode,versions=self.search(profile,lambda stage:self.db.execute("update sm_private.match_sessions set stage=%s where id=%s and revision=%s",(stage,id,revision)))
        versions=dict(versions)
        if self.settings.embedding_provider=='local':
            from .prospects import ProspectLibrary,COHORT_VERSION
            try:
                if not hasattr(self,'prospect_library'):self.prospect_library=ProspectLibrary(self.settings)
                versions['prospect_cohorts']=self.prospect_library.associate(profile)
            except (OSError,ValueError,KeyError,ProviderUnavailable):
                # Optional analysis must not prevent delivery of a valid shortlist.
                versions['prospect_cohorts']={'available':False,'algorithm':COHORT_VERSION,'assignments':[]}
        persistence_started = monotonic()
        self.db.save_results(id,results,mode,versions,revision=revision)
        log.info('Match phases ms: %s, queue=%d, persistence=%d, candidates=%d',
                 versions.get('timing_ms', {}),
                 queue_ms,
                 round((monotonic() - persistence_started) * 1000),
                 versions.get('diagnostics', {}).get('retrieved', 0))
