create table sm_private.support_tickets(id uuid primary key,user_id uuid not null,subject text not null check(length(subject) between 1 and 160),message text not null check(length(message) between 1 and 4000),status text not null default 'open' check(status in ('open','closed')),created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table sm_private.support_replies(id uuid primary key,ticket_id uuid not null references sm_private.support_tickets on delete cascade,actor_id uuid not null,is_staff boolean not null,message text not null check(length(message) between 1 and 4000),created_at timestamptz not null default now());
create table sm_private.admin_audit(id uuid primary key,actor_id uuid not null,action text not null,target_id uuid not null,created_at timestamptz not null default now());
create index support_owner on sm_private.support_tickets(user_id,created_at desc);
do $$ declare t text; r text; begin foreach t in array array['support_tickets','support_replies','admin_audit'] loop
execute format('alter table sm_private.%I enable row level security',t);
execute format('revoke all on sm_private.%I from public',t);
foreach r in array array['anon','authenticated'] loop
if exists(select 1 from pg_roles where rolname=r) then execute format('revoke all on sm_private.%I from %I',t,r); end if;
end loop; end loop; end $$;
