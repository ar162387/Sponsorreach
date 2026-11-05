"""Real database tests for once-only signup grants and exhausted free accounts."""
import os
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from sponsor_match.db import Database
from sponsor_match.billing import Credits,InsufficientCredits,entry

@pytest.fixture
def free(monkeypatch):
    url=os.getenv('BILLING_TEST_DATABASE_URL')
    if not url:pytest.skip('Requires isolated billing test database')
    assert '127.0.0.1:55432/sponsormatch_billing_test' in url
    monkeypatch.setenv('BILLING_MODE','test')
    db=Database(url);db.open();db.migrate()
    credits=Credits(db);uid=str(uuid4());credits.ensure_signup(uid)
    yield db,credits,uid
    db.close()

def test_grant_once_under_concurrent_replays(free):
    db,credits,uid=free
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:credits.ensure_signup(uid),range(12)))
    assert credits.summary(uid)['available']==10
    assert len(db.rows("select id from sm_private.credit_ledger where user_id=%s and kind='grant'",(uid,)))==1

def test_last_credit_is_reserved_once_and_failure_releases_it(free):
    db,credits,uid=free
    with db.transaction() as c:entry(c,uid,None,-9,'spend',str(uuid4()))
    def reserve(_):
        sid=str(uuid4())
        try:credits.reserve(uid,sid);return sid
        except InsufficientCredits:return None
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(reserve,range(4)))
    winners=[sid for sid in results if sid]
    assert len(winners)==1 and credits.summary(uid)['available']==0
    assert credits.settle(uid,winners[0],False) is False
    assert credits.summary(uid)['available']==1

def test_ten_search_units_then_upgrade_required_no_reset(free):
    db,credits,uid=free
    for _ in range(10):
        with db.transaction() as c:assert credits.spend_in(c,uid,'search',str(uuid4()))
    assert credits.summary(uid)['available']==0
    credits.ensure_signup(uid)
    with pytest.raises(InsufficientCredits):credits.reserve(uid,str(uuid4()))
    assert credits.summary(uid)['available']==0

def test_signup_balance_shared_across_environments_without_new_grant(free,monkeypatch):
    db,credits,uid=free
    with db.transaction() as c:credits.spend_in(c,uid,'search','first')
    monkeypatch.setenv('BILLING_MODE','live');credits.ensure_signup(uid)
    assert credits.summary(uid)['available']==9

def test_signup_search_delivery_charges_once_and_unlocks_batch(free):
    db,credits,uid=free
    sid=str(uuid4());pid=str(uuid4())
    from psycopg.types.json import Jsonb
    from datetime import datetime,UTC,timedelta
    with db.transaction() as c:
        c.execute("insert into sm_private.candidate_profiles values(%s,%s,'test',%s,%s,null,now(),null)",(pid,uid,Jsonb({}),Jsonb({})))
        c.execute("insert into sm_private.match_sessions(id,profile_id,user_id,owner_hash,idempotency_key,status,expires_at) values(%s,%s,%s,'test',%s,'queued',null)",(sid,pid,uid,str(uuid4())))
    credits.reserve(uid,sid)
    assert credits.summary(uid)['available']==9
    assert credits.summary(uid)['reserved']==1
    assert credits.settle(uid,sid,True)
    assert not credits.settle(uid,sid,True)
    with db.transaction() as c:assert not credits.unlock_in(c,uid,sid,0,True)
    assert credits.summary(uid)['available']==9
    assert db.one('select count(*) n from sm_private.batch_entitlements where user_id=%s and session_id=%s',(uid,sid))['n']==1

def test_paid_subscription_works_after_free_balance_is_used(free):
    db,credits,uid=free
    from datetime import datetime,UTC,timedelta
    for _ in range(10):
        with db.transaction() as c:credits.spend_in(c,uid,'search',str(uuid4()))
    now=datetime.now(UTC)
    credits.record_verified_payment(user_id=uid,subscription_id=str(uuid4()),payment_id=str(uuid4()),invoice_id=str(uuid4()),starts_at=now,ends_at=now+timedelta(days=30),environment='test',product_id='test-product',amount_minor=2499)
    assert credits.summary(uid)['available']==800
    credits.ensure_signup(uid)
    assert credits.summary(uid)['available']==800
    credits.reserve(uid,str(uuid4()))
    assert credits.summary(uid)['available']==799

def test_confirmed_signup_trigger_grants_once(free):
    db,credits,_=free
    uid=str(uuid4())
    with db.transaction() as c:
        c.execute('create schema if not exists auth')
        c.execute('create table auth.users(id uuid primary key,email_confirmed_at timestamptz)')
        try:
            c.execute('create trigger sponsorreach_signup_credits after insert or update of email_confirmed_at on auth.users for each row execute function sm_private.signup_credit_trigger()')
            c.execute('insert into auth.users(id) values(%s)',(uid,))
            assert c.execute('select count(*) n from sm_private.signup_credit_grants where user_id=%s',(uid,)).fetchone()['n']==0
            c.execute('update auth.users set email_confirmed_at=now() where id=%s',(uid,))
            c.execute('update auth.users set email_confirmed_at=now() where id=%s',(uid,))
            assert c.execute('select sum(delta) n from sm_private.credit_ledger where user_id=%s',(uid,)).fetchone()['n']==10
        finally:c.execute('drop table auth.users')
