from datetime import datetime, UTC
from urllib.parse import urlparse
from dataclasses import dataclass
import re
from .models import Employer, Profile
from .taxonomy import Taxonomy, contains, key
from .intelligence import accepted
from .intelligence import digest
from .quality import channel_shape

RANKING_VERSION = "evidence-11-general-role-context"
QUALITY = {"first_party": 1.0, "ats": .85, "third_party": .65, "historical_import": .40, "provided_csv": .40, "demo": 1.0}


def activity_phrases(intent,target):
    if target and target.activities:
        return target.activities
    # Preserve explicit niches outside the bootstrap families. Profession suffixes
    # aren't business sectors; a specific subject must remain in the supplied tags.
    tokens=key(intent.raw_label).split()
    if tokens and tokens[-1] in {'manager','managers','director','directors','supervisor','supervisors'}:
        return [intent.raw_label]
    suffixes={'senior','junior','graduate','trainee','entry','level','engineer','engineers','analyst','analysts','developer','developers','manager','managers','officer','officers','specialist','specialists','consultant','consultants','assistant','assistants','associate','scientist','scientists','researcher','researchers','technician','technicians'}
    subject=[t for t in tokens if t not in suffixes]
    generic={'business','financial','finance','management','operations','administration','administrative','legal','human','resources','professional','general','technical','sales','research','services','retail'}
    if not subject or all(t in generic for t in subject):return [intent.raw_label]
    if len(subject)==1 and len(subject[0])<5:return [intent.raw_label]
    return [intent.raw_label,' '.join(subject)]


def role_segments(claim):
    # Separate recorded roles must not share skill/seniority credit.
    return [s.strip() for s in re.split(r"[,;\n]", claim.text) if s.strip()] if claim.kind in {'function','historical_role'} or claim.source_kind=='provided_csv' else [claim.text]


def supporting_spans(claim, intent, target, taxonomy):
    phrases = activity_phrases(intent,target) if claim.kind=='activity' else ([target.label,*target.aliases] if target else [intent.raw_label])
    if target and target.metadata.get('authority')=='ONS' and claim.kind!='activity':
        # A classification group can contain several occupations; sharing its
        # code does not make every coding-index title an occupational synonym.
        phrases=[intent.raw_label]
    spans=[]
    for span in role_segments(claim):
        matches=[p for p in phrases if contains(span,p)]
        if not matches:continue
        if claim.kind=='activity' and all(re.search(r'\b'+re.escape(key(p))+r"[s ]*(?:merchant|supplies|supplier|equipment|training|education)\b",key(span)) for p in matches):continue
        if claim.kind!='activity':
            # Longer recognized occupations override shared head nouns.
            observed=taxonomy.resolve(span)
            if not observed:
                tokens=key(span).split(); candidates=[]
                for start in range(len(tokens)):
                    for length in range(2,min(8,len(tokens)-start)+1):
                        found=taxonomy.resolve(' '.join(tokens[start:start+length]))
                        if found:candidates.append((length,found))
                if candidates:observed=max(candidates,key=lambda item:item[0])[1]
            matched=[p for p in phrases if contains(span,p)]
            if not observed and matched and all(key(p).endswith('ing') for p in matched):continue
            if observed and target and observed.id!=target.id:
                parent=observed.metadata.get('four_digit_parent')
                shared={key(p) for p in [target.label,*target.aliases]} & {key(p) for p in [observed.label,*observed.aliases]}
                if not shared and (not parent or parent!=target.metadata.get('four_digit_parent')):continue
        spans.append(span)
    return spans


