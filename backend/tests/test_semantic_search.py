"""Evidence boundary checks for the offline semantic experiment."""
import gzip
import json
from dataclasses import replace

import numpy as np
import pytest

from sponsor_match.config import Settings,LOCAL_MODEL
from sponsor_match.models import Profile
from sponsor_match.semantic_search import SemanticMatcher,unambiguous_aliases
from test_matching import employer


def test_official_ambiguous_alias_is_not_forced_into_one_occupation():
    aliases=unambiguous_aliases([
        {'label':'Occupation A','aliases':['Specialist','First title']},
        {'label':'Occupation B','aliases':['Specialist','Second title']},
    ])
    assert 'specialist' not in aliases
    assert aliases['first title']==0 and aliases['second title']==1


@pytest.mark.parametrize('problem',[None,'stale_version','foreign_quote','wrong_entity','wrong_route','missing_channel','non_professional_context','non_professional_context_with_role','ambiguous_unqualified_role','niche_role_wrong_taxonomy'])
def test_semantic_similarity_cannot_bypass_attribution_or_current_employer_gates(tmp_path,monkeypatch,employer,problem):
    employer.version='current'
    employer.claims[0].text='Mechanical design'
    employer.claims[0].excerpt='Our services include Mechanical design.'
    v=np.zeros((1,384),dtype=np.float32);v[0,0]=1
    # This fixture deliberately changes title embeddings. Give that fake
    # encoder a separate cache identity from the other parameterized cases.
    model=LOCAL_MODEL+'-niche-fixture' if problem=='niche_role_wrong_taxonomy' else LOCAL_MODEL
    (tmp_path/'manifest.json').write_text(json.dumps({'model':model,'version':'test-model'}))
    np.savez(tmp_path/'term-vectors.npz',vectors=v,term_ids=np.array(['term']))
    np.savez(tmp_path/'reference-vectors.npz',vectors=v)
    (tmp_path/'references.json').write_text(json.dumps([{'id':'uk-soc-2020:212200','label':'Mechanical engineer','aliases':[]}]))
    observation={'term_id':'term','employer_id':employer.id,'employer_version':'current',
                 'claim_id':employer.claims[0].id,'text':'Mechanical design','raw_span':'Mechanical design'}
    if problem=='stale_version':observation['employer_version']='old'
    if problem=='foreign_quote':observation['raw_span']='MECHANICAL DESIGN'
    if problem=='wrong_entity':employer.identity_status='ambiguous'
    if problem=='wrong_route':employer.memberships[0].route='Global Business Mobility'
    if problem=='missing_channel':employer.channels=[]
    if problem in {'non_professional_context','non_professional_context_with_role'}:
        employer.claims[0].text='Wholesale Mechanical design supplies'
        employer.claims[0].excerpt=employer.claims[0].text
    terms={'term':{'kind':'activity','text':'mechanical design','raw_span':'mechanical design'}}
    observations=[observation]
    if problem=='niche_role_wrong_taxonomy':
        employer.claims[0].kind='historical_role'
        employer.claims[0].text=employer.claims[0].excerpt='Unmapped specialist'
        terms['term']={'kind':'role','text':'Unmapped specialist','raw_span':'Unmapped specialist'}
        observation.update(text='Unmapped specialist',raw_span='Unmapped specialist')
        (tmp_path/'references.json').write_text(json.dumps([
            {'id':'uk-soc-2020:212200','label':'Mechanical engineer','aliases':[]},
            {'id':'uk-soc-2020:999900','label':'Different profession','aliases':[]},
        ]))
        reference_vectors=np.zeros((2,384),dtype=np.float32)
        reference_vectors[0,0]=reference_vectors[1,1]=1
        np.savez(tmp_path/'reference-vectors.npz',vectors=reference_vectors)
    if problem=='ambiguous_unqualified_role':
        employer.claims[0].kind='historical_role'
        terms['term']['kind']='role'
        (tmp_path/'references.json').write_text(json.dumps([
            {'id':'uk-soc-2020:212200','label':'First profession','aliases':['Mechanical design (first domain)']},
            {'id':'uk-soc-2020:999900','label':'Second profession','aliases':['Mechanical design (second domain)']},
        ]))
        np.savez(tmp_path/'reference-vectors.npz',vectors=v.repeat(2,axis=0))
    if problem=='non_professional_context_with_role':
        role=employer.claims[0].model_copy(update={'id':'claim-2','kind':'historical_role','text':'Mechanical Engineer','excerpt':'Mechanical Engineer'})
        employer.claims.append(role)
        terms['role']={'kind':'role','text':'Mechanical Engineer','raw_span':'Mechanical Engineer'}
        observations.append({**observation,'term_id':'role','claim_id':'claim-2','text':'Mechanical Engineer','raw_span':'Mechanical Engineer'})
        np.savez(tmp_path/'term-vectors.npz',vectors=v.repeat(2,axis=0),term_ids=np.array(['term','role']))
    with gzip.open(tmp_path/'corpus.json.gz','wt') as f:
        json.dump({'terms':terms,'observations':observations},f)
    class Provider:
        def embeddings(self,texts):
            result=v.repeat(len(texts),axis=0)
            for i,text in enumerate(texts):
                if text.startswith(('Training and education','Selling and supplying','Membership association','Wholesale')):
                    result[i,0]=0;result[i,1]=1
                if problem=='niche_role_wrong_taxonomy' and text=='mechanical engineer':
                    result[i,0]=0;result[i,1]=1
            return result.tolist()
    class DB:
        def active_snapshot(self):return 'snapshot'
        def employers(self,ids):return [employer]
    monkeypatch.setattr('sponsor_match.semantic_search.embedding_provider',lambda _:Provider())
    settings=replace(Settings(),embedding_model=model,embedding_provider='local',dimensions=384)
    matcher=SemanticMatcher(DB(),settings,tmp_path)
    profile=Profile.model_validate({'background':{'subject':'Engineering'},'role_intents':[{'raw_label':'Unmapped specialist' if problem=='niche_role_wrong_taxonomy' else 'Mechanical engineer','confirmed':True}],'career_stage':'graduate'})
    if problem=='niche_role_wrong_taxonomy':assert not matcher.title_competition.mask(0)[0]
    audit={'include_eligible_results':True}
    results,_,_=matcher.search(profile,audit=audit)
    assert len(audit['eligible_results'])==audit['eligible_before_shortlist_limit']
    if problem and problem not in {'non_professional_context_with_role','niche_role_wrong_taxonomy'}:assert not results
    else:
        assert len(results)==1
        expected='Mechanical Engineer' if problem=='non_professional_context_with_role' else 'Mechanical design'
        if problem=='niche_role_wrong_taxonomy':expected='Unmapped specialist'
        assert results[0].explanation['sources'][0]['matched_spans']==[expected]
        if problem=='non_professional_context_with_role':
            assert results[0].features['evidence_alternative_rank']==2
            assert results[0].explanation['claim_ids']==['claim-2']
        assert not results[0].features['verified_matching_vacancy']
        assert results[0].explanation['derived_relationship']['reviewed'] is False


