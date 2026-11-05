"""Account-wide repeat protection, prospect isolation and credit edge cases."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from test_paid_access import paid, headers, create, fund
from sponsor_match.billing import Credits, entry


def deliver(c, db, uid, profile, rows):
    response=create(c,uid,profile)
    assert response.status_code==202,response.text
    sid=response.json()['session_id']
    db.save_results(sid,rows,'synthetic',{})
    return sid


@pytest.mark.parametrize('repeated,charged',[(0,True),(9,True),(10,True),(11,False),(20,False)])
def test_majority_boundary_across_prospects(paid,repeated,charged):
    c,db,uid,profile,rows=paid
    first=deliver(c,db,uid,profile,rows[:20])
    second_profile=profile.model_copy(deep=True)
    second_profile.role_intents[0].raw_label='Design engineer'
    second=deliver(c,db,uid,second_profile,rows[:repeated]+rows[20:40-repeated])
    assert Credits(db).summary(uid)['available']==9-int(charged)
    assert Credits(db).summary(uid)['reserved']==0
    result=c.get('/api/matches/'+second,headers=headers(uid)).json()
    assert len(result['preview'])==20
    assert result['repeat_credit_saved'] is not charged
    assert result['search_credit_charged'] is charged
    assert c.get('/api/matches/'+first,headers=headers(uid)).json()['profile']['role_intents'][0]['raw_label']=='Mechanical engineer'
    assert result['profile']['role_intents'][0]['raw_label']=='Design engineer'


def test_empty_and_failure_restore_reservations(paid):
    c,db,uid,profile,rows=paid
    empty=deliver(c,db,uid,profile,[])
    assert Credits(db).summary(uid)['available']==10
    assert c.get('/api/matches/'+empty,headers=headers(uid)).json()['total_count']==0
    sid=create(c,uid,profile).json()['session_id']
    assert Credits(db).summary(uid)['reserved']==1
    item=db.one("select * from sm.work_items where dedupe_key=%s",('match:'+sid,))
    item['attempts']=3
    db.fail_work(item,'synthetic_failure',3)
    assert Credits(db).summary(uid)['available']==10
    assert Credits(db).summary(uid)['reserved']==0


def test_locked_companies_do_not_count_as_previously_delivered(paid):
    c,db,uid,profile,rows=paid
    deliver(c,db,uid,profile,rows)
    second=deliver(c,db,uid,profile,rows[20:40])
    assert Credits(db).summary(uid)['available']==8
    assert len(c.get('/api/matches/'+second,headers=headers(uid)).json()['preview'])==20


def test_free_repeat_batch_can_open_at_zero_balance(paid):
    c,db,uid,profile,rows=paid
    deliver(c,db,uid,profile,rows[:20])
    second=deliver(c,db,uid,profile,rows[20:40]+rows[:20])
    with db.transaction() as tx:entry(tx,uid,None,-8,'spend',str(uuid4()))
    state=c.get('/api/matches/'+second,headers=headers(uid)).json()
    assert state['balance']==0 and state['next_batch_cost']==0
    url=f'/api/matches/{second}/batches/1/unlock'
    assert c.post(url,headers=headers(uid)).json()['charged'] is False
    assert c.post(url,headers=headers(uid)).json()['charged'] is False
    assert len(c.get(f'/api/matches/{second}/results?cursor=20',headers=headers(uid)).json()['results'])==20
    assert Credits(db).summary(uid)['available']==0


def test_other_accounts_repeats_still_cost_a_credit(paid):
    c,db,uid,profile,rows=paid
    deliver(c,db,uid,profile,rows[:20])
    other=str(uuid4())
    second=deliver(c,db,other,profile,rows[:20])
    assert Credits(db).summary(other)['available']==9
    assert c.get('/api/matches/'+second,headers=headers(uid)).status_code==404


def test_concurrent_identical_results_only_charge_first_delivery(paid):
    c,db,uid,profile,rows=paid
    ids=[create(c,uid,profile).json()['session_id'] for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda sid:db.save_results(sid,rows[:20],'synthetic',{}),ids))
    assert Credits(db).summary(uid)['available']==9
    assert Credits(db).summary(uid)['reserved']==0
    assert all(len(c.get('/api/matches/'+sid,headers=headers(uid)).json()['preview'])==20 for sid in ids)


def test_expired_reservation_and_duplicate_rows_never_double_charge(paid):
    c,db,uid,profile,rows=paid
    sid=create(c,uid,profile).json()['session_id']
    db.execute("update sm_private.credit_reservations set expires_at=now()-interval '1 second' where session_id=%s",(sid,))
    db.save_results(sid,rows[:2]+rows[:2],'synthetic',{})
    assert Credits(db).summary(uid)['available']==10
    assert db.one('select count(*) n from sm_private.match_results where session_id=%s',(sid,))['n']==2
    assert c.post(f'/api/matches/{sid}/batches/0/unlock',headers=headers(uid)).json()['charged']
    assert not c.post(f'/api/matches/{sid}/batches/0/unlock',headers=headers(uid)).json()['charged']
    assert Credits(db).summary(uid)['available']==9


def test_payment_after_depletion_restores_search_and_replay_adds_nothing(paid):
    c,db,uid,profile,rows=paid
    Credits(db).ensure_signup(uid)
    with db.transaction() as tx:entry(tx,uid,None,-10,'spend',str(uuid4()))
    assert create(c,uid,profile).status_code==402
    assert not db.one('select id from sm_private.match_sessions where user_id=%s',(uid,))
    fund(db,uid)
    assert Credits(db).summary(uid)['available']==800
    sid=deliver(c,db,uid,profile,rows[:20])
    assert Credits(db).summary(uid)['available']==799
    assert len(c.get('/api/matches/'+sid,headers=headers(uid)).json()['preview'])==20


def test_signup_and_paid_usage_are_both_visible_and_account_scoped(paid):
    c,db,uid,profile,rows=paid
    deliver(c,db,uid,profile,rows[:20])
    usage=c.get('/api/account/usage?period_id=signup',headers=headers(uid))
    assert usage.status_code==200
    assert sum(int(day['searches']) for day in usage.json()['days'])==1
    assert Credits(db).usage(str(uuid4()),'signup')['days']==[]
    with db.transaction() as tx:entry(tx,uid,None,-9,'spend',str(uuid4()))
    fund(db,uid)
    deliver(c,db,uid,profile,rows[20:40])
    assert sum(int(day['searches']) for day in Credits(db).usage(uid)['days'])==1
    assert sum(int(day['searches']) for day in Credits(db).usage(uid,'signup')['days'])==1


def test_same_browser_key_cannot_reuse_another_accounts_search(paid):
    c,db,uid,profile,rows=paid
    key=str(uuid4())
    first=create(c,uid,profile,key).json()['session_id']
    other=str(uuid4())
    response=create(c,other,profile,key)
    assert response.status_code==409
    assert Credits(db).summary(other)['available']==10
    assert c.get('/api/matches/'+first,headers=headers(other)).status_code==404
    assert c.post(f'/api/matches/{first}/batches/0/unlock',headers=headers(other)).status_code==404


@pytest.mark.parametrize('total,repeated,charged',[(1,0,True),(1,1,False),(2,1,True),(3,2,False)])
def test_small_batch_majority_boundary(paid,total,repeated,charged):
    c,db,uid,profile,rows=paid
    deliver(c,db,uid,profile,rows[:20])
    deliver(c,db,uid,profile,rows[:repeated]+rows[20:20+total-repeated])
    assert Credits(db).summary(uid)['available']==9-int(charged)


def test_three_different_prospects_share_one_balance_without_mixing_profiles(paid):
    c,db,uid,profile,rows=paid
    ids=[]
    for subject,role,companies in [('Engineering','Mechanical engineer',rows[:20]),('Computer science','Software developer',rows[20:40]),('Accounting','Accountant',rows[:20])]:
        prospect=profile.model_copy(deep=True)
        prospect.background.subject=subject
        prospect.role_intents[0].raw_label=role
        sid=deliver(c,db,uid,prospect,companies);ids.append(sid)
        assert c.get('/api/matches/'+sid,headers=headers(uid)).json()['profile']['background']['subject']==subject
    assert Credits(db).summary(uid)['available']==8
    overview=c.get('/api/account/overview',headers=headers(uid)).json()
    assert set(ids)<={row['id'] for row in overview['sessions']}
