-- Split earlier entitlements into five-company batches using existing result ranks.
create temporary table previous_batch_entitlements on commit drop as
select user_id, session_id, batch, created_at, environment
from sm_private.batch_entitlements;

delete from sm_private.batch_entitlements;
insert into sm_private.batch_entitlements (user_id, session_id, batch, created_at, environment)
select distinct b.user_id, b.session_id, r.rank / 5, b.created_at, b.environment
from previous_batch_entitlements b
join sm_private.match_results r on r.session_id = b.session_id and r.rank / 20 = b.batch;

update sm_private.match_sessions
set versions = jsonb_set(versions, '{refinement_batch}', to_jsonb((versions->>'refinement_batch')::integer * 4))
where jsonb_typeof(versions->'refinement_batch') = 'number';

alter table sm_private.signup_credit_grants
  alter column credits set default 5,
  drop constraint signup_credit_grants_credits_check,
  add constraint signup_credit_grants_credits_check check (credits in (5, 10));

create or replace function sm_private.grant_signup_credits(account_id uuid) returns void
language plpgsql set search_path='' as $$
begin
  insert into sm_private.billing_accounts(user_id) values(account_id) on conflict do nothing;
  perform 1 from sm_private.billing_accounts where user_id=account_id for update;
  insert into sm_private.signup_credit_grants(user_id) values(account_id) on conflict do nothing;
  insert into sm_private.credit_ledger(id,user_id,period_id,delta,kind,reference)
  select gen_random_uuid(), account_id, null, credits, 'grant', 'signup:'||account_id::text
  from sm_private.signup_credit_grants where user_id=account_id
  on conflict(reference) do nothing;
end $$;

alter table sm_private.billing_periods alter column allowance set default 100;
alter table sm_private.billing_plans alter column currency set default 'EUR';
update sm_private.billing_plans set active=false
where active and (currency <> 'EUR' or amount_minor <> 2499 or credits <> 100);
