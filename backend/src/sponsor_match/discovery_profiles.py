"""Occupation-wide synthetic interests and source-backed project variants.

These are test hypotheses, never inferred qualifications about real people.
Employer identifiers are provenance only and never enter a profile's text.
"""
from collections import defaultdict
from pathlib import Path
import gzip,json
import numpy as np
from .intelligence import digest
from .prospects import profile_for
from .taxonomy import key
from .exposure_order import normalized

VERSION='discovery-interest-context-1'


def interest_variants(group,link,activities):
    effective={**group,'label':link['span']} if link['kind']=='role' else group
    own=next((a for a in activities if normalized(a['span'])==normalized(link['span'])),None) if link['kind']=='activity' else None
    selected=[];seen=set()
    for activity in ([own] if own else [])+activities:
        if normalized(activity['span']) in seen:continue
        selected.append(activity);seen.add(normalized(activity['span']))
        if len(selected)==3:break
    for specialization in [None,*selected[:2]]:
        profile=profile_for(effective,specialization['span'] if specialization else '')
        evidence={link['claim_id']}
        if specialization:evidence.add(specialization['claim_id'])
        yield {'profile':profile,'variant':'role_and_specialization','evidence_ids':evidence}
        for focus in selected[:2]:
            if specialization and normalized(focus['span'])==normalized(specialization['span']):continue
            variant=profile.model_copy(update={'experience_summary':'Interested in projects involving '+focus['span'].rstrip('. ')+'.'})
            yield {'profile':variant,'variant':'project_interest','evidence_ids':evidence|{focus['claim_id']}}


class DiscoveryProfiles:
    def __init__(self,folder):
        self.folder=Path(folder);self.activities=defaultdict(list);self.cache={};self.references=[];self.reference_index={};self.term_index={}
        path=self.folder/'references.json'
        if path.exists():
            self.references=json.loads(path.read_text());self.reference_index={r['id']:i for i,r in enumerate(self.references)}
        self.available=all((self.folder/name).exists() for name in ['reference-vectors.npz','term-vectors.npz','corpus.json.gz']) and bool(self.references)
        if self.available:
            self.reference_vectors=np.load(self.folder/'reference-vectors.npz')['vectors']
            data=np.load(self.folder/'term-vectors.npz');self.term_vectors=data['vectors'];self.term_index={tid:i for i,tid in enumerate(data['term_ids'].tolist())}
            with gzip.open(self.folder/'corpus.json.gz','rt') as f:corpus=json.load(f)
            for row in corpus['observations']:
                if row['kind']=='activity' and 3<=len(row['text'])<=150:
                    self.activities[row['employer_id']].append({'span':row['text'],'claim_id':row['claim_id'],'term_id':row['term_id']})

    def official_baseline(self):
        records=[];skipped=[]
        for reference in sorted(self.references,key=lambda r:r['id']):
            label=reference['label']
            if len(label)>120:
                # Never silently truncate an official title's specialization.
                skipped.append(reference['id']);continue
            profile=profile_for(reference)
            records.append({'profile':profile,'reference_id':reference['id']})
        info={'available':bool(self.references),'references':len(self.references),'profiles':len(records),'overlong_titles_not_truncated':skipped,'reference_hash':digest(self.references),'profiles_hash':digest([r['profile'].model_dump(mode='json') for r in records])}
        return records,info

    def contexts_for(self,employer_name,link,group):
        cache_key=(link['employer_id'],link['group_id'],link['kind'],link.get('term_id'))
        if cache_key in self.cache:return self.cache[cache_key]
        if not self.available:return []
        if link['kind']=='role' and link.get('term_id') in self.term_index:
            vector=self.term_vectors[self.term_index[link['term_id']]]
        elif group.get('reference_id') in self.reference_index:
            vector=self.reference_vectors[self.reference_index[group['reference_id']]]
        else:return []
        candidates=[]
        for item in self.activities[link['employer_id']]:
            if len(key(employer_name))>=5 and key(employer_name) in key(item['span']):continue
            score=float(self.term_vectors[self.term_index[item['term_id']]]@vector)
            if score>=.43:candidates.append({**item,'similarity':score})
        candidates.sort(key=lambda item:(-item['similarity'],normalized(item['span']),item['claim_id']))
        result=[];seen=set()
        for item in candidates:
            if normalized(item['span']) in seen:continue
            if candidates and item['similarity']<candidates[0]['similarity']-.10:continue
            result.append(item);seen.add(normalized(item['span']))
            if len(result)==3:break
        self.cache[cache_key]=result
        return result
