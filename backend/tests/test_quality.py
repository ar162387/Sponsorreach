import csv
import gzip
import json
import os
from uuid import uuid4
import pytest
from sponsor_match.quality import assess_row,channel_shape,raw_archive
from sponsor_match.db import Database
from sponsor_match.ingest import import_csv,artifact
from sponsor_match.models import Employer
from sponsor_match.catalogue_cleanup import cleanup_catalogue
from psycopg.types.json import Jsonb

@pytest.mark.parametrize('fields,status',[
    ({},'archive_no_recorded_route'),
    ({'Website':'null','Email':'N/A'},'archive_no_recorded_route'),
    ({'Email':'hello@company.example'},'potential_digital_route'),
    ({'Website':'https://company.example?utm_source=abc'},'potential_digital_route'),
    ({'Address':'12 High Street'},'postal_only_review'),
    ({'Website':'https://google.com/search?q=company'},'review_unusable_or_ambiguous_channels'),
    ({'LinkedIn':'https://www.linkedin.com/in/person'},'review_unusable_or_ambiguous_channels'),
    ({'Email':'ask reception'},'review_unusable_or_ambiguous_channels'),
])
def test_partial_information_is_not_deleted(fields,status):
    assert assess_row(fields)['status']==status


def test_channels_and_immutable_archive(tmp_path):
    assert not channel_shape('linkedin_company','https://linkedin.com/company/')
    assert channel_shape('linkedin_company','https://linkedin.com/company/acme')
    path=tmp_path/'archive.json.gz'
    sha=raw_archive([{'value':'original'}],path)
    assert sha==raw_archive([{'value':'original'}],path)
    assert json.load(gzip.open(path,'rt'))==[{'value':'original'}]
    with pytest.raises(ValueError):raw_archive([{'value':'changed'}],path)

@pytest.fixture
def db():
    if not os.getenv('TEST_DATABASE_URL'):pytest.skip('Dedicated test database required')
    db=Database(os.environ['TEST_DATABASE_URL']);db.open();db.migrate()
    try:yield db
    finally:db.close()


def write_csv(path,email=''):
    row={'Company Name':'Cleanup Test','Company UUID':'source-uuid','Source Record ID':'1','Indicative Tags':'engineering','Field States':'{}','Email':email}
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
    return row


def test_import_archive_replay_and_later_restore(db,tmp_path):
    ns='quality:'+str(uuid4());path=tmp_path/'batch.csv';write_csv(path)
    assert import_csv(db,path,ns)['archived_no_route']==1
    original=str(db.one('select employer_id from sm.import_dispositions where namespace=%s',(ns,))['employer_id'])
    assert not db.employer(original)
    import_csv(db,path,ns)
    assert str(db.one('select employer_id from sm.import_dispositions where namespace=%s',(ns,))['employer_id'])==original
    write_csv(path,'hello@company.example')
    assert import_csv(db,path,ns)['imported']==1
    assert db.employer(original).channels[0].value=='hello@company.example'
    assert db.one('select status from sm.import_dispositions where namespace=%s',(ns,))['status']=='restored'
    write_csv(path)
    import_csv(db,path,ns)
    assert db.employer(original).channels[0].value=='hello@company.example'


def test_existing_cleanup_is_backed_up_and_replayable(db,tmp_path):
    ns='cleanup:'+str(uuid4());path=tmp_path/'batch.csv';row=write_csv(path)
    aid=artifact(db,path,'historical_csv',ns)
    employer=Employer(id=str(uuid4()),name='Cleanup Test',source_namespace=ns,source_key='1')
    db.save_employer(employer,db.taxonomy())
    db.execute('insert into sm.source_records values(%s,%s,%s)',(aid,'1',Jsonb(row)))
    report=cleanup_catalogue(db,path,ns,tmp_path/'output')
    assert report['archived_from_database']==1
    assert not db.employer(employer.id)
    with gzip.open(report['archive_path'],'rt') as f:backup=json.load(f)
    assert backup['tables']['employers'][0]['id']==employer.id
    assert cleanup_catalogue(db,path,ns,tmp_path/'output')['archived_from_database']==0
    import_csv(db,path,ns)
    assert not db.employer(employer.id)
    write_csv(path,'hello@company.example');import_csv(db,path,ns)
    assert db.employer(employer.id)
    write_csv(path)
    with pytest.raises(ValueError,match='contact information'):
        cleanup_catalogue(db,path,ns,tmp_path/'output')
    assert db.employer(employer.id)


def test_explicit_publication_transaction_still_rolls_back(db):
    cache_key='rollback-check:'+str(uuid4())
    with pytest.raises(RuntimeError):
        with db.transaction() as connection:
            connection.execute("insert into sm.query_cache values(%s,'{}'::jsonb,now()+interval '1 minute')",(cache_key,))
            raise RuntimeError('Simulated partial publication failure')
    assert db.one('select 1 from sm.query_cache where cache_key=%s',(cache_key,)) is None
