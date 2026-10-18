create table sm.search_index_versions (
 id uuid primary key, model text not null, dimensions integer not null check(dimensions=768),
 taxonomy_version text not null, status text not null check(status in ('building','published')),
 active boolean not null default false, created_at timestamptz not null default now(), published_at timestamptz,
 check(not active or status='published')
);
create unique index one_active_search_index on sm.search_index_versions(active) where active;
create table sm.search_index_documents (
 index_id uuid references sm.search_index_versions(id), document_id text not null,
 employer_id uuid references sm.employers(id), content_hash text not null,
 facet text not null, content text not null, claim_ids jsonb not null,
 template_version text not null, embedding extensions.vector(768),
 primary key(index_id,document_id)
);
create index versioned_document_vector on sm.search_index_documents using hnsw(embedding extensions.vector_cosine_ops)
 where embedding is not null;
create index reusable_document_vector on sm.search_index_documents(document_id,content_hash) where embedding is not null;
alter table sm.search_index_versions enable row level security;
alter table sm.search_index_documents enable row level security;
revoke all on sm.search_index_versions,sm.search_index_documents from public;
