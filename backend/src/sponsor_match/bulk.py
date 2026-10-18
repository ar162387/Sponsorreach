"""Replayable full-catalogue preparation; source checks are not human labels."""
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from .intelligence import digest
from .pool import STOP
from .taxonomy import contains, key
from .evidence import quote_valid, review_source

POLICY = 'source-corroboration-1'


def assess_draft(draft, taxonomy):
    """Require a distinctive full name and a verbatim professional service span.

    Recruitment advertising/client lists and teaching exchanges cannot establish
    the advertised profession as the employer's own core service.
    """
    if draft.get('status') != 'prepared':
        return [], draft.get('status', 'not_prepared')
    source = draft.get('source_text', '')
    words = [w for w in key(draft['name']).split() if w not in STOP]
    distinctive = ' '.join(words)
    if not distinctive or not contains(source, distinctive):
        return [], 'distinctive_full_name_not_confirmed'
    if not any(len(w) >= 4 and w not in {'care', 'design', 'digital', 'accountants', 'accountancy', 'consulting', 'consultancy', 'partners', 'restaurant', 'school', 'nursing'} for w in words):
        return [], 'generic_identity_requires_review'
    requested = urlparse(draft['requested_url']).hostname or ''
    resolved = urlparse(draft.get('resolved_url', '')).hostname or ''
    if requested.removeprefix('www.') != resolved.removeprefix('www.'):
        return [], 'changed_host_requires_identity_review'
    recruitment = bool(re.search(r'\b(?:recruitment (?:agency|partner|consultancy|specialist)|staffing (?:agency|solutions)|recruiting (?:agency|partner))', source, re.I))
    excluded = re.compile(r'\b(?:vacanc\w*|apply|hiring|job alerts?|job seekers?|seek talented|join our|careers|news|insights?|blog|subscribe|newsletter|webinar|articles?|tips for|guide to|our clients include|client testimonial|case stud\w*|recruitment partner|volunteer\w*|internship\w*|exchange program\w*|website by|website design by|manager|executive)\b|I[’\x27]ve had|Working with .+ was|\.\.\.', re.I)
    claims = []
    for item in draft.get('claims', []):
        if item.get('kind') != 'activity' or not quote_valid(item.get('text', ''), item.get('excerpt', ''), source):
            continue
        if excluded.search(item['excerpt']):
            continue
        concepts = set(taxonomy.inferred_concepts(item['text'], 'activity'))
        if not concepts:
            continue
        # Agencies' client professions don't establish those professions internally.
        if recruitment and not concepts <= {'bootstrap:recruitment', 'bootstrap:hr'}:
            continue
        if 'bootstrap:accounting' in concepts and re.search(r'\b(?:business app|accounting software|bookkeeping software)\b', item['excerpt'], re.I):
            continue
        if 'bootstrap:hospitality' in concepts and re.search(r'\b(?:restaurant management|restaurant and pub (?:customers|costumers)|restaurant clients|for restaurants|wholesale|supplying restaurants|catering products|catering equipment|catering supplies)\b', item['excerpt'], re.I):
            continue
        if 'bootstrap:marketing' in concepts and re.search(r'\b(?:marketing services industry|marketing industry clients)\b',item['excerpt'],re.I):
            continue
        if 'bootstrap:education' in concepts:
            if not re.search(r'\b(?:school|academy|college|university)\b', draft['name'], re.I):
                continue
            if re.search(r'\b(?:exchange|volunteer|internship|recruitment)\b', source, re.I):
                continue
            if not re.search(r'\b(?:our school|our pupils|our students|headteacher|curriculum|ofsted)\b', source, re.I):
                continue
        claims.append(item)
    return claims, 'source_corroborated' if claims else 'professional_context_requires_review'


def publish_prepared(db, folder, namespace='local:nocodb:company-enrichment-v2'):
    """Apply only new, deterministic corroborations to a staging database.

    The operator can inspect the manifest, reproduce it, and transfer its new
    public employer rows to the live database. Existing accepted evidence stays.
    """
    folder = Path(folder)
    taxonomy = db.taxonomy()
    outcomes = []
    manifest_path = folder / 'approved.json'
    approved = json.loads(manifest_path.read_text()).get('employers', []) if manifest_path.exists() else []
    for item in approved:
        if digest(json.loads((folder / item['source_file']).read_text())) != item['source_sha256']:
            raise ValueError('Existing preparation manifest changed')
    rows = db.rows('select e.id,e.name,e.payload from sm.employers e join sm.employer_source_keys k on k.employer_id=e.id where k.namespace=%s and not e.is_demo order by e.id', (namespace,))
    hosts=Counter((urlparse(c['value']).hostname or '').removeprefix('www.') for row in rows for c in row['payload'].get('channels',[]) if c['kind']=='website')
    identities=Counter((key(row['name']),key(row['payload'].get('town',''))) for row in rows)
    for row in rows:
        eid = str(row['id'])
        employer = db.employer(eid)
        if any(c.attribution == 'accepted' for c in employer.claims):
            outcomes.append({'employer_id': eid, 'name': row['name'], 'status': 'previously_prepared'})
            continue
        path = folder / (eid + '.json')
        if not path.exists():
            activity=' '.join(c.text for c in employer.claims if c.kind=='activity')
            websites=[c for c in employer.channels if c.kind=='website' and c.state=='found']
            if not activity.strip():status='no_professional_descriptor'
            elif not taxonomy.inferred_concepts(activity,'activity'):status='no_reviewed_activity_mapping'
            elif not websites:status='no_recorded_first_party_website'
            elif identities[(key(row['name']),key(employer.town))]>1:status='ambiguous_name_town_identity'
            elif all(hosts[(urlparse(c.value).hostname or '').removeprefix('www.')]>1 for c in websites):status='shared_domain_requires_review'
            else:status='no_unambiguous_current_sponsor_link'
            outcomes.append({'employer_id': eid, 'name': row['name'], 'status': status})
            continue
        draft = json.loads(path.read_text())
        claims, status = assess_draft(draft, taxonomy)
        if claims:
            result = review_source(db, eid, draft['requested_url'], draft['source_text'], claims, identity_confirmed=True)
            draft.update(claims=claims, review_status='accepted', acceptance_method='deterministic_source_corroboration', acceptance_policy=POLICY)
            # Explicitly machine-checked, never described as human-reviewed.
            accepted_path = folder / (eid + '.accepted.json')
            accepted_path.write_text(json.dumps(draft, indent=2) + '\n')
            approved.append({'employer_id': eid, 'source_file': accepted_path.name, 'source_sha256': digest(draft)})
            status = 'source_corroborated' if result['accepted_claims'] else 'no_accepted_claims'
        outcomes.append({'employer_id': eid, 'name': row['name'], 'status': status})
    report = {'policy': POLICY, 'created_at': datetime.now(UTC).isoformat(), 'catalogue_employers': len(rows), 'statuses': dict(Counter(r['status'] for r in outcomes)), 'outcomes': outcomes}
    (folder / 'catalogue-outcomes.json').write_text(json.dumps(report, indent=2) + '\n')
    manifest = {'policy': POLICY, 'acceptance_method': 'deterministic_source_corroboration', 'employers': approved}
    (folder / 'approved.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {k: v for k, v in report.items() if k != 'outcomes'}
