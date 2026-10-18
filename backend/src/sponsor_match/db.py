from contextlib import contextmanager
from datetime import datetime, UTC, timedelta
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import time
import os
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from .models import Employer
from .catalogue_cache import CatalogueCache,TAXONOMY_SIGNATURE
from .intelligence import digest, documents, merge_employers, accepted
from .taxonomy import Taxonomy, Concept, key


def owner_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Database:
    def __init__(self, url):
        pool_size=int(os.getenv("SPONSORMATCH_DB_POOL_SIZE","4"))
        if not 1<=pool_size<=16:raise ValueError("Database pool size must be between 1 and 16")
        self.pool = ConnectionPool(url, min_size=1, max_size=pool_size, timeout=10, kwargs={"row_factory": dict_row,"autocommit":True}, open=False)
        self.catalogue_cache=CatalogueCache(url)
        self._taxonomy_cache=None
        self._taxonomy_cached_at=0.

    def open(self):
        self.pool.open(wait=True, timeout=10)

    def close(self):
        self.pool.close()

    @contextmanager
    def transaction(self):
        with self.pool.connection() as connection:
            with connection.transaction():
                yield connection

    def rows(self, query, params=()):
        # Single reads need no BEGIN/COMMIT network round trips. Multi-statement
        # publication and ownership mutations still use transaction() explicitly.
        with self.pool.connection() as c:
            return c.execute(query, params).fetchall()

    def one(self, query, params=()):
        rows = self.rows(query, params)
        return rows[0] if rows else None

    def execute(self, query, params=()):
        with self.transaction() as c:
            return c.execute(query, params).rowcount

    def migrate(self):
        folder = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
        with self.transaction() as c:
            c.execute("create table if not exists public.sponsormatch_migrations(name text primary key, sha256 text not null)")
            c.execute('alter table public.sponsormatch_migrations enable row level security')
            c.execute('revoke all on public.sponsormatch_migrations from public')
            # Supabase can grant public-schema tables to API roles by default.
            for role in ['anon','authenticated']:
                if c.execute('select 1 from pg_roles where rolname=%s',(role,)).fetchone():
                    from psycopg import sql
                    c.execute(sql.SQL('revoke all on public.sponsormatch_migrations from {}').format(sql.Identifier(role)))
            for path in sorted(folder.glob("*.sql")):
                content = path.read_text()
                checksum = hashlib.sha256(content.encode()).hexdigest()
                previous = c.execute("select sha256 from public.sponsormatch_migrations where name=%s", (path.name,)).fetchone()
                if previous:
                    if previous["sha256"] != checksum:
                        raise ValueError("An applied migration changed; create a new migration")
                    continue
                c.execute(content)
                c.execute("insert into public.sponsormatch_migrations values(%s,%s)", (path.name,checksum))

    def taxonomy(self):
        if self._taxonomy_cache and time.monotonic()-self._taxonomy_cached_at<30:
            return self._taxonomy_cache
        signature=self.one(TAXONOMY_SIGNATURE)['signature']
        cached=self.catalogue_cache.get_many('taxonomy',{'active':signature})
        if 'active' in cached:
            payloads=cached['active']
        else:
            payloads=[r['payload'] for r in self.rows("select payload from sm.concepts where kind='occupation' order by id")]
            self.catalogue_cache.put_many('taxonomy',{'active':(signature,payloads)})
        self._taxonomy_cache=Taxonomy([Concept(**p) for p in payloads]) if payloads else Taxonomy()
        self._taxonomy_cached_at=time.monotonic()
        return self._taxonomy_cache

    def seed_taxonomy(self, taxonomy=None):
        from dataclasses import asdict
        taxonomy = taxonomy or Taxonomy()
        with self.transaction() as c:
            with c.cursor() as cursor:
                cursor.executemany("insert into sm.concepts values(%s,%s,%s,%s,%s) on conflict(id) do update set label=excluded.label,version=excluded.version,payload=excluded.payload",[(concept.id,concept.label,concept.kind,concept.version,Jsonb(asdict(concept))) for concept in taxonomy.concepts])
                cursor.executemany("insert into sm.concept_aliases values(%s,%s) on conflict do nothing",[(concept.id,key(alias)) for concept in taxonomy.concepts for alias in [concept.label,*concept.aliases]])
                cursor.executemany("insert into sm.concept_edges values(%s,%s,'related',0.6,true,%s) on conflict do nothing",[(concept.id,related,concept.version) for concept in taxonomy.concepts for related in concept.related if related in taxonomy.by_id])
        self._taxonomy_cache=None

    def employer(self, id):
        row = self.one("select payload from sm.employers where id=%s", (id,))
        return Employer.model_validate(row["payload"]) if row else None

    def employers(self, ids):
        if not ids:
            return []
        # Version headers are small; changed/deleted records cannot be served
        # from a previous cached snapshot, including on saved-results rendering.
        headers=self.rows('select id,version from sm.employers where id=any(%s::uuid[])',(ids,))
        versions={str(r['id']):r['version'] for r in headers}
        payloads=self.catalogue_cache.get_many('employer',versions)
        missing=[eid for eid in versions if eid not in payloads]
        if missing:
            fresh=self.rows('select payload from sm.employers where id=any(%s::uuid[])',(missing,))
            updates={r['payload']['id']:(r['payload']['version'],r['payload']) for r in fresh}
            self.catalogue_cache.put_many('employer',updates)
            payloads.update({eid:payload for eid,(_,payload) in updates.items()})
        return [Employer.model_validate(payloads[eid]) for eid in versions if eid in payloads]


    def save_employer(self, employer, taxonomy=None):
        taxonomy = taxonomy or self.taxonomy()
        with self.transaction() as c:
            # Lock the canonical row so ingestion/revalidation cannot lose each other's updates.
            previous = c.execute("select payload from sm.employers where id=%s for update",(employer.id,)).fetchone()
            incoming_claims = list(employer.claims)
            def channel_observations():
                for channel in employer.channels:
                    c.execute("insert into sm.observations values(%s,%s,%s,%s,%s,%s,%s,'channels-1') on conflict(id) do nothing",(digest([employer.id,channel.model_dump(mode="json")]),employer.id,"channel:"+channel.kind,channel.state,channel.source_url,channel.observed_at,Jsonb(channel.model_dump(mode="json"))))
            def claim_observations(claims):
                for claim in claims:
                    data=claim.model_dump(mode="json")
                    c.execute("insert into sm.observations values(%s,%s,%s,%s,%s,%s,%s,'claims-2') on conflict(id) do nothing",(digest(["claim",employer.id,data]),employer.id,claim.kind,claim.state,claim.source_url,claim.observed_at,Jsonb(data)))
            if previous:
                channel_observations()
                claim_observations(incoming_claims)
            merged = merge_employers(Employer.model_validate(previous["payload"]) if previous else None, employer)
            merged.version = digest(merged.model_dump(exclude={"version"}))
            from .ranking import sponsor_valid
            snapshot=self.active_snapshot(merged.is_demo)
            eligible=merged.identity_status=="accepted" and sponsor_valid(merged,snapshot)
            taxonomy_changed=c.execute('select exists(select 1 from sm.search_documents where employer_id=%s and taxonomy_version<>%s) changed',(merged.id,taxonomy.version)).fetchone()['changed'] if previous else False
            if previous and previous["payload"].get("version") == merged.version and not taxonomy_changed:
                c.execute("update sm.search_documents set sponsor_eligible=%s where employer_id=%s",(eligible,merged.id))
                return merged
            c.execute("insert into sm.employers(id,name,name_key,town_key,company_number,identity_status,payload,is_demo,version) values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(id) do update set name=excluded.name,name_key=excluded.name_key,town_key=excluded.town_key,company_number=excluded.company_number,identity_status=excluded.identity_status,payload=excluded.payload,is_demo=excluded.is_demo,version=excluded.version,updated_at=now()",(merged.id,merged.name,key(merged.name),key(merged.town),merged.company_number or None,merged.identity_status,Jsonb(merged.model_dump(mode="json")),merged.is_demo,merged.version))
            if not previous:
                channel_observations()
                claim_observations(incoming_claims)
            c.execute("insert into sm.employer_source_keys values(%s,%s,%s) on conflict(namespace,record_key) do nothing",(merged.source_namespace,merged.source_key,merged.id))
            c.execute("delete from sm.employer_concepts where employer_id=%s",(merged.id,))
            c.execute("delete from sm.accepted_claims where employer_id=%s",(merged.id,))
            claim_observations(merged.claims)
            for claim in merged.claims:
                data = claim.model_dump(mode="json")
                if accepted(claim):
                    c.execute("insert into sm.accepted_claims(id,employer_id,kind,payload,observation_id) values(%s,%s,%s,%s,%s)",(claim.id,merged.id,claim.kind,Jsonb(data),digest(["claim",merged.id,data])))
                    for concept_id in taxonomy.inferred_concepts(claim.text,"activity" if claim.kind=="activity" else "function"):
                        c.execute("insert into sm.employer_concepts values(%s,%s,%s) on conflict do nothing",(merged.id,concept_id,claim.id))
            c.execute("delete from sm.contact_channels where employer_id=%s",(merged.id,))
            for channel in merged.channels:
                c.execute("insert into sm.contact_channels values(%s,%s,%s,%s,%s,%s,%s) on conflict(id) do update set payload=excluded.payload,state=excluded.state,attribution=excluded.attribution,observed_at=excluded.observed_at",(digest([merged.id,channel.kind,channel.value]),merged.id,channel.kind,channel.state,channel.attribution,channel.observed_at,Jsonb(channel.model_dump(mode="json"))))
            for vacancy in merged.vacancies:
                c.execute("insert into sm.vacancy_observations values(%s,%s,%s,%s,%s) on conflict(id) do nothing",(digest([merged.id,vacancy.model_dump(mode="json")]),merged.id,vacancy.state,vacancy.observed_at,Jsonb(vacancy.model_dump(mode="json"))))
            docs = documents(merged,taxonomy)
            c.execute("delete from sm.search_documents where employer_id=%s and not(id=any(%s::text[]))",(merged.id,[d["id"] for d in docs]))
            for doc in docs:
                c.execute("insert into sm.search_documents(id,employer_id,facet,content,claim_ids,content_hash,template_version,taxonomy_version,published) values(%s,%s,%s,%s,%s,%s,%s,%s,true) on conflict(id) do update set content=excluded.content,claim_ids=excluded.claim_ids,embedding=case when sm.search_documents.content_hash=excluded.content_hash then sm.search_documents.embedding else null end,embedding_model=case when sm.search_documents.content_hash=excluded.content_hash then sm.search_documents.embedding_model else null end,content_hash=excluded.content_hash,taxonomy_version=excluded.taxonomy_version,published=true",(doc["id"],merged.id,doc["facet"],doc["content"],Jsonb(doc["claim_ids"]),doc["content_hash"],doc["template_version"],doc["taxonomy_version"]))
            c.execute("update sm.search_documents set sponsor_eligible=%s where employer_id=%s",(eligible,merged.id))
            return merged

    def active_snapshot(self, demo=False):
        row = self.one("select id from sm.source_artifacts where kind=%s and (metadata->>'active')='true' order by publication_date desc,imported_at desc limit 1",("demo_register" if demo else "official_register",))
        return row["id"] if row else ""

    def create_session(self, request, token, user_id=None):
        hash = owner_hash(token)
        with self.transaction() as c:
            # Serialize identical retries without creating orphan profiles.
            c.execute("select pg_advisory_xact_lock(hashtextextended(%s,0))",(hash+request.idempotency_key,))
            existing = c.execute("select id from sm_private.match_sessions where owner_hash=%s and idempotency_key=%s and expires_at>now()",(hash,request.idempotency_key)).fetchone()
            if existing:
                return str(existing["id"])
            c.execute("delete from sm_private.match_sessions where owner_hash=%s and idempotency_key=%s and expires_at<=now()",(hash,request.idempotency_key))
            id, profile_id, job_id = str(uuid4()),str(uuid4()),str(uuid4())
            expiry = datetime.now(UTC)+timedelta(days=30)
            c.execute("insert into sm_private.candidate_profiles values(%s,%s,%s,%s,%s,%s,now(),%s)",(profile_id,user_id,hash,Jsonb(request.profile.model_dump()),Jsonb(request.identity.model_dump()),Jsonb(request.visa_context.model_dump()) if request.visa_context else None,expiry))
            c.execute("insert into sm_private.match_sessions(id,profile_id,user_id,owner_hash,idempotency_key,status,expires_at) values(%s,%s,%s,%s,%s,'queued',%s)",(id,profile_id,user_id,hash,request.idempotency_key,expiry))
            c.execute("insert into sm.work_items(id,kind,dedupe_key,payload) values(%s,'match',%s,%s)",(job_id,"match:"+id,Jsonb({"session_id":id})))
            return id

    def owned_session(self, id, token, user_id=None):
        return self.one("select s.*,p.profile,p.identity from sm_private.match_sessions s join sm_private.candidate_profiles p on p.id=s.profile_id where s.id=%s and s.expires_at>now() and (s.owner_hash=%s or (%s::uuid is not null and s.user_id=%s::uuid))",(id,owner_hash(token),user_id,user_id))

    def claim_work(self,kinds=None):
        return self.one("""with item as (select id from sm.work_items where available_at<=now() and (%s::text[] is null or kind=any(%s::text[])) and (state='pending' or (state='running' and leased_until<now())) order by available_at,created_at for update skip locked limit 1)
        update sm.work_items w set state='running',attempts=attempts+1,leased_until=now()+case when w.kind='build_prospects' then interval '30 minutes' else interval '2 minutes' end from item where w.id=item.id returning w.*""",(kinds,kinds))

    def finish_work(self, id):
        self.execute("update sm.work_items set state='done',leased_until=null,error_code=null where id=%s",(id,))

    def fail_work(self, item, code, max_attempts=3):
        dead = item["attempts"] >= max_attempts
        with self.transaction() as c:
            c.execute("update sm.work_items set state=%s,error_code=%s,leased_until=null,available_at=now()+(%s * interval '1 second') where id=%s",("dead" if dead else "pending",code,min(300,2**item["attempts"]),item["id"]))
            if dead and item["kind"]=="match":
                c.execute("update sm_private.match_sessions set status='failed',error_code=%s where id=%s",(code,item["payload"]["session_id"]))

    def save_results(self, id, results, mode, versions):
        with self.transaction() as c:
            c.execute("delete from sm_private.match_results where session_id=%s",(id,))
            for i,result in enumerate(results):
                c.execute("insert into sm_private.match_results values(%s,%s,%s,%s,%s,%s,%s,%s)",(id,result.employer_id,i,result.group,result.score,Jsonb(result.features),Jsonb(result.explanation),result.employer_version))
            c.execute("update sm_private.match_sessions set status='ready',stage='Your shortlist is ready',retrieval_mode=%s,versions=%s,error_code=null where id=%s",(mode,Jsonb(versions),id))