def distinctive_modifiers(intent,target,taxonomy):
    if not target:return []
    raw=key(intent.raw_label).split();canonical=set(key(target.label).split())
    if len(raw)<2 or not canonical.intersection(raw):return []
    frequency=getattr(taxonomy,'token_frequency',{})
    words=key(target.label).split()
    acronyms={''.join(w[0] for w in words[start:end]) for start in range(len(words)) for end in range(start+2,len(words)+1)}
    ordinary={'senior','junior','graduate','trainee','registered','qualified','entry','level','staff'}
    return [w for w in raw if w not in canonical and w not in ordinary and w not in acronyms and frequency.get(w,0)<min(20,max(2,len(taxonomy.concepts)//100))]


def interleave_intents(results,intents,limit):
    ordered=sorted(results,key=lambda r:(-r.score,r.employer_id))
    if len(intents)<2:return ordered[:limit]
    buckets=[[r for r in ordered if r.features['intent']==i.raw_label] for i in intents]
    output=[];seen=set()
    while any(buckets) and len(output)<limit:
        for bucket in buckets:
            while bucket and bucket[0].employer_id in seen:bucket.pop(0)
            if bucket and len(output)<limit:
                result=bucket.pop(0);seen.add(result.employer_id);output.append(result)
    return output


def sponsor_valid(employer, active_snapshot, at=None):
    at = at or datetime.now(UTC)
    for m in employer.memberships:
        if m.snapshot_id != active_snapshot or m.attribution != "accepted" or m.route.casefold() != "skilled worker":
            continue
        rating = key(m.rating)
        if not ("a rating" in rating or "a premium" in rating or "a sme" in rating) or "b rating" in rating:
            continue
        try:
            age = (at.date() - datetime.fromisoformat(m.snapshot_date).date()).days
        except ValueError:
            continue
        if 0 <= age <= 7:
            return True
    return False


def usable_channels(employer, at=None):
    at = at or datetime.now(UTC)
    result = []
    for c in employer.channels:
        if c.attribution != "accepted" or c.state != "found" or c.kind in {"search_page", "linkedin_person"} or not c.value:
            continue
        if c.source_kind!='provided_csv' and (not c.observed_at or not 0 <= (at - c.observed_at).total_seconds() / 86400 <= 90):
            continue
        if not employer.is_demo and not channel_shape(c.kind,c.value):continue
        if c.kind not in {"email", "phone", "address"} and urlparse(c.value).scheme not in {"http", "https"}:
            continue
        result.append(c)
    return result


def open_jobs(employer, at=None):
    at = at or datetime.now(UTC)
    return [v for v in employer.vacancies if v.verified and v.state == "open" and v.country.casefold() in {"gb", "uk", "united kingdom"} and v.provider != "llm_adjudicated" and v.observed_at and 0 <= (at-v.observed_at).total_seconds() <= 72*3600 and (not v.closing_at or v.closing_at > at) and v.url not in {c.value for c in employer.channels if c.kind in {"website", "careers"}}]


@dataclass
class Ranked:
    employer_id: str
    group: str
    score: float
    features: dict
    explanation: dict
    employer_version: str


def rank(employer: Employer, profile: Profile, taxonomy: Taxonomy, active_snapshot: str, semantic=0., at=None):
    at = at or datetime.now(UTC)
    channels = usable_channels(employer, at)
    if employer.identity_status != "accepted" or not channels or not sponsor_valid(employer, active_snapshot, at):
        return None
    if profile.location.strict and employer.workplace_locations and not profile.location.relocate and profile.location.preferred_regions and not any(contains(loc, p) for loc in employer.workplace_locations for p in profile.location.preferred_regions):
        return None
    claims = [c for c in employer.claims if accepted(c, at)]
    best = None
    for intent in profile.role_intents:
        intent_semantic=semantic.get(intent.raw_label,0.) if isinstance(semantic,dict) else semantic
        concept = taxonomy.resolve(intent.raw_label)
        targets = [(concept, "direct")] if concept else []
        if concept and profile.related_roles_enabled:
            targets += [(taxonomy.by_id[r], "related") for r in concept.related if r in taxonomy.by_id]
        if not concept:
            # A niche title can match explicit professional text without a forced taxonomy mapping.
            targets = [(None, "direct")]
        for target, group in targets:
            supported = []; spans_by_id={}
            modifiers=distinctive_modifiers(intent,target,taxonomy) if group=='direct' else []
            for c in claims:
                if c.kind not in {'activity','function','historical_role'}:continue
                spans=supporting_spans(c,intent,target,taxonomy)
                if modifiers:
                    context=[w for w in key(profile.background.specialization).split() if len(w)>4 and taxonomy.token_frequency.get(w,0)<10]
                    spans=[span for span in spans if all(contains(span,w) for w in modifiers) or any(contains(span,w) for w in context)]
                if spans:supported.append(c);spans_by_id[c.id]=spans
            if not supported:continue
            roles = 1. if any(c.kind in {"function", "historical_role"} for c in supported) else .8
            # Skills are only matched to source text, not assumed from an occupation.
            explicit = list({key(s):s for s in [s.label for s in profile.skills] + profile.certifications}.values())
            skill_hits = [s for s in explicit if any(contains(span, s) for c in supported for span in spans_by_id[c.id])]
            task = min(1.,len(skill_hits)/3.)
            prefs = .5
            if employer.workplace_locations and profile.location.preferred_regions:
                prefs = float(any(contains(loc, p) for loc in employer.workplace_locations for p in profile.location.preferred_regions))
            preference_signals=[prefs]
            if profile.preferred_industries:
                preference_signals.append(1. if any(contains(c.text,p) for c in claims if c.kind=="activity" for p in profile.preferred_industries) else .5)
            if profile.career_stage in {"student","graduate"}:
                preference_signals.append(1. if any(contains(span,p) for c in supported for span in spans_by_id[c.id] for p in ["graduate","trainee","junior","entry level"]) else .5)
            prefs=sum(preference_signals)/len(preference_signals)
            q = max(QUALITY[c.source_kind] for c in supported)
            action = 1. if any(c.kind in {"email", "careers"} for c in channels) else .6
            matching_jobs = [v for v in open_jobs(employer, at) if target and target.id in v.concept_ids]
            score = q*(.40*roles+.25*task+.20*max(0.,min(1.,intent_semantic))+.10*prefs)+.05*action+.03*bool(matching_jobs)
            if group == "related":
                score *= .9
            chosen = max(supported, key=lambda c: (QUALITY[c.source_kind], c.kind in {"function", "historical_role"}))
            phrase = {"historical_role": "Previously observed role", "function": "Published professional function", "activity": "Published business activity", "skill": "Published professional skill"}.get(chosen.kind, "Published evidence")
            reason = f"{phrase}: {'; '.join(spans_by_id[chosen.id][:2]).rstrip('. ')}. This aligns with your interest in {(target.label if group=='related' and target else intent.raw_label).lower()}."
            if chosen.source_kind=='provided_csv':
                phrase='Recorded role history' if chosen.kind=='historical_role' else 'Recorded business activity'
                reason=f"{phrase}: {'; '.join(spans_by_id[chosen.id][:2]).rstrip('. ')}. This aligns with your interest in {(target.label if group=='related' and target else intent.raw_label).lower()}."
            if group == "related":
                reason = f"Related career: {target.label}. " + reason + f" This is an alternative to {intent.raw_label}, not the same role."
            features = {"role": roles, "task": task, "semantic": intent_semantic, "preference": prefs, "quality": q, "action": action, "verified_matching_vacancy": bool(matching_jobs), "intent": intent.raw_label}
            result = Ranked(employer.id, group, score, features,
                {"text": reason, "claim_ids": [c.id for c in supported], "evidence_ids": [digest(["claim",employer.id,c.model_dump(mode="json")]) for c in supported], "sources": [{"url": c.source_url, "excerpt": c.excerpt, "matched_spans": spans_by_id[c.id][:2], "observed_at": c.observed_at.isoformat() if c.observed_at else None,"kind":c.source_kind} for c in supported[:3]], "skill_hits": skill_hits, "basis": chosen.kind}, employer.version)
            if best is None or (group == "direct" and best.group == "related") or (group == best.group and score > best.score):
                best = result
    return best


def rrf(branches):
    weights = {"function": 1., "activity": .6, "lexical": 1., "concept": 1.2}
    totals = {}
    for kind, rows in branches:
        seen = set()
        rank_number = 0
        for employer_id in rows:
            if employer_id in seen:
                continue
            seen.add(employer_id)
            rank_number += 1
            totals[employer_id] = totals.get(employer_id, 0.) + weights[kind]/(60+rank_number)
    return sorted(totals, key=lambda x: (-totals[x], x))[:1500]
