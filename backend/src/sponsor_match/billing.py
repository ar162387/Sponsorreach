"""Private transactional credit accounting. Provider integration must call these only after verification.

All spending and payment fulfilment are server-authoritative.
"""
from datetime import datetime, UTC, timedelta
from uuid import uuid4
import os
from psycopg.types.json import Jsonb

def billing_enabled():
    return os.getenv("BILLING_MODE","off") in ("test","live") or os.getenv("BILLING_ENFORCE_CREDITS", "false")=="true"

def credit_environment():
    return "live" if os.getenv("BILLING_MODE")=="live" or os.getenv("AGENTAOS_API_KEY","").startswith("sk_live_") else "test"

def spending_enabled():
    return os.getenv("BILLING_MODE","off") in ("test","live")

def cost(c,action):
    row=c.execute("select units from sm_private.credit_costs where action=%s",(action,)).fetchone()
    if not row:raise ValueError("Unknown credit action")
    return row["units"]


class InsufficientCredits(ValueError): pass

def lock_account(c, user_id):
    c.execute("insert into sm_private.billing_accounts(user_id) values(%s) on conflict do nothing", (user_id,))
    c.execute("select user_id from sm_private.billing_accounts where user_id=%s for update", (user_id,)).fetchone()

def current_period(c, user_id):
    return c.execute("select p.* from sm_private.billing_periods p join sm_private.billing_subscriptions s on s.id=p.subscription_id where p.user_id=%s and s.environment=%s and p.starts_at<=now() and p.ends_at>now() and not p.revoked and not p.suspended order by p.starts_at desc limit 1 for update of p", (user_id,credit_environment())).fetchone()

def available(c, period):
    if not period: return 0
    row=c.execute("select coalesce(sum(delta),0) balance from sm_private.credit_ledger where period_id=%s", (period['id'],)).fetchone()
    held=c.execute("select coalesce(sum(units),0) n from sm_private.credit_reservations where period_id=%s and state='reserved' and expires_at>now()", (period['id'],)).fetchone()
    return max(0,row['balance']-held['n'])

def entry(c,user_id,period_id,delta,kind,reference,session_id=None):
    c.execute("insert into sm_private.credit_ledger(id,user_id,period_id,delta,kind,reference,session_id) values(%s,%s,%s,%s,%s,%s,%s)", (str(uuid4()),user_id,period_id,delta,kind,reference,session_id))

def signup_available(c, user_id):
    row=c.execute("select coalesce(sum(delta),0) n from sm_private.credit_ledger where user_id=%s and period_id is null",(user_id,)).fetchone()
    held=c.execute("select coalesce(sum(units),0) n from sm_private.credit_reservations where user_id=%s and period_id is null and state='reserved' and expires_at>now()",(user_id,)).fetchone()
    return max(0,row['n']-held['n'])

def funding(c,user_id,units):
    # Spend the one-time signup balance first. It is never renewed by payment.
    if signup_available(c,user_id)>=units:return None
    period=current_period(c,user_id)
    if available(c,period)<units:raise InsufficientCredits('Your credits are used up. Subscribe to continue searching.')
    return period

def batch_value(c, user_id, session_id, batch, employer_ids=None):
    """Count distinct real companies and those already unlocked on this account.

    Call under the account lock so concurrent deliveries cannot both charge for
    the same companies. Locked results in other shortlists do not count as seen.
    """
    rows=c.execute("""select distinct r.employer_id from sm_private.match_results r
        join sm.employers e on e.id=r.employer_id
        where r.session_id=%s and r.rank>=%s and r.rank<%s and not e.is_demo""",
        (session_id,batch*20,(batch+1)*20)).fetchall()
    permitted={str(id) for id in employer_ids} if employer_ids is not None else None
    ids=[row['employer_id'] for row in rows if permitted is None or str(row['employer_id']) in permitted]
    if not ids:return {'total':0,'repeated':0,'chargeable':False}
    seen=c.execute("""select distinct r.employer_id from sm_private.match_results r
        join sm_private.match_sessions s on s.id=r.session_id
        where s.user_id=%s and r.employer_id=any(%s) and r.session_id<>%s
        and (s.billing_environment is null or s.billing_environment=%s)
        and (s.access in ('paid','demo_unlocked') or exists(
            select 1 from sm_private.batch_entitlements b where b.user_id=%s
            and b.session_id=s.id and b.batch=r.rank/20
            and b.environment in (%s,'legacy')))""",
        (user_id,ids,session_id,credit_environment(),user_id,credit_environment())).fetchall()
    repeated=len(seen)
    return {'total':len(ids),'repeated':repeated,'chargeable':repeated*2<=len(ids)}


