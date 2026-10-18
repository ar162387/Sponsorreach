from copy import deepcopy
import math
import pytest
from sponsor_match.evaluation_lab import freeze, score, per_query, bootstrap_delta, agreement


def run(ids, pid='p', family='environment', **extra):
    return [{'id':pid,'family':family,'profile':{'background':{'subject':'Environmental engineering'}},
             'versions':{'ranking':'test'},'results':[{'employer_id':eid,'name':eid,'explanation':{'text':eid}} for eid in ids],**extra}]


def review(frozen, labels, kind='human', reviewer='reviewer-a'):
    return [{**p,'label':labels.get(p['employer_id'],'unjudged'),'reviewer_type':kind,'reviewer_id':reviewer} for p in frozen['packet']]


def test_hand_calculated_precision_ndcg_and_complete_pool():
    # One direct result, one irrelevant, one missing preview slot.
    r=per_query(['bad','good'],{'bad','good'},{'bad':'irrelevant','good':'direct'},3)
    assert r['precision_fixed_slots']==pytest.approx(1/3)
    assert r['precision_returned']==.5
    assert r['ndcg']==pytest.approx(1/math.log2(3))
    assert r['pool_recall_at_saved_depth']==1
    unjudged=per_query(['good'],{'good','new'},{'good':'direct'},3)
    assert unjudged['ndcg'] is None and unjudged['pool_recall_at_saved_depth'] is None
    assert unjudged['precision_fixed_slots']==pytest.approx(1/3)


def test_unjudged_results_have_bounds_not_false_negatives():
    r=per_query(['good','unknown','bad'],{'good','unknown','bad'},{'good':'direct','bad':'irrelevant'},3)
    assert r['precision_fixed_slots'] is None and r['precision_returned'] is None
    assert r['precision_lower_bound']==pytest.approx(1/3)
    assert r['precision_upper_bound']==pytest.approx(2/3)
    assert per_query([],set(),{},3)['precision_returned'] is None
    assert per_query([],set(),{},3)['ndcg'] is None


def test_task_specific_quality_is_distinct_from_broad_role_fit():
    labels={'broad':'direct','specific':'direct'}
    r=per_query(['broad','specific'],set(labels),labels,3,{'broad':'broad','specific':'specific'})
    assert r['precision_fixed_slots']==pytest.approx(2/3)
    assert r['task_precision_fixed_slots']==pytest.approx(1/3)
    assert r['ndcg']==1 and r['task_ndcg']<1
    assert per_query(['broad'],set(labels),labels,3,{})['task_precision_fixed_slots'] is None


def test_pooled_runs_comparison_and_failure_stage_are_explicit():
    f=freeze({'a':run(['bad','good'],retrieval_ids=['good','bad']),
              'b':run(['good','other'],retrieval_ids=['good','other'])})
    labels=review(f,{'good':'direct','bad':'irrelevant','other':'related'})
    result=score(f,labels)
    assert result['status']=='evaluated' and not result['release_ready']
    assert result['runs']['b']['metrics']['3']['precision_fixed_slots']['value']==pytest.approx(1/3)
    assert result['runs']['b']['metrics']['3']['ndcg']['value']>result['runs']['a']['metrics']['3']['ndcg']['value']
    assert result['comparisons'][0]['ci95'] is None  # One occupational cluster cannot supply a useful CI.
    assert len(f['packet'])==3


def test_automated_judgments_cannot_be_reported_as_human_accuracy():
    f=freeze({'a':run(['good'])});labels=review(f,{'good':'direct'},'ai_development')
    assert score(f,labels)['status']=='not_evaluated'
    ai=score(f,labels,'ai_development')
    assert ai['judged_pairs']==1 and ai['reviewer_type']=='ai_development' and not ai['release_ready']
    f=freeze({'a':run([])})
    empty=score(f,[])
    assert empty['runs']['a']['metrics']['3']['precision_fixed_slots']['value'] is None
    assert empty['runs']['a']['abstentions']==1


def test_stale_profiles_evidence_duplicates_and_reviews_fail_closed():
    other=run(['good']);other[0]['profile']['background']['subject']='Law'
    with pytest.raises(ValueError,match='changed its profile'):freeze({'a':run(['good']),'b':other})
    with pytest.raises(ValueError,match='same profiles'):freeze({'a':run(['good']),'b':run(['good'],pid='q')})
    with pytest.raises(ValueError,match='Duplicate employer'):freeze({'a':run(['good','good'])})
    f=freeze({'a':run(['good'])});r=review(f,{'good':'direct'})
    changed=deepcopy(f);changed['runs']['a'][0]['ranking']=[]
    with pytest.raises(ValueError,match='modified'):score(changed,r)
    stale=deepcopy(r);stale[0]['review_hash']='old'
    with pytest.raises(ValueError,match='Stale'):score(f,stale)
    conflict=deepcopy(r[0]);conflict['label']='irrelevant'
    with pytest.raises(ValueError,match='Conflicting'):score(f,r+[conflict])
    a=run(['good']);b=run(['good'])
    a[0]['versions']['snapshot']='old';b[0]['versions']['snapshot']='new'
    with pytest.raises(ValueError,match='source snapshot'):freeze({'a':a,'b':b})


def test_retrieval_miss_is_not_inferred_from_absence_in_final_ranking():
    f=freeze({'a':run(['bad']),'b':run(['good'])})
    result=score(f,review(f,{'good':'direct','bad':'irrelevant'}))
    assert result['diagnostics'][0]['failure']=='stage_not_instrumented'
    f=freeze({'a':run(['bad'],retrieval_ids=['bad']),'b':run(['good'])})
    assert score(f,review(f,{'good':'direct','bad':'irrelevant'}))['diagnostics'][0]['failure']=='retrieval_miss'


def test_family_slices_and_paired_bootstrap_are_reproducible():
    a=run(['bad'],'p','one')+run(['good'],'q','two')
    b=run(['good'],'p','one')+run(['good'],'q','two')
    f=freeze({'a':a,'b':b});r=score(f,review(f,{'good':'direct','bad':'irrelevant'}))
    assert set(r['runs']['a']['slices'])=={'one','two'}
    assert r['comparisons'][0]['profiles']==2 and r['comparisons'][0]['ci95'] is not None
    assert bootstrap_delta([('one',.2),('two',-.1)])==bootstrap_delta([('one',.2),('two',-.1)])


def test_independent_review_agreement_exports_conflicts():
    f=freeze({'a':run(['good','bad'])})
    a=review(f,{'good':'direct','bad':'irrelevant'},reviewer='a')
    b=review(f,{'good':'direct','bad':'related'},reviewer='b')
    r=agreement(f,a,b)
    assert r['pairs']==2 and r['agreement']==.5 and len(r['disagreements'])==1
    assert r['cohen_kappa']==pytest.approx(1/3)
    with pytest.raises(ValueError,match='distinct reviewer'):agreement(f,a,a)
