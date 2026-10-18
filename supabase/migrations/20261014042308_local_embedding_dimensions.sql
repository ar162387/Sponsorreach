alter table sm.search_index_versions drop constraint search_index_versions_dimensions_check;
alter table sm.search_index_versions add constraint search_index_versions_dimensions_check check(dimensions in (384,768));
alter table sm.search_index_documents add column embedding_384 extensions.vector(384);
create index versioned_document_vector_384 on sm.search_index_documents using hnsw(embedding_384 extensions.vector_cosine_ops) where embedding_384 is not null;
create index reusable_document_vector_384 on sm.search_index_documents(document_id,content_hash) where embedding_384 is not null;
