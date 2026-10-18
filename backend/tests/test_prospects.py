from pathlib import Path
import json
import pytest
from sponsor_match.prospects import VectorStore,descriptors,profile_for,occupation_references
from sponsor_match.coverage import CoverageLedger,import_benchmarks
from sponsor_match.models import Employer
from test_csv_baseline import claim
from test_api import integration
from test_matching import employer


def test_source_role_cleanup_removes_company_and_geographic_suffix():
    e=Employer(id='company-id',name='Example Care Centre',source_namespace='test',source_key='1',claims=[claim('Care Assistant – Example Care Centre, Software Engineer - London, URGENTLY HIRING: Metrology Technician','historical_role')])
    spans=list(descriptors(e))
    assert [s['text'] for s in spans]==['Care Assistant','Software Engineer','Metrology Technician']
    assert all(s['raw_span'] in e.claims[0].excerpt for s in spans)
    assert all('Example Care Centre' not in s['text'] for s in spans)


def test_synthetic_profile_contains_no_employer_identity_or_invented_skills():
    p=profile_for({'id':'group','label':'Instrumentation technician'},'Precision measurement')
    assert p.role_intents[0].confirmed and not p.skills and not p.certifications
    assert 'group' not in p.search_text()
    assert p.background.specialization=='Precision measurement'


def test_embeddings_are_reused_only_for_same_model_and_content(tmp_path):
    class Provider:
        calls=0
        def embeddings(self,texts):self.calls+=1;return [[1.]+[0.]*383 for _ in texts]
    provider=Provider();store=VectorStore(tmp_path/'vectors.sqlite',provider,'model-1')
    first=store.encode(['precision testing','software development'])
    second=store.encode(['software development','precision testing'])
    assert provider.calls==1 and (first==second).all()
    VectorStore(tmp_path/'vectors.sqlite',provider,'model-2').encode(['precision testing'])
    assert provider.calls==2


def test_invalid_embedding_count_cannot_publish_uninitialized_vectors(tmp_path):
    class Provider:
        def embeddings(self,texts):return []
    with pytest.raises(ValueError):VectorStore(tmp_path/'vectors.sqlite',Provider(),'bad').encode(['text'])


def test_exposure_frequencies_and_rank_depths_are_recorded_without_labels(tmp_path):
    ledger=CoverageLedger(tmp_path/'coverage.sqlite')
    run=ledger.start({'ranking':'v1'},'stable-key')
    assert ledger.start({'ranking':'v1'},'stable-key')==run
    p=profile_for({'label':'Technician'})
    hits=[{'employer_id':str(i),'group':'direct'} for i in range(12)]
    ledger.record(run,p.model_dump(),hits,1,{'source':'synthetic'})
    ledger.record(run,p.model_dump(),hits,1,{'source':'synthetic'})
    stats=ledger.exposures(run)
    assert len(stats)==12 and stats['0']['appearances']==1
    assert stats['0']['preview_appearances']==1 and stats['4']['preview_appearances']==0
    assert stats['11']['top10_appearances']==0
    p.experience_summary='A different synthetic prospect.'
    ledger.record(run,p.model_dump(),hits,2,{'source':'synthetic'})
    assert ledger.exposures(run)['0']['appearances']==2


def test_import_replay_does_not_create_duplicate_historical_runs(tmp_path):
    folder=tmp_path/'benchmark';folder.mkdir()
    p=profile_for({'label':'Technician'})
    (folder/'runs.json').write_text(json.dumps([{'profile':p.model_dump(),'ranking':['a','b'],'results':[]}]))
    ledger=CoverageLedger(tmp_path/'ledger.sqlite')
    a=import_benchmarks(ledger,[folder],{'a','b'})
    b=import_benchmarks(ledger,[folder,folder],{'a','b'})
    assert a[0]==b[0] and a[3]==b[3]



def test_suggestions_api_limits_input_and_excludes_employer_payload(integration,monkeypatch):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from sponsor_match.api import create_app
    from sponsor_match.config import LOCAL_MODEL
    from sponsor_match.prospects import ProspectLibrary
    db,settings,_=integration
    local=replace(settings,embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384)
    monkeypatch.setattr(ProspectLibrary,'suggest',lambda self,text:{'available':True,'suggestions':[{'label':'Precision technician','requires_user_confirmation':True}]})
    app=create_app(local,db)
    client=TestClient(app)
    assert client.post('/api/profiles/suggestions',json={'text':'x'}).status_code==422
    assert client.post('/api/profiles/suggestions',json={'text':'x'*501}).status_code==422
    result=client.post('/api/profiles/suggestions',json={'text':'Precision measurement'}).json()
    assert result['available'] and 'employer_id' not in str(result)


