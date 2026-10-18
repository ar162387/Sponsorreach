"""Offline title-family competition diagnostic; never changes live matching.

Compare historical-role spans with every official occupation label/alias.
Activity spans are deliberately not interpreted as occupational titles.
"""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from sponsor_match.config import Settings
from sponsor_match.intelligence import digest
from sponsor_match.providers import embedding_provider
from sponsor_match.prospects import VectorStore
from sponsor_match.taxonomy import key

VERSION='official-title-competition-probe-1'
MIN_COMPETITOR=.60
COMPETITOR_MARGIN=.10


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--matrix',action='append',required=True)
    parser.add_argument('--model-folder',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--family-aware',action='store_true')
    args=parser.parse_args()
    settings=Settings.from_env()
    if settings.embedding_provider!='local':raise ValueError('This diagnostic requires free local embeddings')
    folder=Path(args.model_folder)
    manifest=json.loads((folder/'manifest.json').read_text())
    if manifest['model']!=settings.embedding_model:raise ValueError('Encoder and source model differ')
    references=json.loads((folder/'references.json').read_text())
    reference_vectors=np.load(folder/'reference-vectors.npz')['vectors']
    reference_index={r['id']:i for i,r in enumerate(references)}
    # Keep ambiguous aliases attached to every applicable parent; they cannot
    # become a confident competing-family veto merely through ordering.
    titles=defaultdict(set)
    for reference in references:
        parent=reference['id'].rsplit(':',1)[-1][:4]
        for title in [reference['label'],*reference.get('aliases',[])]:
            if key(title):titles[key(title)].add(parent)
    title_labels=sorted(titles)
    store=VectorStore(folder.parent/'occupation-title-vectors.sqlite3',embedding_provider(settings),settings.embedding_model)
    title_vectors=store.encode(title_labels,lambda item:print(json.dumps(item),flush=True))
    rows=[];inputs=[];seen=set()
    for matrix in args.matrix:
        matrix=Path(matrix)
        inputs.append({'matrix':matrix.name,'runs_hash':digest((matrix/'runs.json').read_text()),'labels_hash':digest((matrix/'ai-anchor-reviews.json').read_text())})
        gold={(r['profile_id'],r['employer_id']):r for r in json.loads((matrix/'ai-anchor-reviews.json').read_text())}
        for run in json.loads((matrix/'runs.json').read_text()):
            if run['variant']!='complete':continue
            if run['versions']['prospect_model']!=manifest['version']:raise ValueError('Review source model differs')
            for result in run['results']:
                pair=(run['id'],result['employer_id'])
                if pair not in gold or pair in seen:continue
                seen.add(pair);review=gold[pair];explanation=result['explanation']
                span=explanation['sources'][0]['matched_spans'][0]
                parent=explanation['derived_relationship']['occupation_reference'].rsplit(':',1)[-1][:4]
                vector=store.encode([span])[0];scores=title_vectors@vector
                own=np.array([parent in titles[t] for t in title_labels])
                own_index=int(np.argmax(np.where(own,scores,-np.inf)))
                other_index=int(np.argmax(np.where(~own,scores,-np.inf)))
                own_score=float(scores[own_index]);other_score=float(scores[other_index])
                applicable=explanation['basis'] in {'historical_role','function'}
                rejected=applicable and other_score>=MIN_COMPETITOR and other_score-own_score>COMPETITOR_MARGIN
                target=reference_index[explanation['derived_relationship']['occupation_reference']]
                competing_parents=titles[title_labels[other_index]]
                competitor_indices=[i for i,r in enumerate(references) if r['id'].rsplit(':',1)[-1][:4] in competing_parents]
                affinity=float((reference_vectors[competitor_indices]@reference_vectors[target]).max())
                if args.family_aware:rejected &= affinity<.40
                rows.append({'profile_id':run['id'],'employer_id':result['employer_id'],'employer_name':result['employer_name'],'family':run['family'],'intent':result['features']['intent'],'gold':review['label'],'basis':explanation['basis'],'span':span,'source_excerpt':explanation['sources'][0]['excerpt'],'applicable':applicable,'own_title':title_labels[own_index],'own_similarity':own_score,'competing_title':title_labels[other_index],'competing_parents':sorted(competing_parents),'competing_similarity':other_score,'margin':other_score-own_score,'family_affinity':affinity,'rejected':bool(rejected)})
    summary={'version':'official-title-competition-probe-2' if args.family_aware else VERSION,'family_aware':args.family_aware,'minimum_family_affinity':.40 if args.family_aware else None,'source_model':manifest['version'],'inputs':inputs,'pairs':len(rows),'labels':dict(Counter(r['gold'] for r in rows)),'applicable_role_pairs':sum(r['applicable'] for r in rows),'retained':dict(Counter(r['gold'] for r in rows if not r['rejected'])),'rejected':dict(Counter(r['gold'] for r in rows if r['rejected'])),'by_family':{family:dict(Counter(r['gold'] for r in rows if r['family']==family and r['rejected'])) for family in sorted({r['family'] for r in rows})},'minimum_competitor_similarity':MIN_COMPETITOR,'competing_margin':COMPETITOR_MARGIN,'official_unique_titles':len(titles),'live_integration':False,'note':'Diagnostic agreement with AI development labels, not held-out accuracy or post-filter Precision@K. No source claims, rankings or candidate data changed.'}
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'pairs.json').write_text(json.dumps(rows,indent=2))
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
