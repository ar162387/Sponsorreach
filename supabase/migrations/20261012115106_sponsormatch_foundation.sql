create schema if not exists extensions;
create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;
create schema if not exists sm;
create schema if not exists sm_private;
revoke all on schema sm, sm_private from public;

create table sm.source_artifacts (
 id text primary key, kind text not null, namespace text not null,
 url text not null default '', sha256 text not null, publication_date date,
 imported_at timestamptz not null default now(), metadata jsonb not null default '{}',
 unique(namespace,sha256)
);
create table sm.source_records (
 artifact_id text not null references sm.source_artifacts(id), record_key text not null,
 payload jsonb not null, primary key(artifact_id,record_key)
);
create table sm.employers (
 id uuid primary key, name text not null, name_key text not null, town_key text not null,
 company_number text, identity_status text not null,
 payload jsonb not null, is_demo boolean not null default false,
 version text not null, updated_at timestamptz not null default now()
);
create index employer_identity on sm.employers(name_key,town_key);
create index employer_company_number on sm.employers(company_number) where company_number is not null;
create table sm.employer_source_keys (
 namespace text not null, record_key text not null, employer_id uuid not null references sm.employers(id),
 primary key(namespace,record_key)
);
create table sm.employer_relationships (
 parent_id uuid references sm.employers(id), child_id uuid references sm.employers(id),
 kind text not null, evidence_id text not null, primary key(parent_id,child_id,kind)
);
create table sm.register_entries (
 artifact_id text references sm.source_artifacts(id), record_key text not null,
 name_key text not null, town_key text not null, route text not null, rating text not null,
 payload jsonb not null, primary key(artifact_id,record_key)
);
create index register_identity on sm.register_entries(artifact_id,name_key,town_key);
create table sm.sponsor_memberships (
 employer_id uuid references sm.employers(id), artifact_id text references sm.source_artifacts(id),
 record_key text not null, route text not null, rating text not null,
 attribution text not null, snapshot_date date not null,
 primary key(employer_id,artifact_id,record_key)
);
create table sm.observations (
 id text primary key, employer_id uuid references sm.employers(id), kind text not null,
 state text not null check(state in ('found','verified_absent','not_observed','inconclusive','temporarily_unavailable','blocked')),
 source_url text not null default '', observed_at timestamptz,
 payload jsonb not null, extraction_version text not null
);
create index observation_employer_time on sm.observations(employer_id,observed_at desc);
create table sm.accepted_claims (
 id text primary key references sm.observations(id), employer_id uuid references sm.employers(id),
 kind text not null, payload jsonb not null
);
create table sm.contact_channels (
 id text primary key, employer_id uuid references sm.employers(id),
 kind text not null, state text not null, attribution text not null,
 observed_at timestamptz, payload jsonb not null
);
create table sm.concepts (
 id text primary key, label text not null, kind text not null,
 version text not null, payload jsonb not null
);
create table sm.concept_aliases (
 concept_id text references sm.concepts(id), alias text not null,
 primary key(concept_id,alias)
);
create index concept_alias_lookup on sm.concept_aliases(alias);
create table sm.concept_edges (
 source_id text references sm.concepts(id), target_id text references sm.concepts(id),
 kind text not null, weight real not null, reviewed boolean not null default false,
 provenance text not null, primary key(source_id,target_id,kind)
);
create table sm.employer_concepts (
 employer_id uuid references sm.employers(id), concept_id text references sm.concepts(id),
 claim_id text references sm.observations(id), primary key(employer_id,concept_id,claim_id)
);
create index employer_concept_reverse on sm.employer_concepts(concept_id,employer_id);
create table sm.search_documents (
 id text primary key, employer_id uuid references sm.employers(id),
 facet text not null check(facet in ('activity','function')),
 content text not null, claim_ids jsonb not null,
 content_hash text not null, template_version text not null, taxonomy_version text not null,
 embedding_model text, embedding extensions.vector(768),
 published boolean not null default false,
 fts tsvector generated always as (to_tsvector('english', content)) stored,
 specialist_fts tsvector generated always as (to_tsvector('simple', content)) stored
);
create index document_fts on sm.search_documents using gin(fts);
create index document_specialist_fts on sm.search_documents using gin(specialist_fts);
create index document_vector on sm.search_documents using hnsw(embedding extensions.vector_cosine_ops)
 where published and embedding is not null;
