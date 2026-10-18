import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sponsor_match.api import create_app
from sponsor_match.db import Database
from sponsor_match.config import Settings
from sponsor_match.fixtures import seed_demo
from sponsor_match.cli import worker
from sponsor_match.ingest import import_csv


@pytest.fixture(scope="module")
def integration():
    url=os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated disposable Postgres database")
    settings=Settings(database_url=url)
    db=Database(url);db.open();db.migrate();seed_demo(db,settings);db.close()
    db=Database(url)
    with TestClient(create_app(settings,db)) as client:
        yield db,settings,client


def request():
    return {"profile":{"background":{"subject":"Mechanical Engineering"},"role_intents":[{"raw_label":"Mechanical engineer","confirmed":True}],"career_stage":"graduate","skills":[{"label":"CAD"}]},"identity":{"name":"Test Candidate","email":"candidate@example.com"},"idempotency_key":str(uuid4())}


def test_taxonomy_version_rebuilds_unchanged_employer_documents(integration):
    from dataclasses import replace
    from datetime import datetime,UTC
    from sponsor_match.models import Employer,Claim
    from sponsor_match.taxonomy import Taxonomy
    db,_,_=integration
    eid=str(uuid4());taxonomy=Taxonomy()
    claim=Claim(id=uuid4().hex,kind='activity',text='Software development',excerpt='Software development',source_url='https://acme.example',source_kind='first_party',observed_at=datetime.now(UTC),attribution='accepted')
    employer=db.save_employer(Employer(id=eid,name='Taxonomy version test',source_namespace='taxonomy-version-test',source_key=eid,claims=[claim]),taxonomy)
    before=db.one('select content_hash from sm.search_documents where employer_id=%s',(eid,))['content_hash']
    updated=Taxonomy([replace(c,version='test-next-taxonomy') for c in taxonomy.concepts])
    after=db.save_employer(employer,updated)
    document=db.one('select content_hash,taxonomy_version from sm.search_documents where employer_id=%s',(eid,))
    assert employer.version==after.version
    assert document['content_hash']!=before and document['taxonomy_version']=='test-next-taxonomy'


def test_owner_preview_unlock_and_stable_results(integration):
    db,settings,client=integration
    headers={"X-Session-Token":"a"*64}
    body=request()
    response=client.post("/api/matches",json=body,headers=headers)
    assert response.status_code==202
    id=response.json()["session_id"]
    assert client.post("/api/matches",json=body,headers=headers).json()["session_id"]==id
    worker(db,settings,once=True)
    result=client.get("/api/matches/"+id,headers=headers).json()
    assert result["status"]=="ready"
    assert len(result["preview"])==3 and result["locked_count"]>=1
    assert all(c["is_demo"] for c in result["preview"])
    assert "score" not in str(result)
    inaccessible=client.get("/api/matches/"+id,headers={"X-Session-Token":"b"*64})
    assert inaccessible.status_code==404
    locked=db.rows("select employer_id from sm_private.match_results where session_id=%s and rank>=3",(id,))
    for row in locked:
        assert str(row["employer_id"]) not in response.text and str(row["employer_id"]) not in str(result)
    assert client.get(f"/api/matches/{id}/results?cursor=3",headers=headers).json()["results"]==[]
    blocked_feedback=client.post("/api/feedback",headers=headers,json={"session_id":id,"employer_id":str(locked[0]["employer_id"]),"event":"save"})
    assert blocked_feedback.status_code==404
    before=db.rows("select employer_id,rank from sm_private.match_results where session_id=%s order by rank",(id,))
    unlocked=client.post(f"/api/matches/{id}/demo-unlock",headers=headers)
    assert unlocked.status_code==200 and not unlocked.json()["charged"]
    assert client.post(f"/api/matches/{id}/demo-unlock",headers=headers).status_code==200
    full=client.get(f"/api/matches/{id}/results",headers=headers).json()
    assert len(full["results"])==result["total_count"]
    assert before==db.rows("select employer_id,rank from sm_private.match_results where session_id=%s order by rank",(id,))


