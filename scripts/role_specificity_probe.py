"""Measure generic-title and whole-source contrasts on frozen review pairs."""
import argparse,json
from collections import Counter
from pathlib import Path
import numpy as np
from sponsor_match.config import Settings
from sponsor_match.providers import embedding_provider
from sponsor_match.prospects import VectorStore
from sponsor_match.role_information import RoleInformation


def main():
    p=argparse.ArgumentParser();p.add_argument('--matrix',action='append',required=True);p.add_argument('--model-folder',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    settings=Settings.from_env();provider=embedding_provider(settings)
    folder=Path(args.model_folder);refs=json.loads((folder/'references.json').read_text());ref_vectors=np.load(folder/'reference-vectors.npz')['vectors'];ref_ids={r['id']:i for i,r in enumerate(refs)}
    info=RoleInformation(refs,getattr(provider,'word_parts',None));store=VectorStore(folder.parent/'claim-context-vectors.sqlite3',provider,settings.embedding_model)
    rows=[]
    for matrix in args.matrix:
        matrix=Path(matrix);gold={(r['profile_id'],r['employer_id']):r['label'] for r in json.loads((matrix/'ai-anchor-reviews.json').read_text())}
        for row in json.loads((matrix/'runs.json').read_text()):
            for result in row['results']:
                label=gold.get((row['id'],result['employer_id']))
                if label is None:continue
                intent=result['features']['intent'];generic=info.generic_labels(intent)
                source=result['explanation']['sources'][0];span=source['matched_spans'][0]
                vectors=store.encode([intent,span,source['excerpt'],*generic])
                ref=ref_ids[result['explanation']['derived_relationship']['occupation_reference']]
                parent=refs[ref]['id'].rsplit(':',1)[-1][:4]
                active=[];synonyms=[]
                for name,vector in zip(generic,vectors[3:]):
                    scores=ref_vectors@vector;best_generic=int(np.argmax(scores))
                    other=max((float(score) for i,score in enumerate(scores) if refs[i]['id'].rsplit(':',1)[-1][:4]!=parent),default=-1.)
                    if best_generic==ref and float(scores[ref])>=.60 and float(scores[ref])-other>=.025:synonyms.append(name)
                    else:active.append((name,vector))
                generic=[name for name,_ in active];generic_vectors=[v for _,v in active]
                direct=float(vectors[1]@vectors[0]);generic_scores=[float(vectors[1]@v) for v in generic_vectors]
                context_scores=ref_vectors@vectors[2]
                context_task=float(context_scores[ref]);best=int(np.argmax(context_scores))
                specific_margin=direct-max(generic_scores) if generic_scores else None
                source_specific=float(vectors[2]@vectors[0]);source_generic=[float(vectors[2]@v) for v in generic_vectors]
                source_margin=source_specific-max(source_generic) if source_generic else None
                reference_alignment=float(ref_vectors[ref]@ref_vectors[best])
                generic_ok=specific_margin is None or specific_margin>=-.04 or (source_margin>=-.04 and context_task>=.30)
                context_ok=not (result['explanation']['basis']=='activity' and len(span.split())==1 and context_task<.30 and float(context_scores[best])-context_task>.15 and reference_alignment<.40)
                rows.append({'profile_id':row['id'],'employer_id':result['employer_id'],'name':result['employer_name'],'gold':label,'intent':intent,'span':span,'kind':result['explanation']['basis'],'source_excerpt':source['excerpt'],'generic_labels':generic,'synonymous_counterfactuals':synonyms,'specific_similarity':direct,'generic_similarities':generic_scores,'specificity_margin':specific_margin,'source_specificity_margin':source_margin,'generic_ok':generic_ok,'context_task_similarity':context_task,'best_context_reference':refs[best]['label'],'context_competition_margin':float(context_scores[best])-context_task,'reference_alignment':reference_alignment,'context_ok':context_ok,'retained':generic_ok and context_ok})
    summary={'pairs':len(rows),'labels':dict(Counter(r['gold'] for r in rows)),
             'retained':dict(Counter(r['gold'] for r in rows if r['retained'])),
             'rejected':dict(Counter(r['gold'] for r in rows if not r['retained'])),
             'note':'Feature diagnostic on AI development labels. No ranking or user profiles changed. Not held-out validation or post-filter top-K accuracy.'}
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);(out/'pairs.json').write_text(json.dumps(rows,indent=2));(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
