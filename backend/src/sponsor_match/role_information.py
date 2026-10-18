"""Occupation-wide vocabulary statistics, with no profession-specific aliases."""
import math
from collections import defaultdict
from .taxonomy import key

VERSION='role-information-1'


class RoleInformation:
    def __init__(self,references,word_parts=None):
        self.word_parts=word_parts or (lambda words:[[word] for word in words])
        titles=[(r['id'].rsplit(':',1)[-1][:4],title)
                for r in references for title in [r['label'],*r.get('aliases',[])]]
        words=sorted({word for _,title in titles for word in key(title).split()})
        self.parts=dict(zip(words,self.word_parts(words)))
        families=defaultdict(set)
        for parent,title in titles:
            for word in key(title).split():
                for part in self.parts[word]:families[part].add(parent)
        total=len({parent for parent,_ in titles})
        self.unseen_information=1+math.log(total+1)
        self.information={part:1+math.log((total+1)/(len(parents)+1)) for part,parents in families.items()}

    def generic_labels(self,title):
        """Remove informative qualifiers to construct a contrastive baseline.

        Frequent functional vocabulary is learned across four-digit families.
        WordPiece parts prevent a common compound from looking artificially
        rare solely because its whole-word spelling differs.
        """
        words=key(title).split()
        if len(words)<2:return []
        unknown=[word for word in words if word not in self.parts]
        if unknown:self.parts.update(zip(unknown,self.word_parts(unknown)))
        scores=[min((self.information.get(part,self.unseen_information) for part in self.parts[word]),default=self.unseen_information) for word in words]
        if max(scores)-min(scores)<.5:return []
        # Retain the less informative half in its original order. This is a
        # counterfactual retrieval input, never a rewritten candidate intent.
        keep=set(sorted(range(len(words)),key=lambda i:(scores[i],i))[:max(1,len(words)//2)])
        highest=max(range(len(words)),key=lambda i:(scores[i],-i))
        variants=[' '.join(word for i,word in enumerate(words) if i!=highest),
                  ' '.join(word for i,word in enumerate(words) if i in keep)]
        return list(dict.fromkeys(variants))

    def generic_label(self,title):
        labels=self.generic_labels(title)
        return labels[0] if labels else None