def test_coverage_resume_reuses_actual_hits_and_rejects_changed_snapshot(tmp_path,monkeypatch,employer):
    import gzip
    from sponsor_match.coverage import coverage_loop
    from sponsor_match.config import Settings
    from sponsor_match.ranking import Ranked
    from sponsor_match.taxonomy import Taxonomy
    folder=tmp_path/'model';folder.mkdir();employer.version='version-1'
    (folder/'manifest.json').write_text(json.dumps({'version':'model-1'}))
    (folder/'employer-versions.json').write_text(json.dumps({employer.id:employer.version}))
    (folder/'groups.json').write_text(json.dumps([{'id':'profession','label':'Mechanical engineer'}]))
    with gzip.open(folder/'links.json.gz','wt') as f:json.dump([{'employer_id':employer.id,'group_id':'profession','kind':'role','similarity':.9,'claim_id':employer.claims[0].id,'span':'Mechanical engineer'}],f)
    class DB:
        def rows(self,*args):return [{'id':employer.id}]
        def employers(self,*args):return [employer]
        def one(self,*args):return {'id':'index-1'}
        def active_snapshot(self):return 'snapshot'
        def taxonomy(self):return Taxonomy()
    class Matcher:
        calls=0
        def __init__(self,*args):pass
        def search(self,p):
            Matcher.calls+=1
            assert employer.id not in p.search_text() and employer.name not in p.search_text()
            return [Ranked(employer.id,'direct',.5,{}, {},employer.version)],'test',{}
    monkeypatch.setattr('sponsor_match.coverage.Matcher',Matcher)
    output=tmp_path/'report'
    first=coverage_loop(DB(),Settings(),folder,output,max_profiles=1,rounds=1)
    assert first['total_reached']==1 and Matcher.calls==1
    metadata=json.loads((output/'run-metadata.json').read_text())
    assert metadata['status']=='completed' and metadata['run_id']==first['run_id']
    assert metadata['stop_reason']==first['stop_reason']
    second=coverage_loop(DB(),Settings(),folder,output,max_profiles=2,rounds=1,resume=first['run_id'])
    assert second['total_reached']==1 and Matcher.calls==1
    employer.version='version-2'
    with pytest.raises(ValueError):coverage_loop(DB(),Settings(),folder,output,resume=first['run_id'])


def test_weak_career_ideas_are_not_added_to_fill_the_suggestion_limit(monkeypatch):
    import numpy as np
    from dataclasses import replace
    from sponsor_match.config import Settings,LOCAL_MODEL
    from sponsor_match.prospects import ProspectLibrary
    settings=replace(Settings(),embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384)
    library=ProspectLibrary(settings)
    groups=[{'id':str(i),'label':f'Role family {i}','reference_id':str(i),'observed_roles':[],'employer_count':5,'description':'A professional family','specializations':[],'source_url':'https://example.org/taxonomy'} for i in range(3)]
    vectors=np.zeros((3,384),dtype=np.float32);vectors[:,0]=[1.,.8,.3]
    library._bundle=('version',groups,vectors,{})
    monkeypatch.setattr(library,'load',lambda:True)
    class Encoder:
        def embeddings(self,texts):return [[1.]+[0.]*383]
    monkeypatch.setattr('sponsor_match.prospects.embedding_provider',lambda _:Encoder())
    result=library.suggest('Professional background',6)
    assert len(result['suggestions'])==1
    assert result['suggestions'][0]['requires_user_confirmation']


def test_background_model_refresh_is_deduplicated_per_published_index(integration):
    from sponsor_match.prospects import enqueue_refresh
    from uuid import uuid4
    db,_,_=integration;index=uuid4()
    first=enqueue_refresh(db,index);assert enqueue_refresh(db,index)==first
    row=db.one('select count(*) n from sm.work_items where dedupe_key=%s',(first,))
    assert row['n']==1
    db.execute("update sm.work_items set state='done' where dedupe_key=%s",(first,))


def test_model_snapshot_commit_cannot_overwrite_an_existing_version(tmp_path):
    from sponsor_match.prospects import commit_snapshot
    target=tmp_path/'published'
    for i in range(2):
        staging=tmp_path/f'staging-{i}';staging.mkdir()
        (staging/'manifest.json').write_text(json.dumps({'version':'same-inputs','build':i}))
        (staging/'data.json').write_text(str(i))
        result=commit_snapshot(staging,target)
        assert result['build']==0
    assert (target/'data.json').read_text()=='0'


