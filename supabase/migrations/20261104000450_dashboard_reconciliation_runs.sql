-- Private operational status and a bounded lease shared by scheduled and staff runs.
create table sm_private.reconciliation_runs (
 id uuid primary key,
 environment text not null check(environment in ('test','live')),
 source text not null check(source in ('scheduled','manual')),
 actor_id uuid,
 status text not null default 'running' check(status in ('running','complete','partial','failed','interrupted')),
 started_at timestamptz not null default now(),
 lease_until timestamptz not null default now()+interval '10 minutes',
 finished_at timestamptz,
 error_count integer not null default 0,
 error_code text
);
create unique index reconciliation_single_running on sm_private.reconciliation_runs(environment) where status='running';
create index reconciliation_recent on sm_private.reconciliation_runs(environment,started_at desc);
alter table sm_private.reconciliation_runs enable row level security;
revoke all on sm_private.reconciliation_runs from public;
do $$ declare r text;begin foreach r in array array['anon','authenticated'] loop
if exists(select 1 from pg_roles where rolname=r) then execute format('revoke all on sm_private.reconciliation_runs from %I',r);end if;
end loop;end $$;
