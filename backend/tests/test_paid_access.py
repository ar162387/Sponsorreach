"""Synthetic saved-result snapshots in a disposable DB exercise real API credit gates."""
import os
from uuid import uuid4
from dataclasses import replace
from datetime import datetime,UTC,timedelta
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from sponsor_match.api import create_app
from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.fixtures import seed_demo
from sponsor_match.models import Profile
from sponsor_match.search import Matcher
from sponsor_match.billing import Credits

@pytest.fixture
def paid(monkeypatch):
    url=os.getenv('BILLING_TEST_DATABASE_URL')
    if not url:pytest.skip('Requires disposable billing database')
    monkeypatch.setenv('BILLING_MODE','test');monkeypatch.setenv('BILLING_ENFORCE_CREDITS','true')
    uid=str(uuid4());settings=Settings(database_url=url,require_verified_email=True,supabase_url='https://example.invalid',supabase_publishable_key='test')
    class Auth:
        def __init__(self,uid):self.uid=uid
        def raise_for_status(self):pass
        def json(self):return {'id':self.uid,'email':'synthetic@example.invalid','email_confirmed_at':'2026-01-01'}
    monkeypatch.setattr('sponsor_match.api.httpx.get',lambda url,headers,timeout:Auth(headers['Authorization'].removeprefix('Bearer ')))
    monkeypatch.setattr('sponsor_match.api.sponsor_valid',lambda *a:True)
    db=Database(url);db.open();db.migrate();seed_demo(db,settings)
    profile=Profile.model_validate({'background':{'subject':'Mechanical Engineering'},'role_intents':[{'raw_label':'Mechanical engineer','confirmed':True}],'career_stage':'graduate','skills':[{'label':'CAD'}]})
    ranked,mode,versions=Matcher(db,settings).search(profile)
    assert ranked
    base=db.employer(ranked[0].employer_id);snapshot=[];ids=[]
    for i in range(45):
        eid=str(uuid4());ids.append(eid);e=base.model_copy(update={'id':eid,'name':f'Synthetic payment-test employer {i}','is_demo':False})
        db.execute("insert into sm.employers(id,name,name_key,town_key,identity_status,payload,is_demo,version) values(%s,%s,'synthetic','synthetic','accepted',%s,false,%s)",(eid,e.name,Jsonb(e.model_dump(mode='json')),e.version))
        snapshot.append(replace(ranked[0],employer_id=eid))
    db.close();db=Database(url)
    with TestClient(create_app(settings,db)) as c:yield c,db,uid,profile,snapshot

def headers(uid):return {'Authorization':'Bearer '+uid,'X-Session-Token':'f'*64}
def create(c,uid,profile,key=None):return c.post('/api/matches',headers=headers(uid),json={'profile':profile.model_dump(mode='json'),'idempotency_key':key or str(uuid4())})
def fund(db,uid):
    now=datetime.now(UTC)
    Credits(db).record_verified_payment(user_id=uid,subscription_id=str(uuid4()),payment_id=str(uuid4()),invoice_id=str(uuid4()),starts_at=now-timedelta(days=1),ends_at=now+timedelta(days=29),environment='test',product_id='test-product')

def test_signup_batch_spend_retry_and_withdrawal_keep_stable_positions(paid):
    c,db,uid,profile,rows=paid;fund(db,uid)
    r=create(c,uid,profile);assert r.status_code==202;sid=r.json()['session_id'];db.save_results(sid,rows,'synthetic',{})
    initial=c.get('/api/matches/'+sid,headers=headers(uid)).json();assert initial['credit_mode'] and initial['locked_count']==40
    assert len(c.get('/api/matches/'+sid+'/results',headers=headers(uid)).json()['results'])==5
    assert c.post('/api/matches/'+sid+'/demo-unlock',headers=headers(uid)).status_code==410
    assert c.get('/api/matches/'+sid+'/results?cursor=5',headers=headers(uid)).json()['results']==[]
    eid=rows[1].employer_id
    db.execute("update sm.employers set identity_status='quarantined',version='withdrawn',payload=jsonb_set(jsonb_set(payload,'{identity_status}','\"quarantined\"'),'{version}','\"withdrawn\"') where id=%s",(eid,))
    assert len(c.get('/api/matches/'+sid+'/results',headers=headers(uid)).json()['results'])==4
    assert not c.post('/api/matches/'+sid+'/batches/0/unlock',headers=headers(uid)).json()['charged']
    assert not c.post('/api/matches/'+sid+'/batches/0/unlock',headers=headers(uid)).json()['charged']
    assert len(c.get('/api/matches/'+sid+'/results',headers=headers(uid)).json()['results'])==4
    assert Credits(db).summary(uid)['available']==104
    for batch,n in [(1,5),(8,5)]:
        assert c.post(f'/api/matches/{sid}/batches/{batch}/unlock',headers=headers(uid)).json()['charged']
        assert len(c.get(f'/api/matches/{sid}/results?cursor={batch*5}',headers=headers(uid)).json()['results'])==n
    assert Credits(db).summary(uid)['available']==102
    assert not c.post(f'/api/matches/{sid}/batches/9/unlock',headers=headers(uid)).json()['charged']
    assert Credits(db).summary(uid)['available']==102