def test_best_reachability_example_keeps_the_actual_profile_and_rank(tmp_path):
    ledger=CoverageLedger(tmp_path/'ledger.sqlite');run=ledger.start({'ranking':'version'})
    broad=profile_for({'label':'Engineering technician'})
    niche=profile_for({'label':'Metrology technician'},'Precision measurement')
    ledger.record(run,broad.model_dump(),[{'employer_id':'other'},{'employer_id':'target'}],1,{})
    ledger.record(run,niche.model_dump(),[{'employer_id':'target'}],2,{})
    example=ledger.best_profiles(run)['target']
    assert example['rank']==1
    assert example['profile']['role_intents'][0]['raw_label']=='Metrology technician'
    assert example['profile']['background']['specialization']=='Precision measurement'


def test_cohort_association_preserves_multiple_intents_and_abstains_on_ambiguity(monkeypatch):
    import numpy as np
    from dataclasses import replace
    from sponsor_match.config import Settings,LOCAL_MODEL
    from sponsor_match.models import Profile
    from sponsor_match.prospects import ProspectLibrary
    settings=replace(Settings(),embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384)
    library=ProspectLibrary(settings)
    groups=[{'id':str(i),'label':'Occupation '+str(i),'reference_id':str(i),'employer_count':4} for i in range(2)]
    vectors=np.zeros((2,384),dtype=np.float32);vectors[:,0]=1.
    library._cohort_bundle=('corpus-version',groups,vectors,{'precision technician':'0','accountant':'1'})
    monkeypatch.setattr(library,'load',lambda:True)
    seen=[]
    class Encoder:
        def embeddings(self,texts):seen.extend(texts);return [[1.]+[0.]*383 for _ in texts]
    monkeypatch.setattr('sponsor_match.prospects.embedding_provider',lambda _:Encoder())
    profile=Profile.model_validate({'background':{'subject':'Professional background'},'role_intents':[{'raw_label':s,'confirmed':True} for s in ['Precision technician','Accountant','Unknown specialist']],'career_stage':'experienced'})
    before=profile.model_dump()
    result=library.associate(profile)
    assert [a.get('group_id') for a in result['assignments']]==['0','1',None]
    assert result['assignments'][2]['status']=='unresolved'
    assert result['model_version']=='corpus-version' and result['qualification_claim'] is False
    assert profile.model_dump()==before and not profile.skills and not profile.certifications
    assert all('email' not in t and 'visa' not in t for t in seen)


@pytest.mark.parametrize('available',[True,False])
def test_session_cohort_analysis_is_private_and_failure_does_not_block_results(integration,monkeypatch,available):
    from dataclasses import replace
    from uuid import uuid4
    from sponsor_match.config import LOCAL_MODEL
    from sponsor_match.models import MatchRequest
    from sponsor_match.search import Matcher
    from sponsor_match.prospects import ProspectLibrary
    from sponsor_match.providers import ProviderUnavailable
    db,settings,client=integration
    settings=replace(settings,embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384)
    body=MatchRequest.model_validate({'profile':{'background':{'subject':'Engineering'},'role_intents':[{'raw_label':'Precision technician','confirmed':True}],'career_stage':'experienced'},'identity':{'name':'Private candidate','email':'private-candidate@example.invalid'},'visa_context':{'route':'Graduate'},'idempotency_key':str(uuid4())})
    token=uuid4().hex*2
    sid=db.create_session(body,token)
    matcher=Matcher(db,settings)
    monkeypatch.setattr(matcher,'search',lambda *a:([],'test',{'ranking':'test-version'}))
    def associate(self,profile):
        assert 'Private candidate' not in profile.search_text()
        assert 'private-candidate' not in profile.search_text() and 'Graduate' not in profile.search_text()
        if not available:raise ProviderUnavailable('local_model_temporarily_unavailable')
        return {'available':True,'model_version':'corpus-version','assignments':[{'group_id':'official-occupation','derived':True}]}
    monkeypatch.setattr(ProspectLibrary,'associate',associate)
    try:
        matcher.process_session(sid)
        session=db.owned_session(sid,token)
        assert session['status']=='ready'
        assert session['versions']['prospect_cohorts']['available']==available
        assert db.owned_session(sid,uuid4().hex*2) is None
        assert client.get('/api/matches/'+sid,headers={'X-Session-Token':uuid4().hex*2}).status_code==404
    finally:db.execute('delete from sm.work_items where dedupe_key=%s',('match:'+sid,))


