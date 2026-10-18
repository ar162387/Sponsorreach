import importlib.util
from pathlib import Path
import pytest
from sponsor_match.intelligence import digest


def test_gap_audit_rejects_changed_helpers_and_tampered_frozen_code(tmp_path):
    script=Path(__file__).resolve().parents[2]/'scripts/coverage_gap_audit.py'
    spec=importlib.util.spec_from_file_location('coverage_gap_integrity_test',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    frozen=tmp_path/'frozen';current=tmp_path/'current';frozen.mkdir();current.mkdir()
    sources={'semantic_search.py':'matcher version','helper.py':'evidence helper'}
    for name,text in sources.items():
        (frozen/('frozen-'+name)).write_text(text);(current/name).write_text(text)
    metadata={'ranking_source_hash':digest(sources)}
    module.verify_ranking_sources(frozen,metadata,current)
    (current/'helper.py').write_text('changed eligibility helper')
    with pytest.raises(ValueError,match='Matching code changed'):module.verify_ranking_sources(frozen,metadata,current)
    (current/'helper.py').write_text(sources['helper.py'])
    (frozen/'frozen-helper.py').write_text('tampered artifact')
    with pytest.raises(ValueError,match='integrity failed'):module.verify_ranking_sources(frozen,metadata,current)
