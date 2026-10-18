"""Safety contracts for the generic graph; fixtures use invented occupations."""
from datetime import datetime,UTC
from types import SimpleNamespace
import numpy as np
from sponsor_match.role_graph import RoleGraph
from sponsor_match.config import Settings
from sponsor_match.models import Profile,Employer,Claim


def graph():
    g=RoleGraph(Settings())
    occupations=[{'id':'specialist','label':'Niche practitioner','description':'Specialist work','aliases':[],
                  'skills':[{'id':'task','essential':True}],'isco':['C2000'],'narrower':[]},
                 {'id':'other','label':'Other practitioner','description':'Other work','aliases':[],
                  'skills':[{'id':'other-task','essential':True}],'isco':['C3000'],'narrower':[]}]
    g.library.bundle={'occupations':occupations,'roles':np.eye(2),'title_vectors':np.eye(2),
                      'aliases':{'niche practitioner':0,'other practitioner':1},
                      'skills':[{'id':'task','label':'Specialist procedure'},{'id':'other-task','label':'Other procedure'}],
                      'skill_index':{'task':0,'other-task':1},'skill_vectors':np.eye(2)}
    g.occupations={r['id']:r for r in occupations}
    g.payload={'terms':{'performed':{'text':'Specialist procedure services','kind':'activity'},
                        'tool':{'text':'Software for the procedure','kind':'activity'},
                        'vague':{'text':'Other work','kind':'activity'}},
               'tasks':{'performed':[['task',.9,[.2,.2,.2,.2]]],'tool':[['task',.8,[.95,.2,.2,.2]]],'vague':[['task',.9,[.2,.2,.2,.2]]]},
               'roles':{},'activities':{'performed':{'specialist':.7},'tool':{'specialist':.7},'vague':{'specialist':.36,'other':.9}},
               'skill_competition':[1.,1.],'relation_permissions':{'specialist':[False]*4,'other':[False]*4}}
    g.by_skill={'task':{'performed','tool','vague'},'other-task':set()};g.by_role={'specialist':set(),'other':set()}
    g.term_vectors=np.asarray([[1.,0.],[1.,0.],[1.,0.]]);g.term_index={'performed':0,'tool':1,'vague':2}
    g.observations={tid:[{'employer_id':tid,'employer_version':'v1','claim_id':'c','raw_span':g.payload['terms'][tid]['text']}]
                    for tid in g.term_index}
    return g


def profile(label='Niche practitioner'):
    return Profile.model_validate({'background':{'subject':'Specialist training'},'role_intents':[{'raw_label':label,'confirmed':True}],
                                   'career_stage':'graduate','skills':[{'label':'Specialist procedure'}]})


def test_task_graph_rejects_tools_and_wrong_professional_scope():
    ids,support,resolved=graph().retrieve(profile(),[[1.,0.]],[[1.,0.]])
    assert ids==['performed']
    path=support['performed']['Niche practitioner'][0]
    assert path['path']['skill_id']=='task' and path['raw_skill_alignment']==1.
    assert resolved=={'Niche practitioner':'specialist'}


def test_unknown_acronym_can_use_context_without_rewriting_the_role():
    g=graph();p=profile('XYZ')
    ids,support,_=g.retrieve(p,[[0.,0.]],[[1.,0.]],[1.,0.])
    assert ids==['performed'] and p.role_intents[0].raw_label=='XYZ'
    assert support['performed']['XYZ'][0]['path']['context_interpretation']
    assert g.retrieve(p,[[0.,0.]],[[1.,0.]])[0]==[]


def test_second_ambiguous_intent_does_not_remove_supported_results():
    from sponsor_match.models import RoleIntent
    p=profile();p.role_intents.append(RoleIntent(raw_label='XYZ',confirmed=True))
    assert graph().retrieve(p,[[1.,0.],[0.,0.]],[[1.,0.]])[0]==['performed']


def test_paths_require_current_employer_version_and_exact_source_span():
    g=graph();p=profile();_,support,_=g.retrieve(p,[[1.,0.]],[[1.,0.]])
    e=Employer(id='e',name='Fixture',source_namespace='test',source_key='1',identity_status='accepted',version='v1',
               claims=[Claim(id='c',kind='activity',text='Specialist procedure services',excerpt='Specialist procedure services',
                             source_url='https://fixture.example/services',observed_at=datetime.now(UTC),source_kind='first_party',attribution='accepted')])
    rows=support['performed'];assert g.accepted_support(e,rows)['Niche practitioner']
    e.version='v2';assert not g.accepted_support(e,rows)['Niche practitioner']
    e.version='v1';e.claims[0].excerpt='Different text';assert not g.accepted_support(e,rows)['Niche practitioner']


def test_descendant_walk_handles_cycles_without_crossing_unrelated_roles():
    g=graph();g.occupations['specialist']['narrower']=['specialist']
    assert g.family('specialist')=={'specialist'}


def test_shared_knowledge_is_not_a_practical_function():
    g=graph();g.library.bundle['skills'][0]['type']='knowledge'
    assert g.retrieve(profile(),[[1.,0.]],[[1.,0.]])[0]==[]


def test_a_more_specific_conflicting_task_blocks_weak_semantic_overlap():
    g=graph();g.payload['tasks']['performed']=[['task',.7,[.2]*4],['other-task',1.,[.2]*4]]
    assert g.retrieve(profile(),[[1.,0.]],[[1.,0.]])[0]==[]


def test_explicit_task_does_not_veto_strong_core_professional_evidence():
    g=graph()
    g.occupations['specialist']['skills'].append({'id':'other-task','essential':True})
    g.payload['skill_competition'][1]=0.
    g.by_skill['other-task']={'vague'}
    # The selected task isn't named in the employer's strong core service span.
    ids,paths,_=g.retrieve(profile(),[[1.,0.]],[[0.,1.]])
    assert ids==['performed']
    assert paths['performed']['Niche practitioner'][0]['path']['explicit_skill_alignment'] is None
    # This does not permit a weaker broad activity to pass the same gate.
    g.payload['tasks']['performed'][0][1]=.7
    assert g.retrieve(profile(),[[1.,0.]],[[0.,1.]])[0]==[]


def test_nearby_professional_scope_does_not_erase_strong_practical_evidence():
    g=graph();g.payload['activities']['performed']={'specialist':.46,'other':.9}
    # Strong specific work can support the profession even if another title is
    # the closest semantic match. Wrong low-scope work remains excluded.
    assert g.retrieve(profile(),[[1.,0.]],[[1.,0.]])[0]==['performed']


def test_explicit_niche_task_does_not_require_a_forced_occupation_mapping():
    g=graph();g.library.bundle['roles']=np.zeros((2,2))
    g.term_vectors=np.asarray([[1.,0.],[0.,1.],[0.,1.]])
    p=profile('Unmapped occupation')
    ids,support,resolved=g.retrieve(p,[[0.,0.]],[[1.,0.]],[1.,0.],np.zeros((1,5,2)))
    assert ids==['performed'] and not resolved
    assert support['performed']['Unmapped occupation'][0]['path']['relation']=='explicit_task'
    assert p.role_intents[0].raw_label=='Unmapped occupation'


def test_raw_knowledge_does_not_bypass_professional_context():
    g=graph();g.library.bundle['roles']=np.zeros((2,2))
    g.library.bundle['skills'][0]['type']='knowledge'
    g.term_vectors=np.asarray([[1.,0.],[0.,1.],[0.,1.]])
    assert g.retrieve(profile('Unmapped occupation'),[[0.,0.]],[[1.,0.]],[1.,0.],np.zeros((1,5,2)))[0]==[]