def test_abstention_and_profile_validation(integration):
    db,settings,client=integration
    headers={"X-Session-Token":"c"*64}
    body=request();body["profile"]["role_intents"][0]["raw_label"]="Quantum lattice research consultant"
    response=client.post("/api/matches",headers=headers,json=body)
    worker(db,settings,once=True)
    id=response.json()["session_id"]
    assert client.get(f"/api/matches/{id}",headers=headers).json()["total_count"]==0
    assert client.post(f"/api/matches/{id}/demo-unlock",headers=headers).status_code==409
    body=request();body["profile"]["role_intents"][0]["confirmed"]=False
    assert client.post("/api/matches",headers=headers,json=body).status_code==422
    assert client.get("/api/account/matches",headers=headers).status_code==401


def test_revoked_membership_cannot_be_unlocked(integration):
    db,settings,client=integration
    headers={"X-Session-Token":"d"*64}
    response=client.post("/api/matches",headers=headers,json=request())
    worker(db,settings,once=True)
    id=response.json()["session_id"]
    db.execute("update sm.source_artifacts set metadata=jsonb_set(metadata,'{active}','false') where kind='demo_register'")
    assert client.get(f"/api/matches/{id}",headers=headers).json()["total_count"]==0
    seed_demo(db,settings)


def test_rls_on_all_private_tables(integration):
    db,_,_=integration
    assert all(r["relrowsecurity"] for r in db.rows("select c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('sm','sm_private') and c.relkind='r'"))
    assert db.one("select relrowsecurity from pg_class where oid='public.sponsormatch_migrations'::regclass")['relrowsecurity']
    role="sponsormatch_test_reader"
    with db.transaction() as c:
        c.execute("do $$ begin if not exists(select from pg_roles where rolname='sponsormatch_test_reader') then create role sponsormatch_test_reader; end if; end $$")
        c.execute("grant usage on schema sm_private to sponsormatch_test_reader")
        c.execute("grant select on all tables in schema sm_private to sponsormatch_test_reader")
        c.execute("set local role sponsormatch_test_reader")
        assert not c.execute("select * from sm_private.match_sessions").fetchall()


def test_import_replay_conservative(integration,tmp_path):
    db,_,_=integration
    path=tmp_path/"export.csv"
    path.write_text('Company Name,Company UUID,Source Record ID,Indicative Tags,Field States,Current Job Count,Town,Email\nExample Import,abc,789,accountancy,{},99,Leeds,hello@example.com\n')
    import_csv(db,path,"test-import")
    import_csv(db,path,"test-import")
    rows=db.rows("select payload from sm.employers where payload->>'source_namespace'='test-import'")
    assert len(rows)==1
    assert rows[0]["payload"]["identity_status"]=="unverified"
    assert not rows[0]["payload"]["vacancies"]
    assert all(c["attribution"]=="unverified" for c in rows[0]["payload"]["claims"])


