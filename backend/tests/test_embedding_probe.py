import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def probe():
    path=Path(__file__).resolve().parents[2]/'scripts/embedding_model_probe.py'
    spec=importlib.util.spec_from_file_location('embedding_probe_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_auc_handles_ties_and_requires_both_classes(probe):
    rows=[{'label':'direct','score':.9},{'label':'direct','score':.5},{'label':'irrelevant','score':.5},{'label':'related','score':.1}]
    assert probe.auc(rows,'score')==.875
    assert probe.auc(rows[:2],'score') is None


def test_threshold_comes_only_from_older_pairs(probe):
    training=[{'label':'direct','score':.9},{'label':'direct','score':.7},{'label':'irrelevant','score':.8}]
    evaluation=[{'label':'direct','score':.1},{'label':'irrelevant','score':.99}]
    first=probe.calibration(training,evaluation,'score');assert first['threshold']==.7
    assert first['training']['direct_retention']==1
    assert first['newer_development_sample']['direct_retention']==0
    evaluation[0]['score']=.99;evaluation[1]['label']='direct'
    assert probe.calibration(training,evaluation,'score')['threshold']==first['threshold']
    assert not first['release_ready']


def test_calibration_never_claims_a_cutoff_from_one_class(probe):
    result=probe.calibration([{'label':'direct','score':1}],[],'score')
    assert result['threshold'] is None


def test_non_normalized_cached_vectors_fail_closed(probe,tmp_path):
    import numpy as np
    from sponsor_match.intelligence import digest
    encoder=probe.Encoder('minilm',tmp_path);texts=['Source evidence']
    np.savez_compressed(tmp_path/(digest([probe.VERSION,encoder.spec,texts])+'.npz'),vectors=np.full((1,384),2.))
    with pytest.raises(ValueError,match='cached vectors'):encoder.encode(texts)


@pytest.mark.parametrize('change',['manifest','version','features',None])
def test_publisher_binds_encoder_scores_to_exact_versions_and_pair_features(tmp_path,change):
    import json
    from sponsor_match.intelligence import digest
    path=Path(__file__).resolve().parents[2]/'scripts/publish_operator_report.py'
    spec=importlib.util.spec_from_file_location('encoder_publication_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest={'versions':{'ranking':'r','prospect_model':'m','snapshot':'s'}}
    pairs=[{'definition_similarity':.6}]
    summary={'manifest_hash':digest(manifest),'pair_output_hashes':{name:digest(pairs) for name in ['minilm','bge']}}
    if change=='manifest':manifest['changed']=True
    if change=='version':manifest['versions']['ranking']='other';summary['manifest_hash']=digest(manifest)
    if change=='features':pairs[0]['definition_similarity']=.99
    for name,value in [('manifest.json',manifest),('summary.json',summary),('minilm-pairs.json',pairs),('bge-pairs.json',pairs)]:
        (tmp_path/name).write_text(json.dumps(value))
    if change:
        with pytest.raises(ValueError):module.validate_encoder_probe(tmp_path,{'ranking_version':'r','model_version':'m'},{'snapshot':'s'})
    else:module.validate_encoder_probe(tmp_path,{'ranking_version':'r','model_version':'m'},{'snapshot':'s'})