create index document_employer on sm.search_documents(employer_id);
create table sm.vacancy_observations (
 id text primary key, employer_id uuid references sm.employers(id),
 state text not null, observed_at timestamptz, payload jsonb not null
);
create table sm_private.candidate_profiles (
 id uuid primary key, user_id uuid, owner_hash text not null,
 profile jsonb not null, identity jsonb not null, visa_context jsonb,
 created_at timestamptz not null default now(), expires_at timestamptz not null
);
create table sm_private.match_sessions (
 id uuid primary key, profile_id uuid references sm_private.candidate_profiles(id),
 user_id uuid, owner_hash text not null, idempotency_key text not null,
 status text not null check(status in ('queued','processing','needs_clarification','ready','failed')),
 stage text not null default 'Understanding your career interests',
 access text not null default 'preview' check(access in ('preview','demo_unlocked','paid')),
 error_code text, retrieval_mode text not null default 'pending', versions jsonb not null default '{}',
 created_at timestamptz not null default now(), expires_at timestamptz not null,
 unique(owner_hash,idempotency_key)
);
create index session_owner_time on sm_private.match_sessions(owner_hash,created_at desc);
create index session_user_time on sm_private.match_sessions(user_id,created_at desc);
create table sm_private.match_results (
 session_id uuid references sm_private.match_sessions(id) on delete cascade,
 employer_id uuid references sm.employers(id), rank integer not null,
 group_name text not null check(group_name in ('direct','related')),
 score real not null, features jsonb not null, explanation jsonb not null,
 employer_version text not null, primary key(session_id,employer_id), unique(session_id,rank)
);
create table sm_private.feedback_events (
 id uuid primary key, session_id uuid references sm_private.match_sessions(id) on delete cascade,
 employer_id uuid not null, event text not null, position integer, note text,
 created_at timestamptz not null default now()
);
create table sm.evaluation_labels (
 profile_id text not null, employer_id uuid references sm.employers(id),
 reviewer_id text not null, label text not null, explanation_supported boolean,
 payload jsonb not null, primary key(profile_id,employer_id,reviewer_id)
);
create table sm.work_items (
 id uuid primary key, kind text not null, dedupe_key text unique,
 payload jsonb not null, state text not null default 'pending', attempts integer not null default 0,
 available_at timestamptz not null default now(), leased_until timestamptz,
 error_code text, created_at timestamptz not null default now()
);
create index work_pending on sm.work_items(available_at) where state='pending';
create table sm.sync_cursors (
 namespace text primary key, cursor jsonb not null, updated_at timestamptz not null default now()
);
create table sm.rule_versions (
 id text primary key, source_url text not null, source_hash text not null,
 effective_from date not null, effective_to date, payload jsonb not null
);
create table sm.rule_screens (
 id uuid primary key, rule_version text references sm.rule_versions(id),
 state text not null default 'not_evaluated', inputs jsonb not null, outputs jsonb not null
);
create table sm.query_cache (
 cache_key text primary key, payload jsonb not null, expires_at timestamptz not null
);

-- Private schemas are not exposed through the Supabase Data API. Default deny
-- also protects direct clients; only the server's database role may read bulk data.
do $$ declare t record; begin
 for t in select schemaname,tablename from pg_tables where schemaname in ('sm','sm_private') loop
  execute format('alter table %I.%I enable row level security',t.schemaname,t.tablename);
  execute format('revoke all on %I.%I from public',t.schemaname,t.tablename);
 end loop;
 if to_regprocedure('auth.uid()') is not null then
  execute 'create policy profile_owner on sm_private.candidate_profiles for select to authenticated using ((select auth.uid())=user_id)';
  execute 'create policy session_owner on sm_private.match_sessions for select to authenticated using ((select auth.uid())=user_id)';
  execute 'create policy result_owner on sm_private.match_results for select to authenticated using (exists(select 1 from sm_private.match_sessions s where s.id=session_id and s.user_id=(select auth.uid())))';
 end if;
end $$;
