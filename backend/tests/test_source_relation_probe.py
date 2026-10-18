import importlib.util
from pathlib import Path
import pytest


@pytest.fixture
def validator():
    script=Path(__file__).resolve().parents[2]/'scripts/source_relation_probe.py'
    spec=importlib.util.spec_from_file_location('source_relation_validator_test',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.validate


def test_source_relation_requires_all_targets_and_exact_bounded_evidence(validator):
    source={'target_spans':['specialist work'],'source_excerpt':'Our team performs specialist work for clients.'}
    value={'spans':[{'text':'specialist work','relation':'performed_activity','support_quote':'Our team performs specialist work'}],'explicit_scope':[]}
    assert validator(value,source)==value
    value['spans'][0]['support_quote']='Our team performs specialist work...'
    with pytest.raises(ValueError,match='exact bounded'):validator(value,source)


@pytest.mark.parametrize('problem',['missing','duplicate','invented','wrong_quote','invented_scope','invalid_object'])
def test_bad_extractions_remain_invalid_instead_of_becoming_claims(validator,problem):
    source={'target_spans':['specialist work'],'source_excerpt':'Our team performs specialist work.'}
    span={'text':'specialist work','relation':'performed_activity','support_quote':'specialist work'}
    value={'spans':[span],'explicit_scope':[]}
    if problem=='missing':value['spans']=[]
    if problem=='duplicate':value['spans'].append(dict(span))
    if problem=='invented':span['text']='unobserved role'
    if problem=='wrong_quote':span['support_quote']='Our team'
    if problem=='invented_scope':value['explicit_scope']=[{'label':'scope','quote':'not in source'}]
    if problem=='invalid_object':value['spans']=['not an object']
    with pytest.raises(ValueError):validator(value,source)
