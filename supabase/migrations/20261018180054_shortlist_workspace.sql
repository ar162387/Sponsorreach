alter table sm_private.match_sessions
 add column starred boolean not null default false,
 add column revision integer not null default 0,
 add column refresh_key text,
 add column updated_at timestamptz not null default now();
create index session_user_starred on sm_private.match_sessions(user_id,starred desc,created_at desc);
create table sm_private.employer_bookmarks (
 user_id uuid not null,
 employer_id uuid not null references sm.employers(id),
 session_id uuid references sm_private.match_sessions(id) on delete set null,
 result jsonb not null,
 created_at timestamptz not null default now(),
 primary key(user_id,employer_id)
);
alter table sm_private.employer_bookmarks enable row level security;
revoke all on sm_private.employer_bookmarks from public;
-- Server gateway enforces verified account ownership; direct clients default deny.
do $$ begin
 if exists(select 1 from pg_roles where rolname='anon') then
  revoke all on sm_private.employer_bookmarks from anon;
 end if;
 if exists(select 1 from pg_roles where rolname='authenticated') then
  revoke all on sm_private.employer_bookmarks from authenticated;
 end if;
end $$;
