import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from .models import Employer, Claim
from .taxonomy import Taxonomy, contains

TEMPLATE_VERSION = "facets-2"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def accepted(claim: Claim, at=None):
    at = at or datetime.now(UTC)
    if claim.attribution != "accepted" or claim.state != "found" or claim.source_kind == "historical_import":
        return False
    if claim.source_kind == 'provided_csv':
        # Explicitly operator-authorized baseline, not newly verified website evidence.
        return bool(claim.source_url.startswith('urn:sponsorreach:csv:') and claim.excerpt and claim.text in claim.excerpt and claim.kind in {'activity','historical_role'})
    if not claim.source_url or not claim.excerpt or not claim.observed_at:
        return False
    age = (at - claim.observed_at).total_seconds() / 86400
    return 0 <= age <= (365 if claim.kind == "historical_role" else 180)


def documents(employer: Employer, taxonomy: Taxonomy):
    grouped = defaultdict(list)
    for claim in employer.claims:
        if not accepted(claim) or claim.kind == "sponsorship_wording":
            continue
        facet = "activity" if claim.kind == "activity" else "function"
        concepts = taxonomy.inferred_concepts(claim.text, facet)
        bucket = concepts[0] if concepts else "unclassified"
        grouped[(facet, bucket)].append(claim)
    result = []
    for (facet, bucket), claims in sorted(grouped.items())[:8]:
        # Preserve specific professional language without importing audit prose/PII.
        content = "\n".join(dict.fromkeys(c.text for c in claims))[:2400]
        for channel in employer.channels:
            content=content.replace(channel.value,"")
        content=re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}","",content)
        content=re.sub(r"https?://\S+","",content)
        content=re.sub(r'\b(?:uk visa sponsor|visa sponsorship|skilled worker sponsor|certificate of sponsorship)\b','',content,flags=re.I)
        if not content.strip():
            continue
        result.append({"id": digest([employer.id, facet, bucket]), "employer_id": employer.id,
                       "facet": facet, "content": content, "claim_ids": [c.id for c in claims],
                       "content_hash": digest([content, TEMPLATE_VERSION, taxonomy.version]),
                       "template_version": TEMPLATE_VERSION, "taxonomy_version": taxonomy.version})
    if not result and employer.matching_basis=='provided_csv':
        content='Employer: '+employer.name+'\nLocation: '+employer.town
        result.append({'id':digest([employer.id,'identity']),'employer_id':employer.id,'facet':'activity','content':content,'claim_ids':[], 'content_hash':digest([content,'catalogue-identity-1',taxonomy.version]),'template_version':'catalogue-identity-1','taxonomy_version':taxonomy.version})
    return result


def merge_employers(old: Employer | None, new: Employer):
    if not old:
        return new
    if old.identity_status=="accepted" and new.identity_status=="unverified" and (old.source_namespace,old.source_key)!=(new.source_namespace,new.source_key):
        # Cross-source identity mappings are operator-reviewed. Preserve the
        # canonical register-facing identity when a legacy alias is replayed.
        new.name,new.town,new.county=old.name,old.town,old.county
        new.source_namespace,new.source_key=old.source_namespace,old.source_key
    if old.identity_status=="accepted" and new.identity_status=="unverified" and (old.name.casefold()!=new.name.casefold() or old.town.casefold()!=new.town.casefold() or (old.company_number and new.company_number and old.company_number!=new.company_number)):
        new.identity_status="quarantined"
    claims = {c.id: c for c in old.claims}
    for claim in new.claims:
        prior = claims.get(claim.id)
        if prior and prior.observed_at and (not claim.observed_at or prior.observed_at > claim.observed_at):
            continue
        if prior and prior.attribution == "accepted" and (claim.attribution == "unverified" or claim.state in {"temporarily_unavailable", "blocked", "inconclusive", "not_observed"}):
            continue
        if claim.state == "verified_absent" and claim.attribution == "accepted":
            claims = {k: c for k, c in claims.items() if c.kind != claim.kind or (c.observed_at and claim.observed_at and c.observed_at > claim.observed_at)}
        claims[claim.id] = claim
    channels = list(old.channels)
    replaced_kinds=set()
    for channel in new.channels:
        same = [c for c in old.channels if c.kind == channel.kind]
        if any(c.observed_at and (not channel.observed_at or c.observed_at > channel.observed_at) for c in same):
            continue
        if channel.state in {"temporarily_unavailable", "blocked", "inconclusive", "not_observed"}:
            continue
        if channel.attribution == "accepted" and channel.state in {"found", "verified_absent"} and channel.kind not in replaced_kinds:
            channels = [c for c in channels if c.kind != channel.kind]
            replaced_kinds.add(channel.kind)
        if channel.state == "found" and not any(c.kind == channel.kind and c.value == channel.value for c in channels):
            channels.append(channel)
    # Failure observations cannot revoke an accepted identity. Explicit quarantine can.
    if old.identity_status == "accepted" and new.identity_status == "unverified":
        new.identity_status = old.identity_status
    new.claims = list(claims.values())
    new.channels = channels
    new.memberships = new.memberships or old.memberships
    new.vacancies = new.vacancies or old.vacancies
    new.version = digest(new.model_dump(exclude={"version"}))
    return new