def test_immutable_claim_versions_and_failed_refresh(integration):
    from datetime import UTC,datetime,timedelta
    from sponsor_match.models import Employer,Claim
    db,_,_=integration
    id=str(uuid4());claim_id="test:"+id
    first=Claim(id=claim_id,kind="activity",text="Mechanical design",excerpt="Mechanical design",source_url="https://acme.example/services",observed_at=datetime.now(UTC)-timedelta(days=2),source_kind="first_party",attribution="accepted")
    employer=Employer(id=id,name="Evidence history test",source_namespace="test:evidence",source_key=id,identity_status="accepted",claims=[first])
    db.save_employer(employer)
    updated=employer.model_copy(deep=True)
    updated.claims[0].text="Mechanical design and CAD"
    updated.claims[0].excerpt="Mechanical design and CAD"
    updated.claims[0].observed_at=datetime.now(UTC)-timedelta(days=1)
    db.save_employer(updated)
    failed=updated.model_copy(deep=True)
    failed.claims[0].state="temporarily_unavailable"
    failed.claims[0].observed_at=datetime.now(UTC)
    db.save_employer(failed)
    db.save_employer(failed)
    observations=db.rows("select state,payload from sm.observations where employer_id=%s order by observed_at",(id,))
    assert len(observations)==3
    assert observations[0]["payload"]["text"]=="Mechanical design"
    assert observations[2]["state"]=="temporarily_unavailable"
    current=db.one("select c.payload,o.payload as observation from sm.accepted_claims c join sm.observations o on o.id=c.observation_id where c.id=%s",(claim_id,))
    assert current["payload"]==current["observation"]
    assert current["payload"]["text"]=="Mechanical design and CAD"
    assert current["payload"]["state"]=="found"
    late=employer.model_copy(deep=True)
    db.save_employer(late)
    assert db.employer(id).claims[0].text=="Mechanical design and CAD"


def test_reviewed_identity_link_retains_evidence_and_namespaces(integration):
    from datetime import UTC,datetime
    from sponsor_match.models import Employer,Claim
    from sponsor_match.identity import link_employers
    db,_,_=integration
    ids=[str(uuid4()),str(uuid4())]
    for i,id in enumerate(ids):
        claim=Claim(id="link:"+id,kind="activity",text="Mechanical design",excerpt="Mechanical design",source_url="https://acme.example/services",source_kind="first_party",attribution="accepted",observed_at=datetime.now(UTC))
        db.save_employer(Employer(id=id,name="Same legal employer",company_number="01234567",identity_status="accepted",source_namespace="link-test:"+id,source_key=str(i),claims=[claim]))
    evidence=db.one("select id from sm.observations where employer_id=%s limit 1",(ids[1],))["id"]
    link_employers(db,*ids,evidence,True)
    canonical=db.employer(ids[0]);retired=db.employer(ids[1])
    assert len(canonical.claims)==2 and retired.identity_status=="quarantined"
    assert canonical.source_namespace=="link-test:"+ids[0]
    assert db.one("select count(*) n from sm.accepted_claims where employer_id=%s",(ids[0],))["n"]==2
    assert str(db.one("select employer_id from sm.employer_source_keys where namespace=%s",("link-test:"+ids[1],))["employer_id"])==ids[0]