class Credits:
    def __init__(self, db): self.db=db

    def ensure_signup(self,user_id):
        with self.db.transaction() as c:
            c.execute("""select sm_private.grant_signup_credits(%s) where not exists (
                select 1 from sm_private.member_closures where user_id=%s and status<>'restored')""",(user_id,user_id))

    def reserve(self,user_id,session_id):
        with self.db.transaction() as c:
            return self.reserve_in(c,user_id,session_id)

    def reserve_in(self,c,user_id,session_id):
        lock_account(c,user_id)
        existing=c.execute("select * from sm_private.credit_reservations where session_id=%s",(session_id,)).fetchone()
        if existing:
            if str(existing['user_id'])!=str(user_id): raise ValueError('Reservation ownership mismatch')
            return existing
        units=cost(c,'search')
        period=funding(c,user_id,units)
        return c.execute("insert into sm_private.credit_reservations(id,user_id,period_id,session_id,expires_at,units) values(%s,%s,%s,%s,least(%s, %s),%s) returning *",(str(uuid4()),user_id,period['id'] if period else None,session_id,datetime.now(UTC)+timedelta(minutes=10),period['ends_at'] if period else datetime.now(UTC)+timedelta(minutes=10),units)).fetchone()

    def settle(self,user_id,session_id,nonempty):
        # Caller must invoke inside the transaction that persists the results.
        with self.db.transaction() as c:
            return self.settle_in(c,user_id,session_id,nonempty)

    def settle_in(self,c,user_id,session_id,nonempty,chargeable=True):
        lock_account(c,user_id)
        r=c.execute("select r.*,coalesce(p.revoked,false) revoked,coalesce(p.suspended,false) suspended,p.ends_at from sm_private.credit_reservations r left join sm_private.billing_periods p on p.id=r.period_id where r.session_id=%s and r.user_id=%s for update of r",(session_id,user_id)).fetchone()
        if not r or r['state']!='reserved': return False
        valid=nonempty and not r['revoked'] and not r['suspended'] and min(r['expires_at'],r['ends_at'] or r['expires_at'])>datetime.now(UTC)
        charged=valid and chargeable
        if charged:
            entry(c,user_id,r['period_id'],-r['units'],'search','search:'+str(session_id),session_id)
        if valid:
            c.execute("insert into sm_private.batch_entitlements(user_id,session_id,batch,environment) values(%s,%s,0,%s) on conflict do nothing",(user_id,session_id,credit_environment()))
        c.execute("update sm_private.credit_reservations set state=%s where id=%s",('committed' if charged else 'released',r['id']))
        return bool(charged)

    def unlock_in(self,c,user_id,session_id,batch,nonempty,employer_ids=None):
        if not isinstance(batch,int) or batch<0: raise ValueError('Invalid batch')
        lock_account(c,user_id)
        if c.execute("select 1 from sm_private.batch_entitlements where user_id=%s and session_id=%s and batch=%s",(user_id,session_id,batch)).fetchone(): return False
        if not nonempty: return False
        value=batch_value(c,user_id,session_id,batch,employer_ids)
        if value['total'] and not value['chargeable']:
            if batch==0:self.settle_in(c,user_id,session_id,True,chargeable=False)
            c.execute("insert into sm_private.batch_entitlements(user_id,session_id,batch,environment) values(%s,%s,%s,%s) on conflict do nothing",(user_id,session_id,batch,credit_environment()))
            return False
        if batch==0:
            reservation=c.execute("select id from sm_private.credit_reservations where user_id=%s and session_id=%s and state='reserved'",(user_id,session_id)).fetchone()
            if reservation and self.settle_in(c,user_id,session_id,True):return True
        units=cost(c,'batch')
        period=funding(c,user_id,units)
        entry(c,user_id,period['id'] if period else None,-units,'batch',f'batch:{user_id}:{session_id}:{batch}',session_id)
        c.execute("insert into sm_private.batch_entitlements(user_id,session_id,batch,environment) values(%s,%s,%s,%s)",(user_id,session_id,batch,credit_environment()))
        return True

    def revoke(self,period_id,kind='refund'):
        with self.db.transaction() as c:
            return self.revoke_in(c,period_id,kind)

    def revoke_in(self,c,period_id,kind='refund'):
        if kind not in ('refund','expiry'):raise ValueError('Invalid reversal')
        owner=c.execute('select user_id from sm_private.billing_periods where id=%s',(period_id,)).fetchone()
        if not owner:raise ValueError('Unknown paid period')
        lock_account(c,owner['user_id'])
        p=c.execute('select * from sm_private.billing_periods where id=%s for update',(period_id,)).fetchone()
        if p['revoked']:return
        c.execute("update sm_private.credit_reservations set state='released' where period_id=%s and state='reserved'",(period_id,))
        balance=c.execute('select coalesce(sum(delta),0) n from sm_private.credit_ledger where period_id=%s',(period_id,)).fetchone()['n']
        if balance>0:entry(c,p['user_id'],period_id,-balance,kind,kind+':'+str(period_id))
        c.execute('update sm_private.billing_periods set revoked=true where id=%s',(period_id,))

    def release_abandoned(self):
        return self.db.execute("update sm_private.credit_reservations set state='released' where state='reserved' and expires_at<=now()")

    def record_verified_payment(self, *, user_id, subscription_id, payment_id, invoice_id, starts_at, ends_at, environment, product_id, allowance=800, amount_minor=1999, currency="USD", plan_snapshot=None, provider_session=None, metadata=None, paid_at=None, payment_state="paid"):
        """Internal-only operation; the caller must verify provider payment and correlation first."""
        if environment not in ('test','live') or ends_at<=starts_at or allowance<1 or amount_minor<0: raise ValueError('Invalid paid period')
        with self.db.transaction() as c:
            lock_account(c,user_id)
            closed=c.execute("select 1 from sm_private.member_closures where user_id=%s and status='purged'",(user_id,)).fetchone()
            sub=c.execute('select * from sm_private.billing_subscriptions where id=%s for update',(subscription_id,)).fetchone()
            if sub and (str(sub['user_id'])!=str(user_id) or sub['environment']!=environment or sub['product_id']!=product_id): raise ValueError('Subscription correlation mismatch')
            c.execute("insert into sm_private.billing_subscriptions(id,user_id,environment,status,product_id,period_end) values(%s,%s,%s,'active',%s,%s) on conflict(id) do update set period_end=greatest(sm_private.billing_subscriptions.period_end,excluded.period_end),updated_at=now()",(subscription_id,user_id,environment,product_id,ends_at))
            prior=c.execute('select p.period_id,b.user_id,b.subscription_id from sm_private.billing_payments p join sm_private.billing_periods b on b.id=p.period_id where p.id=%s',(payment_id,)).fetchone()
            if prior:
                if str(prior['user_id'])!=str(user_id) or prior['subscription_id']!=subscription_id:raise ValueError('Payment ownership mismatch')
                if payment_state in ('refunded','charged_back'):self.revoke_in(c,prior['period_id'])
                c.execute('update sm_private.billing_periods set suspended=%s where id=%s',(payment_state=='disputed',prior['period_id']))
                c.execute('update sm_private.billing_payments set status=%s where id=%s',(payment_state,payment_id))
                return False
            p=c.execute('select * from sm_private.billing_periods where subscription_id=%s and ends_at=%s',(subscription_id,ends_at)).fetchone()
            fresh=p is None
            if fresh:
                pid=str(uuid4())
                c.execute('insert into sm_private.billing_periods(id,user_id,subscription_id,starts_at,ends_at,allowance,plan_snapshot) values(%s,%s,%s,%s,%s,%s,%s)',(pid,user_id,subscription_id,starts_at,ends_at,allowance,Jsonb(plan_snapshot or {})))
                if not closed:entry(c,user_id,pid,allowance,'grant','grant:'+subscription_id+':'+ends_at.isoformat())
            else: pid=p['id']
            c.execute("insert into sm_private.billing_payments(id,period_id,invoice_id,amount_minor,currency,status,paid_at,provider_session,metadata) values(%s,%s,%s,%s,%s,%s,%s,%s,%s)",(payment_id,pid,invoice_id,amount_minor,currency,payment_state,paid_at or datetime.now(UTC),provider_session,Jsonb(metadata or {})))
            if payment_state in ('refunded','charged_back'):self.revoke_in(c,pid)
            elif payment_state=='disputed':c.execute('update sm_private.billing_periods set suspended=true where id=%s',(pid,))
            return fresh and not closed

    def summary(self,user_id):
        with self.db.transaction() as c:
            lock_account(c,user_id)
            period=current_period(c,user_id)
            subscription=c.execute('select * from sm_private.billing_subscriptions where user_id=%s and environment=%s order by updated_at desc limit 1',(user_id,credit_environment())).fetchone()
            periods=c.execute('select p.* from sm_private.billing_periods p join sm_private.billing_subscriptions s on s.id=p.subscription_id where p.user_id=%s and s.environment=%s order by p.starts_at desc limit 6',(user_id,credit_environment())).fetchall()
            held=c.execute("select coalesce(sum(r.units),0) n from sm_private.credit_reservations r left join sm_private.billing_periods p on p.id=r.period_id left join sm_private.billing_subscriptions s on s.id=p.subscription_id where r.user_id=%s and (s.environment=%s or r.period_id is null) and r.state='reserved' and r.expires_at>now()",(user_id,credit_environment())).fetchone()['n']
            return {'reserved':held,'subscription':subscription,'period':period,'periods':periods,'available':available(c,period)+signup_available(c,user_id),'signup_credits':signup_available(c,user_id),'monthly_credits':period['allowance'] if period else 0,'price_minor':(period or {}).get('plan_snapshot',{}).get('amount_minor',1999),'currency':(period or {}).get('plan_snapshot',{}).get('currency','USD'),'sales_enabled':False}

    def usage(self,user_id,period_id=None):
        periods=self.db.rows('select p.* from sm_private.billing_periods p join sm_private.billing_subscriptions s on s.id=p.subscription_id where p.user_id=%s and s.environment=%s order by p.starts_at desc limit 6',(user_id,credit_environment()))
        chosen=None if period_id=='signup' else (next((p for p in periods if str(p['id'])==str(period_id)),None) if period_id else (periods[0] if periods else None))
        if period_id and period_id!='signup' and not chosen: raise ValueError('Unknown billing period')
        rows=self.db.rows("select (created_at at time zone 'UTC')::date as day,coalesce(sum(-delta) filter(where kind='search'),0) searches,coalesce(sum(-delta) filter(where kind='batch'),0) batches from sm_private.credit_ledger where user_id=%s and period_id is not distinct from %s::uuid and kind in ('search','batch') group by 1 order by 1",(user_id,chosen['id'] if chosen else None))
        return {'period':chosen,'days':rows,'timezone':'UTC'}

    def spend_in(self,c,user_id,action,reference,session_id=None):
        """Shared internal spending primitive for future features; never a browser-supplied price."""
        lock_account(c,user_id)
        key=f'feature:{user_id}:{action}:{reference}'
        existing=c.execute('select delta from sm_private.credit_ledger where reference=%s',(key,)).fetchone()
        if existing:return False
        units=cost(c,action);period=funding(c,user_id,units)
        entry(c,user_id,period['id'] if period else None,-units,'spend',key,session_id)
        return True
