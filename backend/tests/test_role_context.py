from sponsor_match.models import Profile,RoleIntent,Skill
from sponsor_match.ranking import rank,interleave_intents
from sponsor_match.taxonomy import Taxonomy,Concept
from test_matching import employer,profile
from test_csv_baseline import claim


def test_longer_occupation_is_not_its_shared_head_noun(employer):
    taxonomy=Taxonomy([Concept('general','Operator',[],[],[],[],[]),Concept('specific','Crane operator',[],[],[],[],[])])
    p=Profile.model_validate({'background':{'subject':'Operations'},'role_intents':[{'raw_label':'Operator','confirmed':True}],'career_stage':'experienced'})
    employer.claims=[claim('Crane operator','historical_role')]
    assert rank(employer,p,taxonomy,'snapshot') is None


def test_explicit_occupation_alias_still_matches(employer):
    taxonomy=Taxonomy([Concept('broad','Work specialist',['Work assistant'],[],[],[],[]),Concept('official','Work assistants',['Work assistant'],[],[],[],[])])
    p=Profile.model_validate({'background':{'subject':'Work studies'},'role_intents':[{'raw_label':'Work specialist','confirmed':True}],'career_stage':'graduate'})
    employer.claims=[claim('Work assistant','historical_role')]
    assert rank(employer,p,taxonomy,'snapshot') is not None


def test_unrelated_role_cannot_supply_skills_or_graduate_credit(employer,profile):
    employer.claims=[claim('Mechanical engineer, Graduate CAD designer','historical_role')]
    result=rank(employer,profile,Taxonomy(),'snapshot')
    assert result.features['task']==0
    assert 'Graduate CAD designer' not in result.explanation['text']


def test_additional_unmatched_skill_does_not_dilute_supported_skill_credit(employer,profile):
    first=rank(employer,profile,Taxonomy(),'snapshot',.5)
    profile.skills.append(Skill(label='Knitting'))
    second=rank(employer,profile,Taxonomy(),'snapshot',.5)
    assert first.features['task']==second.features['task']
    profile.certifications=['CAD']
    assert rank(employer,profile,Taxonomy(),'snapshot',.5).features['task']==first.features['task']


def test_specific_alias_retains_subject_without_profession_exception(employer):
    taxonomy=Taxonomy([Concept('broad','Research scientist',['Crystal scientist'],['laboratory research'],[],[],[])])
    p=Profile.model_validate({'background':{'subject':'Crystal science'},'role_intents':[{'raw_label':'Crystal scientist','confirmed':True}],'career_stage':'graduate'})
    employer.claims=[claim('Laboratory research in economics')]
    assert rank(employer,p,taxonomy,'snapshot') is None
    employer.claims=[claim('Laboratory research in crystal growth')]
    assert rank(employer,p,taxonomy,'snapshot') is not None


def test_multiple_interests_receive_preview_representation(employer,profile):
    from dataclasses import replace
    a=rank(employer,profile,Taxonomy(),'snapshot',.8)
    b=replace(a,employer_id='other',score=.01,features={**a.features,'intent':'Accountant'})
    a2=replace(a,employer_id='another')
    result=interleave_intents([a,a2,b],[profile.role_intents[0],RoleIntent(raw_label='Accountant')],3)
    assert result[1].employer_id=='other'


def test_classification_code_is_not_a_synonym_list(employer):
    taxonomy=Taxonomy([Concept('ons:group','Installation workers',['Pipe fitter','Ventilation technician'],[],[],[],[],metadata={'authority':'ONS','four_digit_parent':'1234'})])
    p=Profile.model_validate({'background':{'subject':'Installation'},'role_intents':[{'raw_label':'Pipe fitter','confirmed':True}],'career_stage':'experienced'})
    employer.claims=[claim('Ventilation technician','historical_role')]
    assert rank(employer,p,taxonomy,'snapshot') is None
    employer.claims=[claim('Pipe fitter','historical_role')]
    assert rank(employer,p,taxonomy,'snapshot') is not None


def test_training_and_merchandising_do_not_establish_delivery_of_profession(employer):
    p=Profile.model_validate({'background':{'subject':'Computing'},'role_intents':[{'raw_label':'Cybersecurity analyst','confirmed':True}],'career_stage':'graduate'})
    employer.claims=[claim('Cybersecurity education')]
    assert rank(employer,p,Taxonomy(),'snapshot') is None
    employer.claims=[claim('Cybersecurity services')]
    assert rank(employer,p,Taxonomy(),'snapshot') is not None


def test_acronym_does_not_become_a_different_specialization(employer):
    p=Profile.model_validate({'background':{'subject':'Human resources'},'role_intents':[{'raw_label':'HR specialist','confirmed':True}],'career_stage':'graduate'})
    employer.claims=[claim('Human Resources Assistant','historical_role')]
    assert rank(employer,p,Taxonomy(),'snapshot') is not None


def test_explanation_keeps_original_excerpt_and_separate_matched_spans(employer,profile):
    employer.claims=[claim('Mechanical engineer, Receptionist, Mechanical design engineer','historical_role')]
    result=rank(employer,profile,Taxonomy(),'snapshot')
    source=result.explanation['sources'][0]
    assert source['excerpt']==employer.claims[0].excerpt
    assert all(span in source['excerpt'] for span in source['matched_spans'])
    assert 'Receptionist' not in result.explanation['text']


def test_database_pool_defaults_fit_free_session_pool_budget(monkeypatch):
    from sponsor_match.db import Database
    monkeypatch.delenv('SPONSORMATCH_DB_POOL_SIZE',raising=False)
    db=Database('postgresql://localhost/test')
    assert db.pool.max_size==4
    db.close()
    monkeypatch.setenv('SPONSORMATCH_DB_POOL_SIZE','0')
    import pytest
    with pytest.raises(ValueError):Database('postgresql://localhost/test')