@pytest.mark.parametrize('legacy_identifier',['','01234567'])
def test_register_linkage_preserves_legacy_sources_and_detects_supported_conflicts(integration,legacy_identifier):
    from datetime import datetime,UTC
    from psycopg.types.json import Jsonb
    from sponsor_match.models import Employer
    from sponsor_match.ingest import reconcile_memberships
    from sponsor_match.taxonomy import key
    db,_,_=integration
    artifact_id=uuid4().hex;canonical_id=str(uuid4());legacy_id=str(uuid4());name='Register linkage '+uuid4().hex
    db.execute("insert into sm.source_artifacts(id,kind,namespace,url,sha256,publication_date,metadata) values(%s,'official_register',%s,'https://www.gov.uk/register',%s,%s,%s)",(artifact_id,'test:'+artifact_id,artifact_id,datetime.now(UTC).date(),Jsonb({'active':True})))
    try:
        db.execute("insert into sm.register_entries values(%s,'1',%s,'test town','Skilled Worker','Worker (A rating)',%s)",(artifact_id,key(name),Jsonb({'County':''})))
        current=db.save_employer(Employer(id=canonical_id,name=name,town='Test Town',county='County A',identity_status='accepted',source_namespace='current:'+artifact_id,source_key='1'))
        legacy=db.save_employer(Employer(id=legacy_id,name=name,town='Test Town',company_number=legacy_identifier,identity_status='unverified',source_namespace='legacy:'+artifact_id,source_key='2'))
        reconcile_memberships(db,[canonical_id,legacy_id])
        assert db.employer(canonical_id).memberships[0].attribution==('unverified' if legacy_identifier else 'accepted')
        assert db.employer(legacy_id).identity_status=='unverified'
        assert db.employer(legacy_id).memberships[0].attribution=='unverified'
        version=db.employer(canonical_id).version
        reconcile_memberships(db,[canonical_id])
        assert db.employer(canonical_id).version==version
        assert db.one("select count(*) n from sm.observations where employer_id=%s and kind='sponsor_linkage'",(canonical_id,))['n']==1
        if legacy_identifier:
            assert db.employer(legacy_id).company_number==legacy_identifier
            decision=db.one("select state,payload from sm.observations where employer_id=%s and kind='sponsor_linkage'",(canonical_id,))
            assert decision['payload']['supported_identity_count']==2
            assert decision['state']=='inconclusive'
            return
        # A second supported identity remains a genuine conflict, even though
        # the old raw source observation alone did not block the current one.
        legacy.identity_status='accepted';db.save_employer(legacy)
        reconcile_memberships(db,[canonical_id])
        assert db.employer(canonical_id).memberships[0].attribution=='unverified'
        assert db.one("select count(*) n from sm.observations where employer_id=%s and kind='sponsor_linkage'",(canonical_id,))['n']==2
        assert str(db.one("select employer_id from sm.employer_source_keys where namespace=%s",(current.source_namespace,))['employer_id'])==canonical_id
        assert str(db.one("select employer_id from sm.employer_source_keys where namespace=%s",(legacy.source_namespace,))['employer_id'])==legacy_id
    finally:
        db.execute('delete from sm.sponsor_memberships where artifact_id=%s',(artifact_id,))
        db.execute('delete from sm.register_entries where artifact_id=%s',(artifact_id,))
        db.execute('delete from sm.source_artifacts where id=%s',(artifact_id,))


def test_account_association_requires_owner_and_verified_email(integration,monkeypatch):
    db,settings,_=integration
    from dataclasses import replace
    from unittest.mock import Mock
    account_id=str(uuid4())
    account={"id":account_id,"email":"candidate@example.com","email_confirmed_at":"2026-10-12T00:00:00Z"}
    response=Mock();response.json.return_value=account;response.raise_for_status.return_value=None
    monkeypatch.setattr("sponsor_match.api.httpx.get",lambda *a,**k:response)
    auth_settings=replace(settings,supabase_url="https://auth.example",supabase_publishable_key="test-public-key")
    auth_db=Database(settings.database_url)
    with TestClient(create_app(auth_settings,auth_db)) as client:
        owner={"X-Session-Token":"e"*64}
        id=client.post("/api/matches",headers=owner,json=request()).json()["session_id"]
        worker(auth_db,settings,once=True)
        other={"X-Session-Token":"f"*64,"Authorization":"Bearer test-token"}
        assert client.post("/api/account/associate",headers=other).json()["associated"]==0
        owner["Authorization"]="Bearer test-token"
        assert client.post("/api/account/associate",headers=owner).json()["associated"]>=1
        assert client.get("/api/matches/"+id,headers=other).status_code==200
        assert any(str(s["id"])==id for s in client.get("/api/account/matches",headers=other).json()["sessions"])
        response.json.return_value={**account,"email_confirmed_at":None}
        assert client.get("/api/account/matches",headers=other).status_code==401