def test_provisional_role_with_credentials_is_not_inferred_from_a_broad_intent(monkeypatch):
    import numpy as np
    from dataclasses import replace
    from sponsor_match.config import Settings,LOCAL_MODEL
    from sponsor_match.models import Profile
    from sponsor_match.prospects import ProspectLibrary
    library=ProspectLibrary(replace(Settings(),embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384))
    groups=[{'id':'raw','label':'Registered Nurse (RGN/RMN)','reference_id':None,'employer_count':10},
            {'id':'official','label':'Nursing professionals','reference_id':'soc','employer_count':10}]
    vectors=np.zeros((2,384),dtype=np.float32);vectors[0,0]=1;vectors[1,0]=.85;vectors[1,1]=np.sqrt(1-.85**2)
    library._cohort_bundle=('model',groups,vectors,{})
    monkeypatch.setattr(library,'load',lambda:True)
    class Encoder:
        def embeddings(self,texts):return [[1.]+[0.]*383 for _ in texts]
    monkeypatch.setattr('sponsor_match.prospects.embedding_provider',lambda _:Encoder())
    p=Profile.model_validate({'background':{'subject':'Nursing'},'role_intents':[{'raw_label':'Registered nurse','confirmed':True}],'career_stage':'graduate'})
    result=library.associate(p)
    assert result['assignments'][0]['group_id']=='official'
    assert not p.certifications and result['qualification_claim'] is False


def test_cohort_operator_report_deduplicates_owners_and_exports_no_identity():
    from sponsor_match.prospects import cohort_report
    def row(pid,model='v1'):
        return {'profile_id':pid,'user_id':'private-user-id','owner_hash':'private-cookie-hash','cohorts':{'available':True,'model_version':model,'assignments':[{'status':'associated','group_id':'group','label':'Professional family'}]}}
    class DB:
        def rows(self,sql):return [row('private-profile-1'),row('private-profile-2'),row('private-profile-3','v2')]
    result=cohort_report(DB())
    assert result['distinct_owners']==1
    assert [(g['model_version'],g['profile_count'],g['owner_count']) for g in result['groups']]==[('v1',2,1),('v2',1,1)]
    serialized=json.dumps(result)
    assert 'private-user-id' not in serialized and 'private-cookie-hash' not in serialized and 'private-profile-' not in serialized


def test_refresh_preserves_rankings_and_history_and_rejects_obsolete_model(integration):
    from dataclasses import replace
    from threading import RLock
    from uuid import uuid4
    from sponsor_match.config import LOCAL_MODEL
    from sponsor_match.models import MatchRequest
    from sponsor_match.prospects import refresh_cohorts,COHORT_VERSION
    from sponsor_match.ranking import Ranked
    from test_api import request
    db,settings,_=integration
    local=replace(settings,embedding_provider='local',embedding_model=LOCAL_MODEL,dimensions=384)
    sid=db.create_session(MatchRequest.model_validate(request()),uuid4().hex*2)
    eid=str(db.one('select id from sm.employers order by id limit 1')['id'])
    previous={'available':True,'algorithm':'old-algorithm','model_version':'old-model','assignments':[]}
    db.save_results(sid,[Ranked(eid,'direct',.51,{}, {},'employer-version')],'test',{'ranking':'frozen-ranking','prospect_cohorts':previous})
    before=db.rows('select * from sm_private.match_results where session_id=%s',(sid,))
    class Library:
        _lock=RLock();version='new-model'
        def load(self):return True
        def associate(self,p):return {'available':True,'algorithm':COHORT_VERSION,'model_version':self.version,'assignments':[]}
    library=Library()
    try:
        assert refresh_cohorts(db,local,library=library,session_ids=[sid],expected_version='obsolete')['updated']==0
        assert refresh_cohorts(db,local,library=library,session_ids=[sid])['updated']==1
        versions=db.one('select versions from sm_private.match_sessions where id=%s',(sid,))['versions']
        assert versions['ranking']=='frozen-ranking'
        assert versions['prospect_cohort_history']['old-algorithm:old-model']==previous
        assert before==db.rows('select * from sm_private.match_results where session_id=%s',(sid,))
        assert refresh_cohorts(db,local,library=library,session_ids=[sid])['updated']==0
        library.version='next-model'
        def changed(p):
            library.version='newer-model'
            return {'available':True,'algorithm':COHORT_VERSION,'model_version':'next-model','assignments':[]}
        library.associate=changed
        result=refresh_cohorts(db,local,library=library,session_ids=[sid])
        assert result['status']=='model_changed' and result['updated']==0
        assert db.one('select versions from sm_private.match_sessions where id=%s',(sid,))['versions']==versions
    finally:db.execute('delete from sm.work_items where dedupe_key=%s',('match:'+sid,))


