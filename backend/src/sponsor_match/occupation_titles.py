"""Official-title competition for the offline semantic experiment.

Different occupational titles can describe professionally related functions.
Only a strong title competitor in a semantically distant family can veto a
historical role. No employer identity or manually curated niche terms enter it.
"""
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import numpy as np
from .intelligence import digest
from .taxonomy import key

VERSION='occupation-title-competition-2'


def title_supported(own,competing,affinity):
    return (competing<.60)|(competing-own<=.10)|(affinity>=.40)


class TitleCompetition:
    def __init__(self,folder,store,references,reference_vectors,term_ids,terms,term_vectors):
        self.parents=sorted({r['id'].rsplit(':',1)[-1][:4] for r in references})
        self.reference_parents=[r['id'].rsplit(':',1)[-1][:4] for r in references]
        self.parent_index={parent:i for i,parent in enumerate(self.parents)}
        self.role_indices=np.array([i for i,tid in enumerate(term_ids) if terms[tid]['kind']=='role'],dtype=int)
        titles={}
        for reference,parent in zip(references,self.reference_parents):
            for title in [reference['label'],*reference.get('aliases',[])]:
                if key(title):titles.setdefault(key(title),set()).add(parent)
        self.labels=sorted(titles)
        self.title_parents=[sorted(titles[label]) for label in self.labels]
        fingerprint=digest([VERSION,store.model,references,[term_ids[i] for i in self.role_indices],sha256(term_vectors[self.role_indices].tobytes()).hexdigest()])
        path=Path(folder).parent/('title-competition-'+fingerprint[:24]+'.npz')
        if path.exists():
            with np.load(path,allow_pickle=False) as data:
                self.own=data['own'];self.best=data['best'];self.best_score=data['best_score']
        else:
            vectors=store.encode(self.labels)
            title_columns=[[i for i,parents in enumerate(self.title_parents) if parent in parents] for parent in self.parents]
            self.own=np.empty((len(self.role_indices),len(self.parents)),dtype=np.float32)
            self.best=np.empty(len(self.role_indices),dtype=int)
            self.best_score=np.empty(len(self.role_indices),dtype=np.float32)
            for start in range(0,len(self.role_indices),64):
                batch=self.role_indices[start:start+64];scores=term_vectors[batch]@vectors.T
                self.best[start:start+len(batch)]=np.argmax(scores,axis=1)
                self.best_score[start:start+len(batch)]=np.max(scores,axis=1)
                for column,indices in enumerate(title_columns):self.own[start:start+len(batch),column]=scores[:,indices].max(axis=1)
            temporary=path.with_name(path.stem+'-'+uuid4().hex+'.tmp.npz')
            np.savez_compressed(temporary,own=self.own,best=self.best,best_score=self.best_score)
            temporary.replace(path)
        reference_affinity=reference_vectors@reference_vectors.T
        self.parent_affinity=np.stack([reference_affinity[:,np.array(self.reference_parents)==parent].max(axis=1) for parent in self.parents],axis=1)
        self.total_terms=len(term_ids)
        self.term_to_role={int(term):role for role,term in enumerate(self.role_indices)}
        self._masks={}

    def mask(self,reference):
        if reference not in self._masks:
            own=self.own[:,self.parent_index[self.reference_parents[reference]]]
            affinity=np.array([max(self.parent_affinity[reference,self.parent_index[parent]] for parent in self.title_parents[index]) for index in self.best])
            result=np.ones(self.total_terms,dtype=bool)
            result[self.role_indices]=title_supported(own,self.best_score,affinity)
            self._masks[reference]=result
        return self._masks[reference]

    def features(self,term,reference):
        role=self.term_to_role.get(int(term))
        if role is None:return None
        best=int(self.best[role]);parents=self.title_parents[best]
        return {'version':VERSION,'closest_title':self.labels[best],'closest_parents':parents,'closest_similarity':float(self.best_score[role]),'intended_parent_similarity':float(self.own[role,self.parent_index[self.reference_parents[reference]]]),'family_affinity':max(float(self.parent_affinity[reference,self.parent_index[parent]]) for parent in parents)}
