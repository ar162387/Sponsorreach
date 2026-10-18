from sponsor_match.catalogue_cache import CatalogueCache
from test_api import integration
from test_matching import employer


def test_cache_requires_exact_version_and_isolates_database(monkeypatch,tmp_path):
    monkeypatch.setenv('SPONSORMATCH_CATALOGUE_CACHE',str(tmp_path/'cache.sqlite3'))
    cache=CatalogueCache('postgresql://localhost/first')
    cache.put_many('employer',{'e':('v1',{'id':'e','name':'Old'})})
    assert cache.get_many('employer',{'e':'v1'})['e']['name']=='Old'
    assert cache.get_many('employer',{'e':'v2'})=={}
    assert CatalogueCache('postgresql://localhost/other').get_many('employer',{'e':'v1'})=={}
    cache.put_many('employer',{'e':('v2',{'id':'e','name':'New'})})
    assert cache.get_many('employer',{'e':'v1'})=={}
    assert cache.get_many('employer',{'e':'v2'})['e']['name']=='New'


def test_cache_failure_falls_back_without_breaking_database_access(monkeypatch,tmp_path):
    path=tmp_path/'file';path.write_text('not a directory')
    monkeypatch.setenv('SPONSORMATCH_CATALOGUE_CACHE',str(path/'cache'))
    cache=CatalogueCache('postgresql://localhost/test')
    cache.put_many('employer',{'e':('v1',{})})
    assert cache.get_many('employer',{'e':'v1'})=={}


def test_employer_cache_checks_current_database_version_and_missing_header(integration,employer,monkeypatch):
    from uuid import uuid4
    db,_,_=integration
    e=employer.model_copy(deep=True);e.id=str(uuid4());e.source_key=e.id
    for c in e.claims:c.id=e.id+':'+c.id
    saved=db.save_employer(e)
    assert db.employers([e.id])[0].name=='Acme'
    changed=saved.model_copy(deep=True);changed.name='Updated employer'
    db.save_employer(changed)
    assert db.employers([e.id])[0].name=='Updated employer'
    original=db.rows
    monkeypatch.setattr(db,'rows',lambda sql,params=(): [] if sql.startswith('select id,version from sm.employers') else original(sql,params))
    assert db.employers([e.id])==[]
