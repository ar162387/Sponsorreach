"""Deterministic professional-profile ordering of exact-score ties.

This changes exposure only among identical scores. It never changes eligibility,
scores, intent balance or the saved-shortlist limit. No employer can be targeted
through a candidate-profile field.
"""
import re,unicodedata
from collections import Counter
from .intelligence import digest

VERSION='professional-tie-order-1'
SOURCE_VERSION='source-context-tie-order-1'


def normalized(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',text).casefold()).strip()


def professional_seed(profile):
    # Exclude identity, visa, location and career-stage fields. Those cannot
    # manufacture different exposures without different professional input.
    return digest([VERSION,{'roles':[normalized(r.raw_label) for r in profile.role_intents],
        'subject':normalized(profile.background.subject),'specialization':normalized(profile.background.specialization),
        'skills':sorted({normalized(s.label) for s in profile.skills}),
        'experience':normalized(profile.experience_summary),
        'certifications':sorted({normalized(c) for c in profile.certifications})}])


def semantic_source_context(text,employer_name):
    text=unicodedata.normalize('NFKC',text)
    # Keep the original evidence intact; this is a derived embedding input.
    if len(re.sub(r'\W','',employer_name))>=5:
        name=r'\s+'.join(re.escape(part) for part in employer_name.split())
        text=re.sub(r'(?<!\w)'+name+r'(?!\w)',' ',text,flags=re.I)
    text=re.sub(r'https?://\S+|\bwww\.\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b',' ',text,flags=re.I)
    text=re.sub(r'(?<!\w)(?:\+\d{1,3}[\s().-]*)?(?:\(?\d{2,5}\)?[\s.-]*){2,5}(?!\w)',
                lambda match:' ' if sum(c.isdigit() for c in match.group())>=8 else match.group(),text)
    return re.sub(r'\s+',' ',text).strip()


def profile_tie_shortlist(results,profile,limit,source_scores=None):
    seed=professional_seed(profile)
    source_scores=source_scores or {}
    ordered=sorted(results,key=lambda r:(-r.score,-source_scores.get(r.employer_id,0.),digest([seed,r.employer_id]),r.employer_id))
    if len(profile.role_intents)<2:return ordered[:limit]
    buckets=[[r for r in ordered if r.features['intent']==intent.raw_label] for intent in profile.role_intents]
    output=[];seen=set()
    while any(buckets) and len(output)<limit:
        for bucket in buckets:
            while bucket and bucket[0].employer_id in seen:bucket.pop(0)
            if bucket and len(output)<limit:
                result=bucket.pop(0);seen.add(result.employer_id);output.append(result)
    return output


def source_tie_scores(results,profile_vector,employer_names,store):
    counts=Counter(r.score for r in results)
    contexts={r.employer_id:semantic_source_context(r.explanation['sources'][0]['excerpt'],employer_names[r.employer_id])
              for r in results if counts[r.score]>1}
    texts=list(dict.fromkeys(text for text in contexts.values() if text))
    if not texts:return {}
    vectors=dict(zip(texts,store.encode(texts)))
    return {eid:float(vectors[text]@profile_vector) for eid,text in contexts.items() if text}
