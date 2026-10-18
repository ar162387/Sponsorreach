import importlib.util,json
from pathlib import Path
import pytest
from sponsor_match.intelligence import digest


@pytest.mark.parametrize('changed',['runs','sampling',None])
def test_interest_publication_requires_exact_review_inputs(tmp_path,changed):
    path=Path(__file__).resolve().parents[2]/'scripts/publish_operator_report.py'
    spec=importlib.util.spec_from_file_location('interest_publication_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    runs=[{'id':'fixture','profile':{'role':'unknown niche'}}];sampling={'version':'fixture'}
    (tmp_path/'ai-development-review.json').write_text(json.dumps({'runs_hash':digest(runs),'sampling_hash':digest(sampling)}))
    if changed=='runs':runs[0]['profile']['role']='edited niche'
    if changed=='sampling':sampling['version']='edited'
    (tmp_path/'runs.json').write_text(json.dumps(runs));(tmp_path/'sampling.json').write_text(json.dumps(sampling))
    if changed:
        with pytest.raises(ValueError,match='frozen inputs'):module.validate_interest_review(tmp_path)
    else:module.validate_interest_review(tmp_path)
