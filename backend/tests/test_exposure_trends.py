import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def trends():
    path=Path(__file__).resolve().parents[2]/'scripts/exposure_trends.py'
    spec=importlib.util.spec_from_file_location('exposure_trends_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_frequency_normalizes_by_tested_profiles_without_claiming_quality(trends):
    row={'new_appearances':10,'preview_appearances':2,'top10_appearances':5,'best_new_rank':2,'state':'reached'}
    assert trends.rates(row,100)['appearances_per_1000_profiles']==100
    assert trends.rates(row,200)['appearances_per_1000_profiles']==50
    assert trends.rates(row,100)['example_profile_id'] is None


@pytest.mark.parametrize('row,total',[
    ({'new_appearances':1,'preview_appearances':0,'top10_appearances':0,'state':'reached'},0),
    ({'new_appearances':1,'preview_appearances':2,'top10_appearances':0,'state':'reached'},10),
])
def test_invalid_exposure_counts_cannot_create_a_trend(trends,row,total):
    with pytest.raises(ValueError):trends.rates(row,total)


def test_zero_result_record_is_retained_and_missing_catalogue_is_not_a_regression(trends,monkeypatch):
    def load(folder):
        run={'run_id':folder,'ranking_version':'same','proposal_version':'same','model_version':'same','source_hash':'changed-'+folder,'snapshot':'same','normalization_policy_hash':'same','confirmed_profiles':10}
        ids=['zero','removed'] if folder=='first' else ['zero','added']
        rows=[{'employer_id':eid,'name':eid,'employer_version':'v'} for eid in ids]
        stats={eid:trends.rates({'new_appearances':0,'preview_appearances':0,'top10_appearances':0,'state':'insufficient'},10) for eid in ids}
        return run,rows,stats
    monkeypatch.setattr(trends,'load_run',load)
    summary,rows=trends.compare(['first','last']);by_id={r['employer_id']:r for r in rows}
    assert len(rows)==3 and by_id['zero']['change']=='unreached_in_both'
    assert by_id['removed']['change']=='removed_from_catalogue'
    assert by_id['added']['change']=='added_to_catalogue'
    assert summary['changed_version_dimensions']==['source_hash'] and not summary['relevance_accuracy_measured']
