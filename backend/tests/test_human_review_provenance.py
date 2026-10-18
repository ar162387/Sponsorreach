import copy,importlib.util,sys
from pathlib import Path
import pytest


@pytest.fixture
def review_tools(monkeypatch):
    scripts=Path(__file__).resolve().parents[2]/'scripts';monkeypatch.syspath_prepend(str(scripts))
    spec=importlib.util.spec_from_file_location('human_review_scoring_test',scripts/'evaluate_human_reviews.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def rows():
    return [{'id':'profile','profile':{'background':'fixture'},'versions':{'ranking':'version-a','prospect_model':'source-a','snapshot':'register-a'},'ranking':['a','b'],'results':[{'employer_id':eid,'employer_name':eid,'explanation':{'sources':[{'excerpt':'Source evidence'}]},'channels':[]} for eid in ['a','b']]}]


def test_human_metrics_never_turn_unreviewed_pairs_or_fields_into_verified_values(review_tools):
    data=rows();labels=review_tools.review_packet(data);labels[0]['label']='direct'
    result=review_tools.score_reviews(data,labels)
    assert result['judged_pairs']==1 and result['metrics']['precision_at3']['precision_at_k'] is None
    assert result['metrics']['precision_at3']['overall_judged_item_coverage']==.5
    assert result['explanation_support_rate'] is None and not result['recall_measured'] and not result['release_ready']
    labels[1]['label']='direct';labels[0]['explanation_supported']=True
    result=review_tools.score_reviews(data,labels)
    assert result['metrics']['precision_at3']['precision_at_k']==1.
    assert result['metrics']['precision_at3']['shortlists_below_k']==1
    assert result['explanation_reviews']==1 and result['explanation_support_rate']==1.


@pytest.mark.parametrize('change',['source','profile','version'])
def test_changed_sources_profiles_or_models_cannot_inherit_human_reviews(review_tools,change):
    data=rows();labels=review_tools.review_packet(data);labels[0]['label']='direct'
    if change=='source':data[0]['results'][0]['explanation']['sources'][0]['excerpt']='Changed evidence'
    if change=='profile':data[0]['profile']['background']='Different professional interests'
    if change=='version':data[0]['versions']['prospect_model']='source-b'
    with pytest.raises(ValueError,match='exact profile'):review_tools.score_reviews(data,labels)


def test_ai_labels_and_conflicting_exports_cannot_count_as_human_validation(review_tools):
    data=rows();labels=review_tools.review_packet(data);labels[0]['reviewer_type']='ai'
    with pytest.raises(ValueError,match='AI judgments'):review_tools.score_reviews(data,labels)
    labels=review_tools.review_packet(data);labels[0]['label']='direct';other=copy.deepcopy(labels[0]);other['label']='irrelevant'
    with pytest.raises(ValueError,match='adjudication'):review_tools.score_reviews(data,labels+[other])


def test_offline_packet_cannot_edit_the_context_while_retaining_its_old_signature(review_tools):
    data=rows();labels=review_tools.review_packet(data);labels[0]['label']='direct'
    labels[0]['profile']={'background':'Changed offline context'}
    with pytest.raises(ValueError,match='Offline review context changed'):review_tools.score_reviews(data,labels)
