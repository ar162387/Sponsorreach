from datetime import UTC,datetime
from sponsor_match.models import Claim,Channel,Employer,Profile,Background,RoleIntent
from sponsor_match.intelligence import accepted,documents,merge_employers
from sponsor_match.ranking import rank,usable_channels
from sponsor_match.taxonomy import Taxonomy
from test_matching import employer,profile
from test_api import integration


def claim(text,kind='activity'):
    return Claim(id='provided:'+text,kind=kind,text=text,excerpt=text,source_kind='provided_csv',source_url='urn:sponsorreach:csv:artifact:record:field',attribution='accepted')


def test_explicit_csv_baseline_is_accepted_without_faking_a_website_check():
    c=claim('software development')
    assert accepted(c)
    assert c.observed_at is None and c.source_kind=='provided_csv'
    c.source_url='https://invented-source.example'
    assert not accepted(c)


def test_identity_only_company_is_indexed_but_has_no_professional_match(employer,profile):
    employer.claims=[];employer.matching_basis='provided_csv'
    docs=documents(employer,Taxonomy())
    assert len(docs)==1 and docs[0]['claim_ids']==[]
    assert rank(employer,profile,Taxonomy(),'snapshot') is None


def test_provided_address_is_a_route_without_deliverability_or_freshness_claims():
    e=Employer(id='id',name='Acme',source_namespace='test',source_key='1',channels=[Channel(kind='address',value='10 Example Street, London SW1A 1AA',attribution='accepted',source_kind='provided_csv')])
    assert len(usable_channels(e))==1


def test_multiple_supplied_job_boards_are_preserved():
    old=Employer(id='id',name='Acme',source_namespace='test',source_key='1')
    new=old.model_copy(deep=True)
    new.channels=[Channel(kind='job_board',value='https://indeed.com/cmp/acme',attribution='accepted',source_kind='provided_csv'),Channel(kind='job_board',value='https://totaljobs.com/company/acme',attribution='accepted',source_kind='provided_csv')]
    assert len(merge_employers(old,new).channels)==2


def test_raw_csv_restores_all_routes_and_splits_email_addresses():
    from sponsor_match.csv_baseline import recorded_channels
    channels=recorded_channels({'Email':'one@acme.example, two@acme.example','Extras':'https://indeed.com/cmp/acme https://totaljobs.com/company/acme'},'urn:sponsorreach:csv:a:1:',None)
    assert len(channels)==4
    assert {c.value for c in channels if c.kind=='email'}=={'one@acme.example','two@acme.example'}


def test_provided_role_history_matches_without_creating_open_vacancies(employer):
    employer.claims=[claim('HR Specialist, Office Manager','historical_role')]
    p=Profile(background=Background(subject='Human resources'),role_intents=[RoleIntent(raw_label='HR specialist',confirmed=True)],career_stage='graduate')
    result=rank(employer,p,Taxonomy(),'snapshot')
    assert result is not None and result.features['quality']==.4
    assert not result.features['verified_matching_vacancy']
    assert result.explanation['text'].startswith('Recorded role history')


def test_unknown_specialist_matches_explicit_activity_but_not_generic_sector(employer):
    p=Profile(background=Background(subject='Computing'),role_intents=[RoleIntent(raw_label='Cybersecurity analyst',confirmed=True)],career_stage='graduate')
    employer.claims=[claim('cybersecurity, network protection')]
    assert rank(employer,p,Taxonomy(),'snapshot') is not None
    employer.claims=[claim('retail, shops, general services')]
    assert rank(employer,p,Taxonomy(),'snapshot') is None


def test_authorized_csv_policy_persists_for_later_manual_imports(integration,tmp_path):
    import csv
    from uuid import uuid4
    from sponsor_match.ingest import import_csv
    from sponsor_match.csv_baseline import apply_baseline
    db,_,_=integration
    namespace='test:csv-baseline:'+uuid4().hex
    rationale='Accepted the York website. Rejected a same-name restaurant in Leeds; its burger menu belongs to a different company.'
    row={'Company Name':'Acme Baseline Services','Company UUID':uuid4().hex,'Source Record ID':'1','Indicative Tags':'cybersecurity','Field States':'{}','Email':'hello@acme.example','Address':'10 Example Street, York','Reasoning':rationale}
    path=tmp_path/'companies.csv'
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    assert import_csv(db,path,namespace)['accepted_claims']==0
    result=apply_baseline(db,path,namespace,tmp_path/'activation')
    assert result['counts']['onboarded']==1
    replay=import_csv(db,path,namespace)
    assert replay['baseline_activation']['counts']['onboarded']==1
    eid=str(db.one('select employer_id from sm.employer_source_keys where namespace=%s',(namespace,))['employer_id'])
    assert db.one('select count(*) n from sm.accepted_claims where employer_id=%s',(eid,))['n']==1
    assert db.one('select count(*) n from sm.search_documents where employer_id=%s',(eid,))['n']==1
    assert db.employer(eid).matching_basis=='provided_csv'
    contexts=db.rows("select payload from sm.observations where employer_id=%s and kind='csv_context:Reasoning'",(eid,))
    assert len(contexts)==1  # Import, activation and replay retain one immutable observation.
    assert contexts[0]['payload']['raw_value']==rationale
    assert contexts[0]['payload']['professional_claim'] is False
    raw=db.one('select payload from sm.source_records where artifact_id=%s and record_key=%s',(result['artifact_id'],'1'))
    assert raw['payload']['Reasoning']==rationale
    assert all('burger' not in c.text for c in db.employer(eid).claims)
    assert all('restaurant' not in r['content'] for r in db.rows('select content from sm.search_documents where employer_id=%s',(eid,)))