def test_refinement_reuses_verified_account_identity(integration,monkeypatch):
    db,settings,_=integration
    from dataclasses import replace
    from unittest.mock import Mock
    account={"id":str(uuid4()),"email":"refine@example.com","email_confirmed_at":"2026-10-16T00:00:00Z"}
    response=Mock();response.json.return_value=account;response.raise_for_status.return_value=None
    monkeypatch.setattr("sponsor_match.api.httpx.get",lambda *a,**k:response)
    auth_settings=replace(settings,require_verified_email=True,supabase_url="https://auth.example",supabase_publishable_key="test-public-key")
    auth_db=Database(settings.database_url)
    with TestClient(create_app(auth_settings,auth_db)) as client:
        headers={"X-Session-Token":uuid4().hex*2}
        assert client.get("/api/account/identity",headers=headers).json()=={"signed_in":False}
        assert client.get('/api/account/profile',headers=headers).status_code==401
        assert client.get('/api/account/overview',headers=headers).status_code==401
        original=request();original["identity"]={"name":"Returning Candidate","email":account["email"]}
        id=client.post("/api/matches",headers=headers,json=original).json()["session_id"]
        assert 'loading_context' not in client.get('/api/matches/'+id,headers=headers).json()
        headers["Authorization"]="Bearer test-token"
        client.post("/api/account/associate",headers=headers)
        overview=client.get('/api/account/overview',headers=headers).json()
        assert overview['first_name']=='Returning' and overview['sessions'][0]['id']==id
        assert overview['sessions'][0]['roles']==['Mechanical engineer']
        assert set(overview)=={'first_name','profile','sessions','bookmarks'}
        assert 'refine@example.com' not in str(overview) and 'visa_context' not in str(overview)
        context=client.get('/api/matches/'+id,headers=headers).json()['loading_context']
        assert context['roles']==['Mechanical engineer'] and context['skills']==['CAD']
        assert set(context)=={'roles','background','specialization','skills','locations','related_roles_enabled'}
        assert client.get('/api/matches/'+id,headers={'X-Session-Token':uuid4().hex*2}).status_code==404
        assert client.get("/api/account/identity",headers=headers).json()=={"signed_in":True}
        restored=client.get('/api/account/profile',headers=headers).json()
        assert restored['profile']['background']=={'subject':'Mechanical Engineering','specialization':''}
        assert set(restored)=={'profile','account_key'}
        assert 'email' not in str(restored) and 'visa_context' not in str(restored)
        refined=request();refined.pop("identity")
        result=client.post("/api/matches",headers=headers,json=refined)
        assert result.status_code==202 and result.json()["verification_required"] is False
        saved=auth_db.owned_session(result.json()["session_id"],headers["X-Session-Token"],account["id"])
        assert saved["identity"]==original["identity"]
        # A different signed-in account never inherits a previous user's name.
        account.update(id=str(uuid4()),email="another@example.com")
        other_overview=client.get('/api/account/overview',headers=headers).json()
        assert other_overview=={'first_name':None,'profile':None,'sessions':[],'bookmarks':[]}
        other_profile=client.get('/api/account/profile',headers=headers).json()
        assert other_profile['profile'] is None and other_profile['account_key']!=restored['account_key']
        refined["idempotency_key"]=str(uuid4())
        result=client.post("/api/matches",headers=headers,json=refined)
        saved=auth_db.owned_session(result.json()["session_id"],headers["X-Session-Token"],account["id"])
        assert saved["identity"]["email"]==account["email"]
        assert saved["identity"]["name"]!="Returning Candidate"
        headers.pop("Authorization")
        assert client.post("/api/matches",headers=headers,json=refined).status_code==422
        for _ in range(3):
            worker(auth_db,auth_settings,once=True)