def test_revised_search_reserves_settles_and_empty_search_refunds(paid):
    c,db,uid,profile,rows=paid;fund(db,uid)
    first=create(c,uid,profile).json()['session_id'];db.save_results(first,rows[:2],'synthetic',{})
    key=str(uuid4());second=create(c,uid,profile,key).json()['session_id'];assert create(c,uid,profile,key).json()['session_id']==second
    assert Credits(db).summary(uid)['reserved']==1
    db.save_results(second,rows,'synthetic',{});db.save_results(second,rows,'synthetic',{})
    assert Credits(db).summary(uid)['available']==103 and Credits(db).summary(uid)['reserved']==0
    assert len(c.get(f'/api/matches/{second}/results',headers=headers(uid)).json()['results'])==5
    third=create(c,uid,profile).json()['session_id'];db.save_results(third,[],'synthetic',{})
    assert Credits(db).summary(uid)['available']==103
    assert db.owned_session(first,'f'*64,uid)['expires_at'] is None

def test_no_balance_and_other_owner_never_spend(paid):
    c,db,uid,profile,rows=paid
    first=create(c,uid,profile).json()['session_id'];db.save_results(first,rows,'synthetic',{})
    assert Credits(db).summary(uid)['available']==4
    from sponsor_match.billing import entry
    with db.transaction() as tx:entry(tx,uid,None,-4,'spend',str(uuid4()))
    assert create(c,uid,profile).status_code==402
    assert not c.post(f'/api/matches/{first}/batches/0/unlock',headers=headers(uid)).json()['charged']
    assert c.post(f'/api/matches/{first}/batches/1/unlock',headers=headers(uid)).status_code==402
    assert c.post(f'/api/matches/{first}/batches/0/unlock',headers=headers(str(uuid4()))).status_code==404
    assert c.get(f'/api/matches/{first}/results?cursor=3',headers=headers(uid)).status_code==422
    assert len(c.get(f'/api/matches/{first}/results',headers=headers(uid)).json()['results'])==5

def test_paid_refresh_preserves_entitlements_and_retries_without_double_charge(paid):
    c,db,uid,profile,rows=paid;fund(db,uid)
    first=create(c,uid,profile).json()['session_id'];db.save_results(first,rows[:30],'synthetic',{})
    url=f'/api/matches/{first}/refresh';key=str(uuid4())
    assert c.post(url,headers=headers(uid),json={'idempotency_key':key}).status_code==422
    payload={'idempotency_key':key,'accept_credit_cost':True}
    response=c.post(url,headers=headers(uid),json=payload);assert response.status_code==202
    second=response.json()['session_id'];assert second==first
    assert c.post(url,headers=headers(uid),json=payload).json()['session_id']==second
    assert Credits(db).summary(uid)['reserved']==1
    db.save_results(second,rows[:30],'synthetic',{},revision=1)
    assert Credits(db).summary(uid)['available']==104
    assert len(c.get(f'/api/matches/{first}/results',headers=headers(uid)).json()['results'])==5
    assert len(c.get(f'/api/matches/{second}/results',headers=headers(uid)).json()['results'])==5
    assert c.post(f'/api/matches/{first}/bookmarks/{rows[21].employer_id}',headers=headers(uid),json={'saved':True}).status_code==404
    assert c.post(f'/api/matches/{second}/bookmarks/{rows[1].employer_id}',headers=headers(uid),json={'saved':True}).status_code==200
    overview=c.get('/api/account/overview',headers=headers(uid)).json()
    assert [r['id'] for r in overview['sessions']]==[first]
    next_key=str(uuid4())
    assert c.post(url,headers=headers(uid),json={**payload,'idempotency_key':next_key}).status_code==202
    db.save_results(first,rows[30:]+rows[:5],'synthetic',{},revision=2)
    assert Credits(db).summary(uid)['available']==103
    delivered=c.get(f'/api/matches/{first}',headers=headers(uid)).json()
    assert len(delivered['preview'])==10
    assert {card['employer_id'] for card in delivered['preview'] if card['added_revision']==2}=={row.employer_id for row in rows[30:35]}
    assert c.post(url,headers=headers(uid),json=payload).status_code==202
    assert db.owned_session(first,'f'*64,uid)['revision']==2
    assert overview['bookmarks'][0]['employer_id']==rows[1].employer_id


def test_unknown_area_cards_share_entitlements_but_are_not_main_matches(paid):
    client, db, uid, profile, rows = paid
    profile.location = profile.location.model_copy(update={
        'mode': 'selected_area', 'preferred_regions': ['Coventry'],
    })
    unknown = [replace(row, features={**row.features, 'location_section': 'unknown'})
               for row in rows[5:7]]
    response = create(client, uid, profile)
    assert response.status_code == 202
    sid = response.json()['session_id']
    db.save_results(sid, rows[:5] + unknown, 'synthetic', {})
    url = f'/api/matches/{sid}'
    initial = client.get(url, headers=headers(uid)).json()
    assert initial['total_count'] == 5
    assert initial['unknown_location_count'] == 2
    assert initial['next_locked_batch'] == 1
    assert all(card['location_section'] == 'main' for card in initial['preview'])
    assert client.get(url+'/results?cursor=5', headers=headers(uid)).json()['results'] == []
    assert client.get(url+'/results', headers=headers(str(uuid4()))).status_code == 404
    assert client.post(url+'/batches/1/unlock', headers=headers(uid)).json()['charged']
    assert not client.post(url+'/batches/1/unlock', headers=headers(uid)).json()['charged']
    unlocked = client.get(url+'/results?cursor=5', headers=headers(uid)).json()
    assert unlocked['total_count'] == 5
    assert [card['location_section'] for card in unlocked['results']] == ['unknown', 'unknown']
    assert Credits(db).summary(uid)['available'] == 3
