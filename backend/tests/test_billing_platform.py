"""Payment bridge/plan/ledger tests use only a dedicated local database and synthetic accounts."""
import os
from uuid import uuid4
from datetime import datetime,UTC,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sponsor_match.db import Database
from sponsor_match.api import create_app
from sponsor_match.config import Settings
from sponsor_match.billing import Credits,InsufficientCredits,entry

@pytest.fixture
def platform(monkeypatch):
    url=os.getenv('BILLING_TEST_DATABASE_URL')
    if not url:pytest.skip('Requires isolated billing test database')
    monkeypatch.setenv('BILLING_INTERNAL_SECRET','s'*32)
    monkeypatch.setenv('BILLING_MODE','test')
    db=Database(url);db.open();db.migrate()
    db.execute("insert into sm_private.billing_plans(slug,environment,name,product_id,amount_minor,currency,interval,credits,active) values('monthly-eur-test','test','SponsorReach Monthly','fixture-eur-product',2499,'EUR','month',100,true) on conflict do nothing")
    db.close();db=Database(url)
    with TestClient(create_app(Settings(database_url=url),db)) as c:yield c,db

def post(c,action,**body):return c.post('/api/internal/billing/'+action,json={'environment':'test',**body},headers={'x-billing-secret':'s'*32})

def paid_account(db,allowance=100,environment='test'):
    uid=str(uuid4());now=datetime.now(UTC)
    args=dict(user_id=uid,subscription_id=str(uuid4()),payment_id=str(uuid4()),invoice_id=str(uuid4()),starts_at=now-timedelta(days=1),ends_at=now+timedelta(days=29),environment=environment,product_id='test-product',allowance=allowance)
    Credits(db).record_verified_payment(**args)
    return uid,args

def test_private_bridge_denies_browser_and_bad_secret(platform):
    c,_=platform
    assert c.post('/api/internal/billing/plans',json={'environment':'test'}).status_code==401
    assert c.post('/api/internal/billing/plans',json={'environment':'test'},headers={'x-billing-secret':'wrong'}).status_code==401
    assert post(c,'plans').status_code==200

def test_future_plan_amounts_and_archive_are_immutable(platform):
    c,db=platform;uid,args=paid_account(db,allowance=2400)
    assert Credits(db).summary(uid)['available']==2400
    with pytest.raises(Exception):db.execute("update sm_private.billing_plans set credits=900 where slug='monthly' and environment='test'")
    with pytest.raises(Exception):db.execute('update sm_private.credit_ledger set delta=900 where user_id=%s',(uid,))
    # Mutable merchandising is distinct from the immutable customer contract.
    db.execute("update sm_private.billing_plans set active=false where slug='monthly' and environment='test'")
    assert Credits(db).summary(uid)['available']==2400

def test_test_credits_do_not_fund_live_usage(platform,monkeypatch):
    c,db=platform;uid,args=paid_account(db)
    assert Credits(db).summary(uid)['available']==100
    monkeypatch.setenv('BILLING_MODE','live')
    assert Credits(db).summary(uid)['available']==0
    with pytest.raises(InsufficientCredits):Credits(db).reserve(uid,str(uuid4()))

def test_pending_checkout_reused_and_wrong_owner_cannot_bind(platform):
    c,_=platform;uid=str(uuid4())
    a=post(c,'prepare',user_id=uid,plan='monthly-eur-test');b=post(c,'prepare',user_id=uid,plan='monthly-eur-test')
    assert a.status_code==200 and a.json()['id']==b.json()['id']
    assert post(c,'bind',intent_id=a.json()['id'],user_id=str(uuid4()),session_id=str(uuid4()),url='https://example.invalid',expires_at='2030-01-01T00:00:00Z').status_code==404

def test_verified_fulfilment_replay_and_correlation(platform):
    c,db=platform;uid=str(uuid4());intent=post(c,'prepare',user_id=uid,plan='monthly-eur-test').json();sid=uuid4().hex
    assert post(c,'bind',intent_id=intent['id'],user_id=uid,session_id=sid,url='https://example.invalid',expires_at='2030-01-01T00:00:00Z').status_code==200
    plan=intent['plan_snapshot'];sub={'id':str(uuid4()),'linkId':plan['product_id'],'currency':'eur','unitAmountMinor':2499}
    payment={'id':str(uuid4()),'invoice_id':str(uuid4()),'amount_minor':2499,'currency':'EUR'}
    checkout={'sessionId':sid,'metadata':{'customerId':uid,'checkoutIntentId':intent['id']}}
    now=datetime.now(UTC);body=dict(plan=plan,subscription=sub,payment=payment,checkout=checkout,starts_at=(now-timedelta(days=1)).isoformat(),ends_at=(now+timedelta(days=29)).isoformat())
    assert post(c,'fulfil',**body).json()['granted']
    assert not post(c,'fulfil',**body).json()['granted']
    assert Credits(db).summary(uid)['available']==100
    checkout['metadata']['customerId']=str(uuid4())
    assert post(c,'fulfil',**body).status_code==409

