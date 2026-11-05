import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sponsor_match.api import create_app
from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.admin import staff_ids


def test_malformed_allowlist_fails_closed():
    assert staff_ids('broken')==set()
    uid=str(uuid4())
    assert staff_ids(uid+',broken')==set()
    assert staff_ids(' '+uid+' ')=={uid}
    assert staff_ids(uid+','+str(uuid4()))==set()

@pytest.fixture
def support(monkeypatch):
    url=os.getenv('BILLING_TEST_DATABASE_URL')
    if not url:pytest.skip('Requires isolated database')
    owner,other,staff=[str(uuid4()) for _ in range(3)]
    monkeypatch.setenv('SPONSORREACH_ADMIN_USER_IDS',staff)
    monkeypatch.setenv('SPONSORREACH_ADMIN_EMAIL','support-test@example.invalid')
    class Response:
        def __init__(self,uid):self.uid=uid
        def raise_for_status(self):pass
        def json(self):return {'id':self.uid,'email':'support-test@example.invalid','email_confirmed_at':'2026-10-01','user_metadata':{'admin':True}}
    monkeypatch.setattr('sponsor_match.api.httpx.get',lambda url,headers,timeout:Response(headers['Authorization'].removeprefix('Bearer ')))
    db=Database(url);db.open();db.migrate();db.close();db=Database(url)
    settings=Settings(database_url=url,supabase_url='https://example.invalid',supabase_publishable_key='test')
    with TestClient(create_app(settings,db)) as client:yield client,owner,other,staff


def headers(uid):return {'Authorization':'Bearer '+uid}


def test_staff_guard_and_support_isolation(support):
    c,owner,other,staff=support
    assert c.get('/api/admin/overview').status_code==401
    assert c.get('/api/admin/overview',headers=headers(owner)).status_code==403
    assert c.get('/api/admin/overview',headers=headers(staff)).status_code==200
    r=c.post('/api/account/support',json={'subject':'Billing question','message':'Please explain my credits.'},headers=headers(owner))
    assert r.status_code==201
    tid=r.json()['id']
    assert c.get('/api/account/support/'+tid,headers=headers(other)).status_code==404
    assert c.post('/api/account/support/'+tid+'/reply',json={'message':'Forged response'},headers=headers(other)).status_code==404
    assert c.post('/api/admin/support/'+tid+'/reply',json={'message':'Your saved results remain available.'},headers=headers(staff)).status_code==200
    result=c.get('/api/account/support/'+tid,headers=headers(owner)).json()
    assert result['replies'][0]['is_staff']
    assert c.post('/api/admin/support/'+tid+'/state',json={'closed':True},headers=headers(staff)).status_code==200
    assert c.post('/api/account/support/'+tid+'/reply',json={'message':'Another question'},headers=headers(owner)).status_code==409
    assert c.post('/api/admin/support/'+tid+'/state',json={'closed':False},headers=headers(staff)).status_code==200
    assert c.post('/api/account/support/'+tid+'/reply',json={'message':'Thank you'},headers=headers(owner)).status_code==200


def test_support_validation_and_limits(support):
    c,owner,_,staff=support
    assert c.post('/api/account/support',json={'subject':'  ','message':'  '},headers=headers(owner)).status_code==422
    assert c.post('/api/account/support',json={'subject':'x','message':'x'*4001},headers=headers(owner)).status_code==422
    for _ in range(5):assert c.post('/api/account/support',json={'subject':'Question','message':'Help please'},headers=headers(owner)).status_code==201
    assert c.post('/api/account/support',json={'subject':'Question','message':'Help please'},headers=headers(owner)).status_code==429
    assert c.get('/api/admin/overview?offset=-1',headers=headers(staff)).status_code==422


def test_dashboard_readonly_projections_and_filters(support):
    c,owner,other,staff=support
    c.get('/api/account/billing',headers=headers(owner))
    for view in ['summary','health','members','payments','refunds','credits','checkouts','events','runs','reservations','issues','support']:
        assert c.get('/api/admin/dashboard/'+view,headers=headers(owner)).status_code==403
        response=c.get('/api/admin/dashboard/'+view,headers=headers(staff))
        assert response.status_code==200,response.text
    records=c.get('/api/admin/dashboard/members?q='+owner,headers=headers(staff)).json()
    assert any(str(r['id'])==owner for r in records['rows'])
    detail=c.get('/api/admin/dashboard/members/'+owner,headers=headers(staff)).json()
    assert detail['balance']['signup_credits']==10
    credit_summary=c.get('/api/account/credit-summary',headers=headers(owner)).json()
    assert credit_summary['available']==10 and 'periods' not in credit_summary
    assert not detail['shortlists']
    assert 'email' not in detail['account']
    for query in ['offset=-1','environment=bogus','start=nope','q='+'x'*161]:
        assert c.get('/api/admin/dashboard/payments?'+query,headers=headers(staff)).status_code==422
    assert c.get('/api/admin/dashboard/members?q=nonexistent'+str(uuid4()),headers=headers(staff)).json()['rows']==[]
    assert c.get('/api/admin/dashboard/credits?environment=signup&status=grant&q='+owner,headers=headers(staff)).json()['rows'][0]['delta']==10
    assert c.get('/api/admin/dashboard/payments?environment=all',headers=headers(staff)).status_code==200
    c.post('/api/account/support',json={'subject':'Distinct ticket','message':'Question'},headers=headers(owner))
    tickets=c.get('/api/admin/dashboard/support?q=Distinct+ticket&status=open',headers=headers(staff)).json()
    assert any(t['user_id']==owner for t in tickets['rows'])


def test_configured_id_with_wrong_email_is_denied(support,monkeypatch):
    c,_,_,staff=support
    monkeypatch.setenv('SPONSORREACH_ADMIN_EMAIL','different@example.invalid')
    assert c.get('/api/admin/dashboard/summary',headers=headers(staff)).status_code==403
