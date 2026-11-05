-- Signup credits are one-time service units, separate from paid billing periods.
alter table sm_private.credit_ledger alter column period_id drop not null;
alter table sm_private.credit_reservations alter column period_id drop not null;
create table sm_private.signup_credit_grants (
 user_id uuid primary key references sm_private.billing_accounts(user_id),
 credits integer not null default 10 check(credits=10),
 created_at timestamptz not null default now()
);
alter table sm_private.signup_credit_grants enable row level security;
revoke all on sm_private.signup_credit_grants from public;
create function sm_private.grant_signup_credits(account_id uuid) returns void
language plpgsql set search_path='' as $$
begin
 insert into sm_private.billing_accounts(user_id) values(account_id) on conflict do nothing;
 perform 1 from sm_private.billing_accounts where user_id=account_id for update;
 insert into sm_private.signup_credit_grants(user_id) values(account_id) on conflict do nothing;
 insert into sm_private.credit_ledger(id,user_id,period_id,delta,kind,reference)
 values(gen_random_uuid(),account_id,null,10,'grant','signup:'||account_id::text) on conflict(reference) do nothing;
end $$;
revoke all on function sm_private.grant_signup_credits(uuid) from public;
do $$ declare r text;begin
 foreach r in array array['anon','authenticated'] loop
 if exists(select 1 from pg_roles where rolname=r) then
 execute format('revoke all on sm_private.signup_credit_grants from %I',r);
 execute format('revoke all on function sm_private.grant_signup_credits(uuid) from %I',r);
 end if;end loop;
end $$;
-- Grant on confirmed signup where Supabase Auth is present. Also repaired on
-- verified account access for existing users and imported accounts.
create function sm_private.signup_credit_trigger() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.email_confirmed_at is not null then perform sm_private.grant_signup_credits(new.id);end if;
 return new;
end $$;
revoke all on function sm_private.signup_credit_trigger() from public;
do $$ begin
 if to_regclass('auth.users') is not null then
 execute 'create trigger sponsorreach_signup_credits after insert or update of email_confirmed_at on auth.users for each row execute function sm_private.signup_credit_trigger()';
 end if;
end $$;