def test_cohort_refresh_queue_is_idempotent_per_model(integration):
    from uuid import uuid4
    from sponsor_match.prospects import enqueue_cohort_refresh
    db,_,_=integration;version=uuid4().hex
    key=enqueue_cohort_refresh(db,version)
    assert enqueue_cohort_refresh(db,version)==key
    assert db.one('select count(*) n from sm.work_items where dedupe_key=%s',(key,))['n']==1
    db.execute("update sm.work_items set state='done' where dedupe_key=%s",(key,))


def test_model_publication_checks_cohort_references_before_replacing_pointer(tmp_path,monkeypatch):
    import numpy as np
    from dataclasses import replace
    from sponsor_match.config import Settings,LOCAL_MODEL
    from sponsor_match.intelligence import digest
    from sponsor_match.prospects import publish_model
    folder=tmp_path/'model';folder.mkdir();pointer=tmp_path/'active.json';pointer.write_text('{"version":"old"}')
    manifest={'version':'new','model':LOCAL_MODEL,'dimensions':384,'groups':1,'source_hash':digest({'employer':'v1'})}
    (folder/'manifest.json').write_text(json.dumps(manifest))
    (folder/'groups.json').write_text(json.dumps([{'id':'ref','reference_id':'ref'}]))
    np.savez(folder/'group-vectors.npz',vectors=np.ones((1,384),dtype=np.float32)/np.sqrt(384))
    class DB:
        writes=[]
        def rows(self,sql):return [{'id':'employer','version':'v1'}]
        def execute(self,sql,params):self.writes.append((sql,params))
    db=DB();settings=replace(Settings(),embedding_model=LOCAL_MODEL,embedding_provider='local',dimensions=384)
    monkeypatch.setattr('sponsor_match.prospects.active_pointer',lambda _:pointer)
    with pytest.raises(FileNotFoundError):publish_model(db,settings,folder)
    assert json.loads(pointer.read_text())['version']=='old' and not db.writes
    (folder/'references.json').write_text(json.dumps([{'id':'ref','label':'Professional family','aliases':[]}]))
    result=publish_model(db,settings,folder)
    assert json.loads(pointer.read_text())['version']=='new'
    assert result['cohort_refresh_queued'].endswith(':new') and len(db.writes)==1


def test_activity_proposals_keep_distinct_occupation_families_and_source_lineage(tmp_path):
    import gzip,numpy as np
    from sponsor_match.coverage import expand_activity_hypotheses
    references=[{'id':'soc:'+code,'label':label,'description':'Occupation duties'} for code,label in
                [('111101','Production supervisor'),('111102','Manufacturing manager'),('222201','Engineering technician'),('333301','Distant occupation')]]
    vectors=np.zeros((4,384),dtype=np.float32)
    for i,score in enumerate([1.,.98,.92,.6]):vectors[i,0]=score;vectors[i,i+1]=np.sqrt(1-score**2)
    (tmp_path/'references.json').write_text(json.dumps(references))
    np.savez(tmp_path/'reference-vectors.npz',vectors=vectors)
    np.savez(tmp_path/'term-vectors.npz',vectors=vectors[:1],term_ids=np.array(['activity']))
    observation={'employer_id':'source-employer','employer_version':'v1','term_id':'activity','claim_id':'source-claim','kind':'activity','text':'Precision manufacturing','raw_span':'Precision manufacturing'}
    with gzip.open(tmp_path/'corpus.json.gz','wt') as f:json.dump({'terms':{'activity':{'kind':'activity'}},'observations':[observation]},f)
    original_groups={'soc:111101':references[0]}
    original_links=[{**observation,'group_id':'soc:111101','span':observation['text'],'similarity':1.}]
    groups,links,stats=expand_activity_hypotheses(tmp_path,original_groups,original_links)
    assert {r['group_id'] for r in links}=={'soc:111101','soc:222201'}
    assert len(original_groups)==1 and len(original_links)==1
    added=next(r for r in links if r['group_id']=='soc:222201')
    assert added['claim_id']=='source-claim' and added['mapping_status']=='derived_not_reviewed'
    p=profile_for(groups['soc:222201'],added['span'])
    assert 'source-employer' not in p.search_text() and not p.skills and not p.certifications
