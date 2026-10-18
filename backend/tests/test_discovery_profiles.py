import gzip,json
import numpy as np
from sponsor_match.discovery_profiles import DiscoveryProfiles,interest_variants
from sponsor_match.intelligence import digest


def test_official_baseline_covers_the_resource_without_seeded_professions(tmp_path):
    references=[{'id':'soc:222201','label':'Unfamiliar professional niche'},{'id':'soc:111101','label':'Another professional family'},{'id':'soc:333301','label':'long '*40}]
    (tmp_path/'references.json').write_text(json.dumps(references))
    records,info=DiscoveryProfiles(tmp_path).official_baseline()
    assert [r['reference_id'] for r in records]==['soc:111101','soc:222201']
    assert info['overlong_titles_not_truncated']==['soc:333301']
    for record in records:
        p=record['profile']
        assert p.role_intents[0].confirmed and not p.skills and not p.certifications
        assert p.background.subject.startswith('Professional interest in ')


def test_project_variants_preserve_unknown_roles_and_trace_both_source_facets():
    group={'id':'observed-role:new','label':'Novel discipline specialist'}
    link={'kind':'role','span':'Novel discipline specialist','claim_id':'role-source'}
    activities=[{'span':'Instrument testing','claim_id':'testing-source'},{'span':'Measurement analysis','claim_id':'analysis-source'}]
    variants=list(interest_variants(group,link,activities))
    assert len({digest(v['profile'].model_dump(mode='json')) for v in variants})==len(variants)==7
    combined=next(v for v in variants if v['profile'].background.specialization=='Instrument testing' and 'Measurement analysis' in v['profile'].experience_summary)
    assert combined['evidence_ids']=={'role-source','testing-source','analysis-source'}
    for variant in variants:
        p=variant['profile']
        assert p.role_intents[0].raw_label=='Novel discipline specialist'
        assert not p.skills and not p.certifications and not p.related_roles_enabled
        assert not p.experience_summary or p.experience_summary.startswith('Interested in projects involving ')


def test_interest_variants_do_not_merge_distinct_technical_symbols():
    group={'id':'soc:111101','label':'Software specialist'}
    link={'kind':'activity','span':'C++','claim_id':'cpp-source'}
    variants=list(interest_variants(group,link,[{'span':'C','claim_id':'c-source'},{'span':'C++','claim_id':'cpp-source'}]))
    assert {v['profile'].background.specialization for v in variants}=={'','C','C++'}


def test_contexts_preserve_unmapped_niches_and_exclude_unrelated_or_named_text(tmp_path):
    (tmp_path/'references.json').write_text(json.dumps([{'id':'soc:111101','label':'Official family'}]))
    np.savez(tmp_path/'reference-vectors.npz',vectors=np.array([[1.,0.]],dtype=np.float32))
    ids=['task-a','task-b','unrelated','identity','unknown-role']
    vectors=np.array([[1.,0.],[.97,np.sqrt(1-.97**2)],[0.,1.],[1.,0.],[1.,0.]],dtype=np.float32)
    np.savez(tmp_path/'term-vectors.npz',vectors=vectors,term_ids=np.array(ids))
    observations=[{'employer_id':'employer-source','kind':'activity','text':span,'claim_id':'claim-'+tid,'term_id':tid} for tid,span in zip(ids,['Instrument testing','Measurement analysis','Unrelated commerce','Fixture Company services'])]
    with gzip.open(tmp_path/'corpus.json.gz','wt') as f:json.dump({'observations':observations},f)
    index=DiscoveryProfiles(tmp_path)
    link={'employer_id':'employer-source','kind':'role','group_id':'observed-role:new','term_id':'unknown-role'}
    group={'id':'observed-role:new','label':'New niche','reference_id':None}
    contexts=index.contexts_for('Fixture Company',link,group)
    assert [r['span'] for r in contexts]==['Instrument testing','Measurement analysis']
    assert all(r['claim_id'].startswith('claim-') for r in contexts)
