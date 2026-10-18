"""Metrics consume reviewed labels; unjudged pairs are never negatives."""
import math
from collections import defaultdict
from .models import Profile,Background,RoleIntent,Skill,Location
from .taxonomy import Taxonomy


def profiles():
    result=[]
    for concept in Taxonomy().concepts:
        for variant in range(10):
            result.append({"id":f"{concept.id}:{variant}","occupation_family":concept.id,"synthetic":True,"profile":Profile(background=Background(subject=concept.backgrounds[0]),role_intents=[RoleIntent(raw_label=concept.label,concept_id=concept.id,confirmed=True)],career_stage="graduate" if variant<5 else "experienced",skills=[Skill(label=s) for s in concept.skills[:variant%3]],location=Location(preferred_regions=[] if variant%2 else ["London"],relocate=bool(variant%2)),related_roles_enabled=variant==9).model_dump()})
    return result


def metrics(rankings,labels,k=10):
    if k<1:raise ValueError('Metric depth must be positive')
    by_profile=defaultdict(dict)
    for label in labels:
        if label["label"]!="unjudged":
            by_profile[label["profile_id"]][label["employer_id"]]=label["label"]
    scores=[];top_items=0;judged_items=0;fully_judged_profiles=0
    for pid,ranking in rankings.items():
        judged=by_profile.get(pid,{})
        top=ranking[:k]
        observed=[e for e in top if e in judged]
        top_items+=len(top);judged_items+=len(observed)
        if not judged or not observed:
            continue
        gains={"direct":3,"related":1,"insufficient_evidence":0,"irrelevant":0,"wrong_entity":0}
        fully_judged=len(observed)==len(top)
        fully_judged_profiles+=int(fully_judged)
        dcg=sum((2**gains.get(judged.get(e),0)-1)/math.log2(i+2) for i,e in enumerate(top))
        ideal=sorted([gains.get(v,0) for v in judged.values()],reverse=True)[:k]
        idcg=sum((2**v-1)/math.log2(i+2) for i,v in enumerate(ideal))
        relevant={e for e,label in judged.items() if label=="direct"}
        scores.append({"precision_at_k":sum(judged[e]=="direct" for e in observed)/len(top) if fully_judged else None,"judged_precision_at_k":sum(judged[e]=="direct" for e in observed)/len(observed),"ndcg_at_k":(dcg/idcg if idcg else 0.) if fully_judged else None,"pooled_recall_at_200":len(relevant.intersection(ranking[:200]))/len(relevant) if relevant else None,"judged_coverage":len(observed)/len(top)})
    coverage={"profiles_fully_judged_at_k":fully_judged_profiles,"returned_top_k_items":top_items,"judged_top_k_items":judged_items,"overall_judged_item_coverage":judged_items/top_items if top_items else None}
    if not scores:
        return {"status":"not_evaluated","profiles_judged":0,"profiles_total":len(rankings),**coverage,"release_gate_passed":False}
    averages={name:sum(s[name] for s in scores if s[name] is not None)/sum(s[name] is not None for s in scores) if any(s[name] is not None for s in scores) else None for name in scores[0]}
    return {"status":"evaluated","profiles_judged":len(scores),"profiles_total":len(rankings),**coverage,"abstentions":sum(not r for r in rankings.values()),"shortlists_below_k":sum(len(r)<k for r in rankings.values()),**averages,"release_gate_passed":False,"note":"Precision/NDCG summarize only fully judged returned top-K; inspect profiles_fully_judged_at_k and overall_judged_item_coverage before interpreting them. Abstentions and short lists are reported separately. Pooled recall uses available ranking depth (saved direct shortlists are capped at 100). Release also requires occupational slice coverage, independent explanation review and attribution audits."}
