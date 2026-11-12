"""Validate real web request construction against the API's strict schemas."""
import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sponsor_match.models import MatchRequest, ShortlistRefresh

WEB = Path(__file__).resolve().parents[2] / 'web'


def web_request(**overrides):
    options = {
        'profile': {'background': {'subject': 'Mechanical Engineering'},
                    'role_intents': [{'raw_label': 'Mechanical engineer', 'confirmed': False}],
                    'career_stage': 'graduate'},
        'visaContext': None, 'creditConsent': True,
        'idempotencyKey': str(uuid4()),
        **overrides,
    }
    script = """
const ts = require('typescript');
const fs = require('node:fs');
const m = {exports: {}};
const code = ts.transpileModule(fs.readFileSync('lib/search-request.ts', 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS}
}).outputText;
new Function('exports', code)(m.exports);
process.stdout.write(JSON.stringify(m.exports.searchRequest(JSON.parse(process.argv[1]))));
"""
    result = subprocess.run(['node', '-e', script, json.dumps(options)], cwd=WEB,
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('consent', [True, False])
def test_signed_in_new_search_matches_api_contract(consent):
    body = web_request(creditConsent=consent)
    assert 'accept_credit_cost' not in body
    assert 'identity' not in body
    parsed = MatchRequest.model_validate(body)
    assert parsed.profile.role_intents[0].confirmed
    # This was the exact field that made all form submissions fail with 422.
    with pytest.raises(ValidationError):
        MatchRequest.model_validate({**body, 'accept_credit_cost': consent})


def test_legacy_identity_and_optional_visa_are_preserved():
    body = web_request(identity={'name': 'Candidate', 'email': 'candidate@example.com'},
                       visaContext={'route': 'Graduate', 'expiry': '2027-11-05'})
    parsed = MatchRequest.model_validate(body)
    assert parsed.identity.email == 'candidate@example.com'
    assert parsed.visa_context.expiry == '2027-11-05'


@pytest.mark.parametrize('consent', [True, False])
def test_revised_search_keeps_credit_consent(consent):
    body = web_request(sourceSession='existing-shortlist', creditConsent=consent,
                       identity={'name': 'Ignored', 'email': 'ignored@example.com'})
    assert 'identity' not in body
    assert ShortlistRefresh.model_validate(body).accept_credit_cost is consent


from test_paid_access import paid, headers
from sponsor_match.billing import Credits


def test_new_account_web_submission_queues_and_delivers_results(paid):
    client, db, uid, profile, results = paid
    body = web_request(profile=profile.model_dump(mode='json'))
    response = client.post('/api/matches', json=body, headers=headers(uid))
    assert response.status_code == 202, response.text
    sid = response.json()['session_id']
    # Retrying the same browser submission must not create another search or charge.
    assert client.post('/api/matches', json=body, headers=headers(uid)).json()['session_id'] == sid
    assert Credits(db).summary(uid)['available'] == 4
    assert Credits(db).summary(uid)['reserved'] == 1
    db.save_results(sid, results, 'synthetic', {})
    response = client.get('/api/matches/' + sid, headers=headers(uid))
    assert response.status_code == 200
    assert response.json()['status'] == 'ready'
    assert response.json()['total_count'] > 0
    assert Credits(db).summary(uid)['available'] == 4
    assert Credits(db).summary(uid)['reserved'] == 0


def test_reported_software_background_manager_role_returns_actionable_clarification(paid):
    client,db,uid,_,results=paid
    Credits(db).ensure_signup(uid)
    profile={'profile_version':1,'background':{'subject':'software enginer','specialization':''},'role_intents':[{'raw_label':'manager','confirmed':True}],'explore':False,'career_stage':'graduate','skills':[{'label':'plumber','source':'user'},{'label':'software','source':'user'},{'label':'full stack','source':'user'}],'experience_summary':'','preferred_industries':[],'certifications':[],'location':{'preferred_regions':['birmingham'],'relocate':True,'strict':False},'related_roles_enabled':False}
    body=web_request(profile=profile)
    rejected=client.post('/api/matches',json=body,headers=headers(uid))
    assert rejected.status_code==422
    assert rejected.json()['detail']['code']=='profile_needs_clarification'
    assert 'manager' in rejected.json()['detail']['normalization']['clarification']
    assert Credits(db).summary(uid)['available']==5
    profile['role_intents'][0]['raw_label']='Software engineering manager'
    accepted=client.post('/api/matches',json=web_request(profile=profile),headers=headers(uid))
    assert accepted.status_code==202,accepted.text
    sid=accepted.json()['session_id'];db.save_results(sid,results[:20],'synthetic',{})
    assert client.get('/api/matches/'+sid,headers=headers(uid)).json()['status']=='ready'
    assert Credits(db).summary(uid)['available']==4
