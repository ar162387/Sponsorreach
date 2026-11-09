create table sm_private.member_signin_methods (
 provider text not null check (provider in ('google','facebook')),
 subject text not null,
 user_id uuid not null,
 primary key (provider,subject),
 unique (user_id,provider)
);

create table sm_private.member_signin_attempts (
 id uuid primary key,
 browser_hash text not null,
 provider text not null check (provider in ('google','facebook')),
 link_user_id uuid,
 shortlist_id uuid,
 subject text,
 suggested_email text,
 challenged_email text,
 state text not null default 'started' check (state in ('started','exchanging','verify')),
 expires_at timestamptz not null default now()+interval '10 minutes'
);
create index member_signin_attempts_expiry on sm_private.member_signin_attempts(expires_at);

create table sm_private.member_closures (
 user_id uuid primary key,
 request_id uuid not null unique,
 status text not null check (status in ('pending','purging','restored','purged')),
 purge_at timestamptz not null,
 receipt_email text,
 billing_checked_at timestamptz,
 last_attempt_at timestamptz,
 restored_at timestamptz
);
create index member_closures_pending on sm_private.member_closures(purge_at) where status in ('pending','purging');

do $$ declare t text; r text; begin
 foreach t in array array['member_signin_methods','member_signin_attempts','member_closures'] loop
  execute format('alter table sm_private.%I enable row level security',t);
  execute format('revoke all on sm_private.%I from public',t);
  foreach r in array array['anon','authenticated'] loop
   if exists(select 1 from pg_roles where rolname=r) then
    execute format('revoke all on sm_private.%I from %I',t,r);
   end if;
  end loop;
 end loop;
end $$;

update sm_private.billing_events
set payload = jsonb_build_object(
 'id', payload->'id', 'business', payload->'business', 'type', payload->'type', 'data',
 jsonb_strip_nulls(jsonb_build_object(
   'livemode', payload#>'{data,livemode}', 'sessionId', payload#>'{data,sessionId}', 'id', payload#>'{data,id}'
 ))
);

-- Financial activity stays append-only during normal operation. Only the
-- permanent erasure transaction can remove a closed member's credit history.
create or replace function sm_private.protect_credit_ledger() returns trigger
language plpgsql set search_path='' as $$
begin
 if tg_op='DELETE'
    and current_setting('sponsorreach.member_purge',true)=old.user_id::text
    and exists (select 1 from sm_private.member_closures where user_id=old.user_id and status='purging') then
  return old;
 end if;
 raise exception 'Credit ledger entries are append-only';
end $$;