def test_refund_scope_and_usage_reconciliation(platform):
    c,db=platform;uid,args=paid_account(db);p=Credits(db).summary(uid)['period']
    with db.transaction() as tx:entry(tx,uid,p['id'],-3,'search',str(uuid4()))
    assert post(c,'refund-prepare',user_id=str(uuid4()),payment_id=args['payment_id']).status_code==404
    assert post(c,'refund-prepare',user_id=uid,payment_id=args['payment_id'],reason='test').status_code==200
    assert Credits(db).summary(uid)['available']==797
    assert post(c,'payment-state',payment_id=args['payment_id'],status='refunded').status_code==200
    assert Credits(db).summary(uid)['available']==0
    assert post(c,'payment-state',payment_id=args['payment_id'],status='refunded').status_code==200
    assert sum(int(d['searches']) for d in Credits(db).usage(uid)['days'])==3

def test_expired_and_empty_work_release_without_recharging(platform):
    c,db=platform;uid,_=paid_account(db)
    session=str(uuid4());Credits(db).reserve(uid,session)
    db.execute("update sm_private.credit_reservations set expires_at=now()-interval '1 second' where session_id=%s",(session,))
    assert not Credits(db).settle(uid,session,True)
    assert Credits(db).summary(uid)['available']==100

def test_shared_currency_feature_spending_is_idempotent(platform):
    c,db=platform;uid,_=paid_account(db);action='test-'+uuid4().hex
    db.execute('insert into sm_private.credit_costs(action,units) values(%s,5)',(action,))
    with db.transaction() as tx:assert Credits(db).spend_in(tx,uid,action,'feature-request')
    with db.transaction() as tx:assert not Credits(db).spend_in(tx,uid,action,'feature-request')
    assert Credits(db).summary(uid)['available']==795


def test_live_checkout_refuses_missing_current_official_source(platform):
    from psycopg.types.json import Jsonb
    c,db=platform
    snapshots=db.rows("select id,metadata from sm.source_artifacts where kind='official_register' and metadata->>'active'='true'")
    before=db.one('select count(*) n from sm_private.billing_checkouts')['n']
    try:
        db.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{active}','false') where kind='official_register'")
        assert post(c,'launch-status',environment='live').json()['research_ready'] is False
        assert post(c,'prepare',environment='live',user_id=str(uuid4()),plan='monthly-eur-test').status_code==503
        assert db.one('select count(*) n from sm_private.billing_checkouts')['n']==before
    finally:
        for snapshot in snapshots:db.execute('update sm.source_artifacts set metadata=%s where id=%s',(Jsonb(snapshot['metadata']),snapshot['id']))


def test_reconciliation_lease_and_recovery(platform):
    c,db=platform
    db.execute("update sm_private.reconciliation_runs set status='interrupted',finished_at=now() where status='running'")
    first=post(c,'run-start',source='scheduled').json()
    assert first['acquired']
    second=post(c,'run-start',source='manual').json()
    assert not second['acquired'] and second['id']==first['id']
    assert post(c,'run-finish',run_id=first['id'],status='partial',errors=1,error='sync_items_pending').status_code==200
    next_run=post(c,'run-start',source='scheduled').json()
    assert next_run['acquired']
    db.execute("update sm_private.reconciliation_runs set lease_until=now()-interval '1 second' where id=%s",(next_run['id'],))
    replacement=post(c,'run-start',source='scheduled').json()
    assert replacement['acquired'] and replacement['id']!=next_run['id']
    assert db.one('select status from sm_private.reconciliation_runs where id=%s',(next_run['id'],))['status']=='interrupted'
    post(c,'run-finish',run_id=replacement['id'],status='complete',errors=0)


def test_partial_sync_does_not_set_success_timestamp(platform):
    c,db=platform
    before=db.one("select last_success_at from sm_private.billing_sync where id='transactions'")
    post(c,'sync-state',cursor=0,success=True,error='sync_items_pending')
    assert db.one("select last_success_at from sm_private.billing_sync where id='transactions'")==before


def test_reconciliation_pending_verification_cannot_report_complete(platform):
    c,db=platform
    db.execute("update sm_private.reconciliation_runs set status='interrupted',finished_at=now() where status='running'")
    event_id='test:'+str(uuid4())
    from psycopg.types.json import Jsonb
    db.execute('insert into sm_private.billing_events(id,payload) values(%s,%s)',(event_id,Jsonb({})))
    run=post(c,'run-start',source='scheduled').json()
    result=post(c,'run-finish',run_id=run['id'],status='complete',errors=0).json()
    assert result['status']=='partial'
    assert db.one('select error_code from sm_private.reconciliation_runs where id=%s',(run['id'],))['error_code']=='verification_pending'
    db.execute("update sm_private.billing_events set status='done' where id=%s",(event_id,))