def test_real_pgvector_branch_and_filtered_retrieval(integration,monkeypatch):
    db,settings,_=integration
    from sponsor_match.models import Profile
    from sponsor_match.search import Matcher
    from dataclasses import replace
    import json
    from types import SimpleNamespace
    from sponsor_match.indexes import build_index,publish_index
    from sponsor_match.providers import ProviderUnavailable
    vector=[1.]+[0.]*767
    first=build_index(db,settings,provider=SimpleNamespace(embeddings=lambda texts:[vector for _ in texts]))
    matcher=Matcher(db,replace(settings,openai_api_key="mocked-no-network"))
    monkeypatch.setattr(matcher.provider,"embeddings",lambda texts:[vector for _ in texts])
    results,mode,_=matcher.search(Profile.model_validate(request()["profile"]))
    assert results and mode=="hybrid"
    assert all(r.features["semantic"]==1. for r in results)
    # Vectors exercise Postgres, not an external model quality claim.
    def unavailable(texts):raise ProviderUnavailable("test outage")
    reused=build_index(db,settings,provider=SimpleNamespace(embeddings=unavailable))
    assert reused['generated_documents']==0
    with pytest.raises(ProviderUnavailable):
        build_index(db,replace(settings,embedding_model="test-new-model"),provider=SimpleNamespace(embeddings=unavailable))
    assert str(db.one("select id from sm.search_index_versions where active")['id'])==reused['published_index']
    publish_index(db,first['published_index'])
    assert str(db.one("select id from sm.search_index_versions where active")['id'])==first['published_index']
    # Free local vectors occupy a separate typed column; rollback keeps both spaces.
    from sponsor_match.config import LOCAL_MODEL
    local_settings=replace(settings,embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384)
    smaller=[1.]+[0.]*383
    local_index=build_index(db,local_settings,provider=SimpleNamespace(embeddings=lambda texts:[smaller for _ in texts]))
    local_matcher=Matcher(db,local_settings)
    monkeypatch.setattr(local_matcher.provider,'embeddings',lambda texts:[smaller for _ in texts])
    local_results,local_mode,_=local_matcher.search(Profile.model_validate(request()['profile']))
    assert local_results and local_mode=='hybrid'
    assert db.one('select dimensions from sm.search_index_versions where active')['dimensions']==384
    # An old 768-dimensional application must fall back rather than mix spaces.
    _,wrong_mode,_=matcher.search(Profile.model_validate(request()['profile']))
    assert wrong_mode=='lexical_concept_fallback'
    db.execute("update sm.search_index_versions set active=false where active")
    db.execute("delete from sm.query_cache")


def test_verification_gate_withholds_all_results_until_owner_association(integration,monkeypatch):
    from dataclasses import replace
    from unittest.mock import Mock
    _,settings,_=integration
    account={"id":str(uuid4()),"email":"different@example.com","email_confirmed_at":"2026-10-14T00:00:00Z"}
    response=Mock();response.json.side_effect=lambda:account;response.raise_for_status.return_value=None
    monkeypatch.setattr('sponsor_match.api.httpx.get',lambda *a,**k:response)
    settings=replace(settings,require_verified_email=True,supabase_url='https://auth.example',supabase_publishable_key='test-public')
    db=Database(settings.database_url)
    with TestClient(create_app(settings,db)) as client:
        headers={'X-Session-Token':'1'*64}
        id=client.post('/api/matches',headers=headers,json=request()).json()['session_id']
        worker(db,settings,once=True)
        data=client.get('/api/matches/'+id,headers=headers).json()
        assert data['verification_required'] and 'preview' not in data and 'total_count' not in data
        assert client.get(f'/api/matches/{id}/results',headers=headers).status_code==403
        assert client.post(f'/api/matches/{id}/demo-unlock',headers=headers).status_code==403
        headers['Authorization']='Bearer test-token'
        assert client.post('/api/account/associate',headers=headers).json()['associated']==0
        assert client.get(f'/api/matches/{id}/results',headers=headers).status_code==403
        account['email']='candidate@example.com'
        assert client.post('/api/account/associate',headers=headers).json()['associated']>=1
        data=client.get('/api/matches/'+id,headers=headers).json()
        assert not data['verification_required'] and len(data['preview'])==3


