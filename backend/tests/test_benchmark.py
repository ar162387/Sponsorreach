from sponsor_match.benchmark import prospect_profiles, percentile
from sponsor_match.models import Profile


def test_prospect_suite_covers_families_and_adversarial_inputs():
    cases=prospect_profiles()
    assert len(cases)==253
    assert len({c['id'] for c in cases})==253
    assert len({c['occupation_family'] for c in cases if c['occupation_family']!='adversarial'})==24
    for case in cases:
        profile=Profile.model_validate(case['profile'])
        assert profile.role_intents
        assert 'email' not in profile.search_text()
    multi=next(c for c in cases if c['id']=='adversarial:multiple_intents')
    assert len(multi['profile']['role_intents'])==3


def test_percentiles_report_empty_and_interpolated_values():
    assert percentile([], .95) is None
    assert percentile([10], .95)==10
    assert percentile([10,20],.5)==15


def test_stage_prefix_does_not_lose_supported_professional_concept():
    from sponsor_match.taxonomy import Taxonomy,Concept
    imported=Concept('ons:software','Software occupations',['Senior software engineer'],[],[],[],[])
    taxonomy=Taxonomy([*Taxonomy().concepts,imported])
    assert taxonomy.resolve('Senior software engineer').id=='bootstrap:software'
    assert taxonomy.resolve('Junior software engineer').id=='bootstrap:software'
