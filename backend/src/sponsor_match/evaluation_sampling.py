"""Deterministic occupation-stratified synthetic profiles, independent of employer results."""
from collections import defaultdict
from copy import deepcopy
import re
from .intelligence import digest
from .models import Profile


def sample_profiles(occupations, skills, count=80, seed='sponsorreach-eval-1'):
    by_id={r['id']:r for r in occupations}; skill_index={s['id']:s for s in skills}
    def codes(row,visited=None):
        visited=set() if visited is None else visited
        if row['id'] in visited:return set()
        visited.add(row['id']);result=set(row.get('isco',[]))
        for parent in row.get('broader',[]):
            if parent in by_id:result.update(codes(by_id[parent],visited))
        return result
    strata=defaultdict(list)
    for row in occupations:
        linked=[skill_index[s['id']] for s in row['skills'] if s['id'] in skill_index and skill_index[s['id']].get('type')=='skill']
        code=next(iter(sorted(codes(row))),None)
        match=re.search(r'/C(\d{4})$',code or '')
        if not match or len(linked)<2:continue
        strata[match[1][0]].append((row,match[1],linked))
    for major in strata:strata[major].sort(key=lambda x:digest([seed,x[0]['id']]))
    if count>sum(len(v) for v in strata.values()):raise ValueError('Not enough eligible occupations')
    chosen=[]
    while len(chosen)<count:
        for major in sorted(strata):
            if strata[major]:chosen.append(strata[major].pop())
            if len(chosen)==count:break
    output=[]
    for occupation,code,linked in chosen:
        family='isco:'+code[:2]
        split='held_out' if int(digest([seed,family])[:8],16)%5==0 else 'development'
        # Skills describe invented test personas, not abilities inferred for real users.
        linked.sort(key=lambda s:digest([seed,occupation['id'],s['id']]))
        labels=[s['label'] for s in linked[:3]]
        base={'background':{'subject':occupation['label'][:180]},
              'role_intents':[{'raw_label':occupation['label'][:120],'confirmed':True}],
              'career_stage':'graduate'}
        for variant in ['role_only','explicit_tasks','full_context']:
            profile=deepcopy(base)
            if variant!='role_only':profile['skills']=[{'label':s,'source':'user'} for s in labels]
            if variant=='full_context':
                profile['background']['specialization']=labels[0][:180]
                profile['experience_summary']=('Synthetic test scenario: practical work involving '+', '.join(labels)+'.')[:500]
                profile['location']={'preferred_regions':['London'],'relocate':True}
                profile['career_stage']='experienced'
            output.append({'id':'sample:'+occupation['id'].rsplit('/',1)[-1]+':'+variant,
                           'family':family,'major_family':code[0],'split':split,'variant':variant,
                           'synthetic':True,'source_occupation':occupation['id'],'sampling_seed':seed,
                           'profile':Profile.model_validate(profile).model_dump()})
    return output
