import json
import numpy as np
import pytest
from pydantic import ValidationError
from sponsor_match.onboarding import OnboardingLibrary,SuggestionContext
from sponsor_match.config import Settings
from test_api import integration


def test_skills_are_from_the_selected_occupation_and_require_confirmation(monkeypatch):
    library=OnboardingLibrary(Settings())
    roles=np.eye(2,384,dtype=np.float32);skills=np.eye(3,384,dtype=np.float32)
    library.bundle={'signature':'fixture','manifest':{'source_version':'fixture'},'roles':roles,'skill_vectors':skills,
        'occupations':[{'id':'role-a','label':'Unfamiliar niche','description':'A specialist role','skills':[{'id':'s1','essential':True}]},
                       {'id':'role-b','label':'Other work','description':'Other specialist work','skills':[{'id':'s2','essential':True}]}],
        'skills':[{'id':'s1','label':'A source-backed capability'},{'id':'s2','label':'Another capability'},{'id':'s3','label':'Unrelated'}],
        'skill_index':{'s1':0,'s2':1,'s3':2},'aliases':{'unfamiliar niche':0,'other work':1}}
    monkeypatch.setattr(library,'load',lambda:True)
    class Encoder:
        def embeddings(self,texts):return [[1.]+[0.]*383 for _ in texts]
    monkeypatch.setattr('sponsor_match.onboarding.embedding_provider',lambda _:Encoder())
    result=library.suggest(SuggestionContext(text='Unfamiliar niche',roles=['Unfamiliar niche']))
    assert [s['id'] for s in result['skill_suggestions']]==['s1']
    assert result['skill_suggestions'][0]['requires_user_confirmation'] and not result['qualification_claims']
    assert result['experience_prompts'][0]['prompt'].startswith('Describe a real project')
    assert library.suggest(SuggestionContext(text='Unfamiliar niche',roles=['Unfamiliar niche'],skills=['A source-backed capability']))['skill_suggestions']==[]


def test_unknown_niches_can_continue_without_invented_skill_suggestions(tmp_path,monkeypatch):
    monkeypatch.setenv('SPONSORREACH_ONBOARDING_DATA',str(tmp_path))
    assert OnboardingLibrary(Settings()).suggest(SuggestionContext(text='Previously unseen niche'))['skill_suggestions']==[]


def test_context_limits_prevent_oversized_or_invalid_suggestion_requests():
    with pytest.raises(ValidationError):SuggestionContext(text='valid',roles=['x'*121])
    with pytest.raises(ValidationError):SuggestionContext(text='x'*501)


def test_manual_worker_filter_leaves_import_and_crawl_jobs_unclaimed(integration):
    from uuid import uuid4
    from datetime import datetime,UTC,timedelta
    from psycopg.types.json import Jsonb
    db,_,_=integration
    blocked=str(uuid4());allowed=str(uuid4());at=datetime.now(UTC)-timedelta(days=10)
    for id,kind in [(blocked,'refresh_channel'),(allowed,'match')]:
        db.execute("insert into sm.work_items(id,kind,dedupe_key,payload,available_at) values(%s,%s,%s,%s,%s)",(id,kind,id,Jsonb({}),at))
    try:
        item=db.claim_work(kinds=['match']);assert str(item['id'])==allowed
        assert db.one('select state from sm.work_items where id=%s',(blocked,))['state']=='pending'
    finally:db.execute('delete from sm.work_items where id=any(%s::uuid[])',([blocked,allowed],))
