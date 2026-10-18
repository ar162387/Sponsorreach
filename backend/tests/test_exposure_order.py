from sponsor_match.exposure_order import professional_seed,profile_tie_shortlist,semantic_source_context,source_tie_scores
from sponsor_match.models import Profile
from sponsor_match.ranking import Ranked,interleave_intents


def profile():
    return Profile.model_validate({'background':{'subject':'Professional background','specialization':'Specialist work'},'career_stage':'graduate','role_intents':[{'raw_label':'Specialist','confirmed':True}],'skills':[{'label':'Task A'},{'label':'Task B'}]})


def result(eid,score=.5,intent='Specialist'):
    return Ranked(eid,'direct',score,{'intent':intent},{},'version')


def test_stable_ties_ignore_input_order_and_do_not_change_any_scores():
    p=profile();rows=[result(str(i)) for i in range(60)]
    first=profile_tie_shortlist(rows,p,10)
    assert first==profile_tie_shortlist(list(reversed(rows)),p,10)
    assert len({r.employer_id for r in first})==10
    assert all(r.score==.5 for r in rows)
    other=p.model_copy(deep=True);other.background.specialization='Different professional work'
    assert [r.employer_id for r in first]!=[r.employer_id for r in profile_tie_shortlist(rows,other,10)]


def test_score_differences_and_intent_balance_are_preserved():
    p=profile();p.role_intents.append(p.role_intents[0].model_copy(update={'raw_label':'Second interest'}))
    rows=[result('a',.9),result('b',.8),result('c',.1,'Second interest'),result('d',.09999999999,'Second interest')]
    expected=interleave_intents(rows,p.role_intents,4)
    assert profile_tie_shortlist(rows,p,4)==expected
    assert [r.employer_id for r in profile_tie_shortlist(rows,p,2)]==['a','c']


def test_formatting_skill_order_and_nonprofessional_fields_cannot_create_new_seed():
    p=profile();other=p.model_copy(deep=True)
    other.skills.reverse();other.skills.append(other.skills[0].model_copy())
    other.background.subject='  PROFESSIONAL   BACKGROUND  '
    other.career_stage='experienced';other.location.preferred_regions=['London'];other.related_roles_enabled=True
    assert professional_seed(p)==professional_seed(other)
    other.skills[0].label='Different task'
    assert professional_seed(p)!=professional_seed(other)


def test_empty_results_and_shortlists_do_not_fabricate_employers():
    p=profile();rows=[result('only')]
    assert profile_tie_shortlist([],p,100)==[]
    assert profile_tie_shortlist(rows,p,100)==rows
    assert profile_tie_shortlist(rows,p,0)==[]


def test_source_context_only_resolves_equal_scores():
    p=profile();rows=[result('higher',.50000000001),result('weaker_source'),result('stronger_source')]
    scores={'higher':-.5,'weaker_source':.1,'stronger_source':.9}
    assert [r.employer_id for r in profile_tie_shortlist(rows,p,3,scores)]==['higher','stronger_source','weaker_source']


def test_context_removes_contacts_and_exact_identity_but_keeps_professional_terms():
    a='Acme Engineering Ltd designs CAD components to ISO 9001. Call +44 20 7946 0958 or info@acme.example https://acme.example/about'
    b=a.replace('+44 20 7946 0958','01234 567890').replace('info@acme.example','contact@acme.example')
    cleaned=semantic_source_context(a,'Acme Engineering Ltd')
    assert cleaned==semantic_source_context(b,'Acme Engineering Ltd')
    assert cleaned=='designs CAD components to ISO 9001. Call or'
    assert 'other company' in semantic_source_context('other company provides testing','Acme Engineering Ltd')


def test_context_encoder_sees_only_distinct_sanitized_quotes_for_real_ties():
    import numpy as np
    rows=[result('a'),result('b'),result('unique',.6)]
    for r in rows:r.explanation={'sources':[{'excerpt':r.employer_id+' Corporation performs specialist work'}]}
    class Store:
        calls=[]
        def encode(self,texts):
            self.calls.append(texts)
            return np.array([[1.,0.] for _ in texts])
    store=Store();names={r.employer_id:r.employer_id+' Corporation' for r in rows}
    scores=source_tie_scores(rows,np.array([1.,0.]),names,store)
    assert scores=={'a':1.,'b':1.}
    assert store.calls==[['performs specialist work']]
    assert source_tie_scores([rows[2]],np.array([1.,0.]),names,store)=={}
    assert len(store.calls)==1