def test_visible_card_includes_imported_contact_routes(integration):
    from sponsor_match.models import Channel
    from datetime import datetime,UTC
    db,settings,client=integration
    headers={'X-Session-Token':'contact-display-check-'+'f'*40}
    created=client.post('/api/matches',json=request(),headers=headers)
    assert created.status_code==202
    id=created.json()['session_id'];worker(db,settings,once=True)
    preview=client.get('/api/matches/'+id,headers=headers).json()['preview']
    employer=db.employer(preview[0]['employer_id'])
    employer.channels.extend([Channel(kind='email',value='recorded@employer.example',observed_at=datetime.now(UTC)),Channel(kind='linkedin_company',value='https://linkedin.com/company/recorded-employer',observed_at=datetime.now(UTC)),Channel(kind='search_page',value='https://www.totaljobs.com/jobs/acme?q=acme',observed_at=datetime.now(UTC))])
    db.save_employer(employer)
    response=client.get('/api/matches/'+id,headers=headers)
    card=next(c for c in response.json()['preview'] if c['employer_id']==employer.id)
    assert any(c['value']=='recorded@employer.example' and c['note']=='Imported · not rechecked' for c in card['channels'])
    assert any(c['kind']=='linkedin_company' and 'Imported' in c['note'] for c in card['channels'])
    assert any(c['label']=='Totaljobs · search results' for c in card['channels'])


def test_personal_overview_excludes_expired_searches(integration,monkeypatch):
    from dataclasses import replace
    from unittest.mock import Mock
    db,settings,_=integration
    account={'id':str(uuid4()),'email':'expiry-check@example.invalid','email_confirmed_at':'2026-10-18T00:00:00Z'}
    response=Mock();response.json.return_value=account;response.raise_for_status.return_value=None
    monkeypatch.setattr('sponsor_match.api.httpx.get',lambda *a,**k:response)
    auth_settings=replace(settings,require_verified_email=True,supabase_url='https://auth.example',supabase_publishable_key='test')
    auth_db=Database(settings.database_url)
    with TestClient(create_app(auth_settings,auth_db)) as client:
        headers={'X-Session-Token':uuid4().hex*2,'Authorization':'Bearer test'}
        body=request();body['visa_context']={'route':'Private test context'}
        session=client.post('/api/matches',headers=headers,json=body).json()['session_id']
        result=client.get('/api/account/overview',headers=headers).json()
        assert len(result['sessions'])==1 and 'Private test context' not in str(result)
        row=auth_db.one('select profile_id from sm_private.match_sessions where id=%s',(session,))
        auth_db.execute("update sm_private.candidate_profiles set expires_at=now()-interval '1 second' where id=%s",(row['profile_id'],))
        assert client.get('/api/account/overview',headers=headers).json()=={'first_name':None,'profile':None,'sessions':[],'bookmarks':[]}
        # Isolate this expired synthetic profile from subsequent worker/retention checks.
        auth_db.execute('delete from sm.work_items where dedupe_key=%s',('match:'+session,))
        auth_db.execute('delete from sm_private.match_sessions where id=%s',(session,))
        auth_db.execute('delete from sm_private.candidate_profiles where id=%s',(row['profile_id'],))


