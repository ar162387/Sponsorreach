create table sm.import_dispositions (
 namespace text not null, record_key text not null, employer_id uuid not null,
 artifact_id text references sm.source_artifacts(id),
 status text not null check(status in ('archived','restored')),
 reason text not null, archive_path text not null, archive_sha256 text not null,
 raw_sha256 text not null, screened_at timestamptz not null default now(),
 primary key(namespace,record_key)
);
alter table sm.import_dispositions enable row level security;
revoke all on sm.import_dispositions from public;
