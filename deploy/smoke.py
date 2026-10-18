"""Production smoke check with synthetic professional text; no emails or accounts."""
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

runtime = json.loads(Path('/etc/sponsorreach/runtime.json').read_text())
os.environ.update(runtime)
sys.path.insert(0, '/opt/sponsorreach/app/backend/src')

def get(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        assert response.status == 200
        return response.read()

assert b'SponsorReach' in get('http://127.0.0.1:3000/match')
get('http://127.0.0.1:8001/health')
body = json.dumps({'text': 'Computer science graduate interested in software development with Python', 'roles': ['software developer'], 'skills': []}).encode()
started = time.monotonic()
request = urllib.request.Request('http://127.0.0.1:8001/api/profiles/suggestions', data=body, headers={'Content-Type': 'application/json', 'X-API-Secret': runtime['SPONSORMATCH_API_SECRET']})
with urllib.request.urlopen(request, timeout=180) as response:
    ideas = json.load(response)
assert ideas.get('skill_suggestions'), 'No personalized skill choices'
print(json.dumps({'suggestions': len(ideas['skill_suggestions']), 'suggestion_seconds': round(time.monotonic() - started, 2)}), flush=True)

from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.models import Profile
import secrets
from uuid import uuid4

db = Database(runtime['DATABASE_URL'])
db.open()
try:
    profile = Profile.model_validate({'background': {'subject': 'Computer science', 'specialization': 'Software development'}, 'role_intents': [{'raw_label': 'software developer', 'confirmed': True}], 'career_stage': 'graduate', 'skills': [{'label': 'Python'}, {'label': 'SQL'}], 'experience_summary': 'Built and tested a database-backed web application.', 'location': {'preferred_regions': ['London'], 'relocate': True}, 'preferred_industries': ['Software'], 'related_roles_enabled': False})
    if len(sys.argv) > 1:
        profile.experience_summary += ' ' + sys.argv[1]
    started = time.monotonic()
    owner = secrets.token_urlsafe(40)
    payload = {'profile': profile.model_dump(), 'identity': {'name': 'Deployment smoke check', 'email': 'deployment-check@example.invalid'}, 'idempotency_key': 'deployment-' + uuid4().hex}
    headers = {'Content-Type': 'application/json', 'X-API-Secret': runtime['SPONSORMATCH_API_SECRET'], 'X-Session-Token': owner}
    request = urllib.request.Request('http://127.0.0.1:8001/api/matches', data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        session_id = json.load(response)['session_id']
    deadline = time.monotonic() + 180
    while True:
        row = db.one("select status,retrieval_mode,versions,profile_id,error_code from sm_private.match_sessions where id=%s", (session_id,))
        if row['status'] in {'ready', 'failed'}: break
        if time.monotonic() > deadline: raise TimeoutError('Deployment match remained queued/processing')
        time.sleep(2)
    assert row['status'] == 'ready', 'Worker failed: ' + str(row['error_code'])
    assert row['retrieval_mode'] == 'hybrid', 'Embedding retrieval did not run'
    count = db.one("select count(*) n from sm_private.match_results where session_id=%s", (session_id,))['n']
    assert count, 'Expected supported software employers in the published catalogue'
    request = urllib.request.Request('http://127.0.0.1:8001/api/matches/' + session_id, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response: public = json.load(response)
    assert public['verification_required'] and 'preview' not in public, 'Email gate leaked results'
    print(json.dumps({'matches': count, 'mode': row['retrieval_mode'], 'match_seconds': round(time.monotonic() - started, 2), 'ranking': row['versions']['ranking'], 'email_gate': 'passed'}), flush=True)
    # Remove only the exact successful synthetic session created by this script.
    with db.transaction() as connection:
        connection.execute("delete from sm.work_items where dedupe_key=%s", ('match:' + session_id,))
        connection.execute("delete from sm_private.match_sessions where id=%s", (session_id,))
        connection.execute("delete from sm_private.candidate_profiles where id=%s", (row['profile_id'],))
finally:
    db.close()
