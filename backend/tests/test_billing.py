"""Real Postgres concurrency checks; never run against the application database."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, UTC, timedelta
from uuid import uuid4
import pytest
from sponsor_match.db import Database
from sponsor_match.billing import Credits, InsufficientCredits, entry, lock_account

@pytest.fixture
def account():
    url=os.getenv('BILLING_TEST_DATABASE_URL')
    if not url: pytest.skip('Set BILLING_TEST_DATABASE_URL to an isolated database')
    db=Database(url);db.open();db.migrate()
    uid=str(uuid4());sid=str(uuid4());now=datetime.now(UTC)
    credits=Credits(db)
    args=dict(user_id=uid,subscription_id=sid,payment_id=str(uuid4()),invoice_id=str(uuid4()),starts_at=now-timedelta(days=1),ends_at=now+timedelta(days=29),environment='test',product_id='test-product')
    credits.record_verified_payment(**args)
    yield db,credits,uid,args
    db.close()

def test_payment_replay_and_duplicate_cycle(account):
    db,credits,uid,args=account
    assert not credits.record_verified_payment(**args)
    assert not credits.record_verified_payment(**{**args,'payment_id':str(uuid4())})
    assert credits.summary(uid)['available']==800
    assert len(db.rows("select * from sm_private.credit_ledger where user_id=%s",(uid,)))==1

def test_concurrent_last_credit(account):
    db,credits,uid,args=account
    p=credits.summary(uid)['period']
    with db.transaction() as c: entry(c,uid,p['id'],-799,'search',str(uuid4()))
    def reserve(_):
        try: credits.reserve(uid,str(uuid4()));return True
        except InsufficientCredits:return False
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(reserve,range(4)))
    assert sum(results)==1
    assert credits.summary(uid)['available']==0

def test_settlement_and_retry(account):
    db,credits,uid,args=account
    session=str(uuid4())
    # A batch entitlement references a durable shortlist.
    with db.transaction() as c:
        pid=str(uuid4());expiry=datetime.now(UTC)+timedelta(days=30)
        c.execute("insert into sm_private.candidate_profiles values(%s,%s,'test','{}','{}',null,now(),%s)",(pid,uid,expiry))
        c.execute("insert into sm_private.match_sessions(id,profile_id,user_id,owner_hash,idempotency_key,status,expires_at) values(%s,%s,%s,'test',%s,'ready',%s)",(session,pid,uid,str(uuid4()),expiry))
    credits.reserve(uid,session)
    assert credits.settle(uid,session,True)
    assert not credits.settle(uid,session,True)
    assert credits.summary(uid)['available']==799

def test_empty_releases_reservation(account):
    db,credits,uid,args=account
    sid=str(uuid4());credits.reserve(uid,sid)
    assert credits.summary(uid)['available']==799
    assert not credits.settle(uid,sid,False)
    assert credits.summary(uid)['available']==800

def test_expired_work_does_not_charge_next_period(account):
    db,credits,uid,args=account
    sid=str(uuid4());credits.reserve(uid,sid)
    db.execute("update sm_private.credit_reservations set expires_at=now()-interval '1 second' where session_id=%s",(sid,))
    assert not credits.settle(uid,sid,True)
    assert credits.summary(uid)['available']==800

def test_refund_removes_only_remaining_balance(account):
    db,credits,uid,args=account
    p=credits.summary(uid)['period']
    with db.transaction() as c: entry(c,uid,p['id'],-7,'search',str(uuid4()))
    credits.revoke(p['id']);credits.revoke(p['id'])
    assert credits.summary(uid)['available']==0
    assert db.one('select sum(delta) balance from sm_private.credit_ledger where period_id=%s',(p['id'],))['balance']==0

def test_period_rollover_and_history(account):
    db,credits,uid,args=account
    old=credits.summary(uid)['period']
    db.execute("update sm_private.billing_periods set starts_at=now()-interval '31 days',ends_at=now()-interval '1 day' where id=%s",(old['id'],))
    assert credits.summary(uid)['available']==0
    assert credits.record_verified_payment(**{**args,'payment_id':str(uuid4()),'starts_at':datetime.now(UTC),'ends_at':datetime.now(UTC)+timedelta(days=30)})
    assert credits.summary(uid)['available']==800
    with pytest.raises(ValueError):credits.usage(uid,str(uuid4()))

def test_other_owner_cannot_reuse_reservation(account):
    db,credits,uid,args=account
    sid=str(uuid4());credits.reserve(uid,sid)
    with pytest.raises(ValueError):credits.reserve(str(uuid4()),sid)
    with pytest.raises(ValueError):credits.record_verified_payment(**{**args,'user_id':str(uuid4()),'payment_id':str(uuid4())})

def test_opening_first_batch_settles_existing_reservation_once(account):
    db,credits,uid,args=account
    session=str(uuid4())
    with db.transaction() as c:
        pid=str(uuid4());expiry=datetime.now(UTC)+timedelta(days=30)
        c.execute("insert into sm_private.candidate_profiles values(%s,%s,'test','{}','{}',null,now(),%s)",(pid,uid,expiry))
        c.execute("insert into sm_private.match_sessions(id,profile_id,user_id,owner_hash,idempotency_key,status,expires_at) values(%s,%s,%s,'test',%s,'ready',%s)",(session,pid,uid,str(uuid4()),expiry))
    credits.reserve(uid,session)
    with db.transaction() as c:assert credits.unlock_in(c,uid,session,0,True)
    assert not credits.settle(uid,session,True)
    assert credits.summary(uid)['available']==799

def test_dispute_between_reservation_and_delivery_releases_without_spending(account):
    db,credits,uid,args=account
    sid=str(uuid4());r=credits.reserve(uid,sid)
    db.execute('update sm_private.billing_periods set suspended=true where id=%s',(r['period_id'],))
    assert not credits.settle(uid,sid,True)
    assert db.one('select state from sm_private.credit_reservations where id=%s',(r['id'],))['state']=='released'
    assert not db.one("select id from sm_private.credit_ledger where user_id=%s and kind='search'",(uid,))
