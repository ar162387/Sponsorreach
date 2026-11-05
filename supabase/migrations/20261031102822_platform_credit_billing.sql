-- Plan catalogue and fulfilment snapshots; credits remain internal service units.
create table sm_private.billing_plans(slug text not null,environment text not null check(environment in ('test','live')),name text not null,product_id text not null,amount_minor integer not null check(amount_minor>0),currency text not null default 'USD',interval text not null default 'month' check(interval='month'),credits integer not null check(credits>0),active boolean not null default false,primary key(slug,environment),unique(product_id,environment));
insert into sm_private.billing_plans values('monthly','test','SponsorReach Monthly','ff02e1f3-2a13-4eb9-ab18-0440e03527e3',1999,'USD','month',800,true);
create table sm_private.credit_costs(action text primary key,units integer not null check(units>0));
insert into sm_private.credit_costs values('search',1),('batch',1);
alter table sm_private.billing_periods drop constraint if exists billing_periods_allowance_check;
alter table sm_private.billing_periods add constraint positive_allowance check(allowance>0);
alter table sm_private.billing_periods add column plan_snapshot jsonb not null default '{}';
alter table sm_private.billing_payments drop constraint if exists billing_payments_currency_check;
alter table sm_private.billing_payments add column provider_session text unique;
alter table sm_private.billing_payments add column metadata jsonb not null default '{}';
alter table sm_private.billing_checkouts add column plan_snapshot jsonb not null default '{}';
alter table sm_private.billing_checkouts add column checkout_url text;
alter table sm_private.billing_checkouts add column expires_at timestamptz not null default now()+interval '30 minutes';
alter table sm_private.credit_reservations add column units integer not null default 1 check(units>0);
alter table sm_private.credit_ledger add column action text;
alter table sm_private.credit_ledger drop constraint if exists credit_ledger_kind_check;
alter table sm_private.credit_ledger add constraint ledger_kind check(kind in ('grant','search','batch','spend','expiry','refund'));
alter table sm_private.billing_events add column error_code text;
alter table sm_private.billing_events add column processed_at timestamptz;
alter table sm_private.refund_requests add column reason text not null default '';
alter table sm_private.refund_requests add column provider_note text;
create table sm_private.billing_sync(id text primary key,cursor integer not null default 0,last_success_at timestamptz,error_code text);
insert into sm_private.billing_sync(id) values('transactions');
-- Account-owned research outlives authentication/browser expiry.
alter table sm_private.candidate_profiles alter column expires_at drop not null;
alter table sm_private.match_sessions alter column expires_at drop not null;
update sm_private.candidate_profiles set expires_at=null where user_id is not null;
update sm_private.match_sessions set expires_at=null where user_id is not null;
-- Preserve legacy research without awarding fictional purchased credits.
insert into sm_private.billing_accounts(user_id) select distinct user_id from sm_private.match_sessions where user_id is not null on conflict do nothing;
update sm_private.billing_accounts a set preview_session=(select s.id from sm_private.match_sessions s where s.user_id=a.user_id and s.status='ready' and exists(select 1 from sm_private.match_results r where r.session_id=s.id) order by s.created_at,s.id limit 1);
insert into sm_private.batch_entitlements(user_id,session_id,batch) select distinct s.user_id,s.id,r.rank/20 from sm_private.match_sessions s join sm_private.match_results r on r.session_id=s.id where s.user_id is not null and s.access in ('paid','demo_unlocked') on conflict do nothing;
create function sm_private.protect_credit_ledger() returns trigger language plpgsql as $$ begin raise exception 'Credit ledger entries are append-only'; end $$;
create trigger credit_ledger_immutable before update or delete on sm_private.credit_ledger for each row execute function sm_private.protect_credit_ledger();
revoke all on function sm_private.protect_credit_ledger() from public;
do $$ declare t text;r text;begin foreach t in array array['billing_plans','credit_costs','billing_sync'] loop
execute format('alter table sm_private.%I enable row level security',t);
execute format('revoke all on sm_private.%I from public',t);
foreach r in array array['anon','authenticated'] loop if exists(select 1 from pg_roles where rolname=r) then execute format('revoke all on sm_private.%I from %I',t,r);end if;end loop;
end loop;end $$;
alter table sm_private.batch_entitlements add column environment text not null default 'test';
update sm_private.batch_entitlements set environment='legacy';
alter table sm_private.match_sessions add column billing_environment text;
