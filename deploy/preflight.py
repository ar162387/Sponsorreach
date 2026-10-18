"""Fail closed unless the published data and offline encoder work on the host."""
import json
import os
from pathlib import Path
import resource
import sys
import time

os.environ.update(json.loads(Path('/etc/sponsorreach/runtime.json').read_text()))
sys.path.insert(0, '/opt/sponsorreach/app/backend/src')
from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.intelligence import digest
from sponsor_match.onboarding import OnboardingLibrary, SuggestionContext
from sponsor_match.prospects import active_pointer, model_root
from sponsor_match.providers import embedding_provider

settings = Settings.from_env()
assert settings.environment == 'production' and settings.manual_catalogue_updates
assert settings.embedding_provider == 'local' and settings.require_verified_email
started = time.monotonic()
vectors = embedding_provider(settings).embeddings(['Software developer using Python', 'Waiter serving restaurant guests'])
assert len(vectors) == 2 and all(len(v) == 384 for v in vectors)
db = Database(settings.database_url)
db.open()
try:
    counts = db.one("select count(*) n from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv'")
    index = db.one('select id,model,dimensions from sm.search_index_versions where active')
    assert counts['n'] >= 7309 and index and index['model'] == settings.embedding_model and index['dimensions'] == 384
    assert db.active_snapshot(), 'Missing official sponsor snapshot'
    folder = model_root() / 'cdbd25ac18bbcbf97ddf07d6'
    manifest = json.loads((folder / 'manifest.json').read_text())
    current = {str(r['id']): r['version'] for r in db.rows("select id,version from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv'")}
    assert digest(current) == manifest['source_hash'], 'Published employer artifact does not match this database'
    pointer = active_pointer(settings)
    pointer.write_text(json.dumps({'version': manifest['version'], 'folder': str(folder)}))
    suggestions = OnboardingLibrary(settings)
    examples = {}
    for role in ['software developer', 'waiter', 'plumber']:
        response = suggestions.suggest(SuggestionContext(text=role, roles=[role]))
        assert response['skill_suggestions'], 'Missing source-backed suggestions: ' + role
        examples[role] = len(response['skill_suggestions'])
    print(json.dumps({'employers': counts['n'], 'active_index': str(index['id']), 'encoder': settings.embedding_model, 'skill_suggestion_counts': examples, 'seconds': round(time.monotonic() - started, 2), 'peak_rss_mib': round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))
finally:
    db.close()