def test_workspace_profiles_refresh_stars_and_bookmarks(integration,monkeypatch):
    from dataclasses import replace
    from unittest.mock import Mock
    from sponsor_match.search import Matcher
    db,settings,_=integration
    account={'id':str(uuid4()),'email':'workspace@example.invalid','email_confirmed_at':'2026-10-18T00:00:00Z'}
    response=Mock();response.json.side_effect=lambda:dict(account);response.raise_for_status.return_value=None
    monkeypatch.setattr('sponsor_match.api.httpx.get',lambda *a,**k:response)
    config=replace(settings,require_verified_email=True,supabase_url='https://auth.example',supabase_publishable_key='test')
    headers={'X-Session-Token':uuid4().hex*2,'Authorization':'Bearer test'}
    matcher=Matcher(db,config)
    with TestClient(create_app(config,Database(settings.database_url))) as client:
        first=client.post('/api/matches',headers=headers,json=request()).json()['session_id']
        second_body=request();second_body['profile']['background']['subject']='Software engineering'
        second=client.post('/api/matches',headers=headers,json=second_body).json()['session_id']
        matcher.process_session(first);matcher.process_session(second)
        assert client.get('/api/account/profile?session_id='+first,headers=headers).json()['profile']['background']['subject']=='Mechanical Engineering'
        assert client.get('/api/account/profile?session_id='+second,headers=headers).json()['profile']['background']['subject']=='Software engineering'
        assert client.post(f'/api/matches/{first}/star',headers=headers,json={'saved':True}).json()=={'starred':True}
        overview=client.get('/api/account/overview',headers=headers).json()
        assert overview['sessions'][0]['id']==first and overview['sessions'][0]['starred']
        results=client.get(f'/api/matches/{first}/results',headers=headers).json()['results']
        eid=results[0]['employer_id']
        locked=str(db.one('select employer_id from sm_private.match_results where session_id=%s and rank>=3 limit 1',(first,))['employer_id'])
        assert client.post(f'/api/matches/{first}/bookmarks/{locked}',headers=headers,json={'saved':True}).status_code==404
        for _ in range(2):assert client.post(f'/api/matches/{first}/bookmarks/{eid}',headers=headers,json={'saved':True}).json()=={'bookmarked':True}
        overview=client.get('/api/account/overview',headers=headers).json()
        assert [e['employer_id'] for e in overview['bookmarks']]==[eid]
        assert client.get(f'/api/matches/{first}/results',headers=headers).json()['results'][0]['bookmarked']
        client.post(f'/api/matches/{first}/demo-unlock',headers=headers,json={})
        key=str(uuid4());body={'idempotency_key':key}
        assert client.post(f'/api/matches/{first}/refresh',headers=headers,json=body).status_code==202
        assert client.post(f'/api/matches/{first}/refresh',headers=headers,json=body).status_code==202
        assert db.one('select revision from sm_private.match_sessions where id=%s',(first,))['revision']==1
        assert client.post(f'/api/matches/{first}/refresh',headers=headers,json={'idempotency_key':str(uuid4())}).status_code==409
        # An old worker cannot publish over the newer refresh.
        db.save_results(first,[],'stale',{},revision=0)
        assert client.get(f'/api/matches/{first}',headers=headers).json()['status']=='queued'
        matcher.process_session(first,revision=1)
        saved=client.get(f'/api/matches/{first}',headers=headers).json()
        assert saved['access']=='demo_unlocked' and saved['starred'] and saved['revision']==1
        assert client.get('/api/account/overview',headers=headers).json()['bookmarks'][0]['employer_id']==eid
        # Refinement updates the same shortlist while preserving the other profile.
        updated=request()['profile'];updated['background']['subject']='Mechanical design'
        assert client.post(f'/api/matches/{first}/refresh',headers=headers,json={'idempotency_key':str(uuid4()),'profile':updated}).status_code==202
        assert client.get('/api/account/profile?session_id='+first,headers=headers).json()['profile']['background']['subject']=='Mechanical design'
        assert client.get('/api/account/profile?session_id='+second,headers=headers).json()['profile']['background']['subject']=='Software engineering'
        matcher.process_session(first,revision=2)
        other=dict(account);account['id']=str(uuid4())
        assert client.post(f'/api/matches/{first}/star',headers=headers,json={'saved':False}).status_code==404
        assert client.post(f'/api/matches/{first}/refresh',headers=headers,json={'idempotency_key':str(uuid4())}).status_code==403
        assert client.get('/api/account/profile?session_id='+first,headers=headers).status_code==404
        assert client.get('/api/account/overview',headers=headers).json()['bookmarks']==[]
        account.update(other)
        assert client.post(f'/api/account/bookmarks/{eid}',headers=headers,json={'saved':False}).json()=={'bookmarked':False}
        assert client.get('/api/account/overview',headers=headers).json()['bookmarks']==[]
        # Feedback remains independently recorded for a later admin view.
        assert client.post('/api/feedback',headers=headers,json={'session_id':first,'employer_id':eid,'event':'not_relevant'}).status_code==201
        assert db.one("select count(*) n from sm_private.feedback_events where session_id=%s and event='not_relevant'",(first,))['n']==1
