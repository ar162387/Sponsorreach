import importlib.util
from pathlib import Path
from sponsor_match.models import Profile


def test_official_review_sample_is_order_independent_and_never_infers_qualifications():
    path=Path(__file__).resolve().parents[2]/'scripts/discovery_review_matrix.py'
    spec=importlib.util.spec_from_file_location('discovery_review_matrix_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    references=[{'id':'soc:'+code,'label':'Unfamiliar role '+code,'description':'A task description. '*80,'aliases':['Alternate role '+code]} for code in ['111101','111102','222201']]
    rows,info=module.matrix(references,1)
    assert (rows,info)==module.matrix(list(reversed(references)),1)
    assert info['major_families']==2 and len(info['selected_references'])==2
    assert len(rows)==16 and info['human_judgments']==0 and not info['quality_accuracy_measured']
    for row in rows:
        profile=Profile.model_validate(row['profile'])
        assert not profile.skills and not profile.certifications and not row['candidate_qualification_claims']
        assert not profile.experience_summary or profile.experience_summary.startswith('Interested in work involving: ')
        assert row['provenance']['reference_id']==row['family']
    assert len({row['id'] for row in rows})==len(rows)
