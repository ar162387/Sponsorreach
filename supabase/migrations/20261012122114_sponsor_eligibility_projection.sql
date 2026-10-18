alter table sm.search_documents add column sponsor_eligible boolean not null default false;
drop index sm.document_vector;
create index document_vector on sm.search_documents using hnsw(embedding extensions.vector_cosine_ops)
 where published and sponsor_eligible and embedding is not null;
create index document_eligible on sm.search_documents(employer_id) where published and sponsor_eligible;
