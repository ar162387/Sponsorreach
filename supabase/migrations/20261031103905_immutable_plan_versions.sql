create function sm_private.protect_plan_contract() returns trigger language plpgsql as $$ begin
if (new.product_id,new.amount_minor,new.currency,new.interval,new.credits,new.environment,new.slug) is distinct from (old.product_id,old.amount_minor,old.currency,old.interval,old.credits,old.environment,old.slug) then raise exception 'Create a new plan version instead of changing a sold contract';end if;return new;end $$;
create trigger plan_contract_immutable before update on sm_private.billing_plans for each row execute function sm_private.protect_plan_contract();
revoke all on function sm_private.protect_plan_contract() from public;
