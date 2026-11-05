-- Server-owned billing. No browser role may mutate or read these tables directly.
create table sm_private.billing_accounts(user_id uuid primary key, preview_session uuid, created_at timestamptz not null default now());
create table sm_private.billing_checkouts(id uuid primary key, user_id uuid not null references sm_private.billing_accounts, environment text not null check(environment in ('test','live')), product_id text not null, provider_session text unique, status text not null default 'pending', created_at timestamptz not null default now());
create unique index billing_pending_checkout on sm_private.billing_checkouts(user_id,environment) where status='pending';
create table sm_private.billing_subscriptions(id text primary key,user_id uuid not null references sm_private.billing_accounts,environment text not null,status text not null,product_id text not null,cancel_at_period_end boolean not null default false,period_end timestamptz,updated_at timestamptz not null default now());
create table sm_private.billing_periods(id uuid primary key,user_id uuid not null references sm_private.billing_accounts,subscription_id text not null references sm_private.billing_subscriptions,starts_at timestamptz not null,ends_at timestamptz not null,allowance integer not null default 800 check(allowance=800),revoked boolean not null default false,check(ends_at>starts_at),unique(subscription_id,ends_at));
create table sm_private.billing_payments(id text primary key,checkout_id uuid references sm_private.billing_checkouts,period_id uuid references sm_private.billing_periods,invoice_id text,amount_minor integer not null,currency text not null check(currency='USD'),status text not null,paid_at timestamptz not null);
create table sm_private.credit_ledger(id uuid primary key,user_id uuid not null references sm_private.billing_accounts,period_id uuid not null references sm_private.billing_periods,delta integer not null,kind text not null check(kind in ('grant','search','batch','expiry','refund')),reference text not null unique,session_id uuid,created_at timestamptz not null default now());
create table sm_private.credit_reservations(id uuid primary key,user_id uuid not null references sm_private.billing_accounts,period_id uuid not null references sm_private.billing_periods,session_id uuid not null unique,expires_at timestamptz not null,state text not null default 'reserved' check(state in ('reserved','committed','released')));
create table sm_private.batch_entitlements(user_id uuid not null,session_id uuid not null references sm_private.match_sessions on delete cascade,batch integer not null check(batch>=0),created_at timestamptz not null default now(),primary key(user_id,session_id,batch));
create table sm_private.billing_events(id text primary key,payload jsonb not null,status text not null default 'pending',attempts integer not null default 0,created_at timestamptz not null default now());
create table sm_private.refund_requests(id uuid primary key,user_id uuid not null,payment_id text not null unique references sm_private.billing_payments,status text not null default 'pending',created_at timestamptz not null default now());
create index credit_ledger_account_time on sm_private.credit_ledger(user_id,created_at desc);
create index reservation_pending on sm_private.credit_reservations(expires_at) where state='reserved';
do $$ declare t record; r text; begin
 for t in select tablename from pg_tables where schemaname='sm_private' and tablename in ('billing_accounts','billing_checkouts','billing_subscriptions','billing_periods','billing_payments','credit_ledger','credit_reservations','batch_entitlements','billing_events','refund_requests') loop
 execute format('alter table sm_private.%I enable row level security',t.tablename);
 execute format('revoke all on sm_private.%I from public',t.tablename);
 foreach r in array array['anon','authenticated'] loop
 if exists(select 1 from pg_roles where rolname=r) then execute format('revoke all on sm_private.%I from %I',t.tablename,r); end if;
 end loop;
 end loop;
end $$;