def test_generic_role_fragments_are_learned_from_taxonomy_ambiguity():
    from sponsor_match.semantic_search import underspecified_role_words
    references=[{'id':'soc:'+code,'label':label,'aliases':[]} for code,label in
                [('111100','Hotel manager'),('222200','Finance manager'),('333300','Store manager'),('444400','Plumber')]]
    words=underspecified_role_words(references)
    assert 'manager' in words
    assert 'plumber' not in words


@pytest.mark.parametrize('relation',[1,2,3])
def test_secondary_activity_relation_requires_support_in_occupation_duties(relation):
    from sponsor_match.semantic_search import occupation_relation_permissions,activity_relation_mask
    duties=np.eye(4,dtype=np.float32)
    # One occupation explicitly performs this work; another has only subject
    # overlap. The policy operates on descriptions, without occupation names.
    occupations=np.zeros((2,4),dtype=np.float32)
    occupations[:,0]=.4
    occupations[0,relation]=.6
    occupations[1,relation]=.2
    permitted,_=occupation_relation_permissions(occupations,duties)
    evidence=np.zeros((1,4),dtype=np.float32)
    evidence[0,0]=.4;evidence[0,relation]=.8
    assert activity_relation_mask(evidence,duties,permitted=permitted[0])[0].tolist()==[True]
    assert activity_relation_mask(evidence,duties,permitted=permitted[1])[0].tolist()==[False]
    assert activity_relation_mask(evidence,duties)[0].tolist()==[False]


def test_weak_secondary_duty_similarity_does_not_grant_permission():
    from sponsor_match.semantic_search import occupation_relation_permissions
    permitted,_=occupation_relation_permissions(np.array([[.1,.2,.19,.18]]),np.eye(4))
    assert permitted.tolist()==[[True,False,False,False]]


def test_omitted_domain_qualifiers_are_detected_across_occupation_families():
    from sponsor_match.semantic_search import ambiguous_unqualified_titles
    titles=ambiguous_unqualified_titles([
        {'id':'soc:111101','label':'First profession','aliases':['Service lead (first domain)','Specific role']},
        {'id':'soc:222201','label':'Second profession','aliases':['Service lead (second domain)']},
        {'id':'soc:222202','label':'Second specialization','aliases':['Specific second role']},
    ])
    assert 'service lead' in titles
    assert 'specific role' not in titles
    assert 'specific second role' not in titles


def test_qualifiers_within_one_parent_do_not_create_cross_profession_ambiguity():
    from sponsor_match.semantic_search import ambiguous_unqualified_titles
    assert not ambiguous_unqualified_titles([
        {'id':'soc:111101','label':'First niche','aliases':['Role (first specialty)']},
        {'id':'soc:111102','label':'Second niche','aliases':['Role (second specialty)']},
    ])


def test_a_confidently_synonymous_occupation_is_not_a_generic_counterfactual():
    from sponsor_match.semantic_search import occupational_contrasts
    refs=np.eye(2,dtype=np.float32);parents=np.array(['1111','2222'])
    assert occupational_contrasts(['Equivalent title'],np.array([[1.,0.]]),refs,parents,0)==[]
    kept=occupational_contrasts(['Different domain'],np.array([[0.,1.]]),refs,parents,0)
    assert [label for label,_ in kept]==['Different domain']


def test_ambiguous_counterfactual_is_not_assumed_to_preserve_the_occupation():
    from sponsor_match.semantic_search import occupational_contrasts
    refs=np.array([[1.,0.],[.99,.141067]],dtype=np.float32)
    kept=occupational_contrasts(['Generic title'],np.array([[1.,0.]]),refs,np.array(['1111','2222']),0)
    assert [label for label,_ in kept]==['Generic title']
