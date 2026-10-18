"""Compare local encoders against AI-labelled professional evidence pairs.

No database writes or network calls. Labels never enter encoder input text.
These development samples are not independent human validation.
"""
import argparse,html,json,math,time
from collections import Counter
from pathlib import Path
import numpy as np
from sponsor_match.intelligence import digest

VERSION='occupation-definition-encoder-probe-2'
MODELS={
    'minilm':{'name':'sentence-transformers/all-MiniLM-L6-v2','revision':'1110a243fdf4706b3f48f1d95db1a4f5529b4d41','chunk_tokens':224,'query_prefix':''},
    'bge':{'name':'BAAI/bge-small-en-v1.5','revision':'5c38ec7c405ec4b44b94cc5a9bb96e735b38267a','chunk_tokens':448,'query_prefix':'Represent this sentence for searching relevant passages: '},
}


def auc(rows,field):
    positive=[r[field] for r in rows if r['label']=='direct']
    negative=[r[field] for r in rows if r['label']!='direct']
    if not positive or not negative:return None
    return sum(float(p>n)+.5*float(p==n) for p in positive for n in negative)/(len(positive)*len(negative))


def calibration(training,evaluation,field,retention=.95):
    direct=sorted((r[field] for r in training if r['label']=='direct'),reverse=True)
    if not direct or not any(r['label']!='direct' for r in training):
        return {'threshold':None,'status':'insufficient_calibration_labels'}
    threshold=direct[max(0,math.ceil(retention*len(direct))-1)]
    def summarize(rows):
        kept=[r for r in rows if r[field]>=threshold];total=sum(r['label']=='direct' for r in rows)
        supported=sum(r['label']=='direct' for r in kept)
        return {'pairs':len(rows),'retained':dict(Counter(r['label'] for r in kept)),
                'rejected':dict(Counter(r['label'] for r in rows if r[field]<threshold)),
                'direct_retention':supported/total if total else None,'retained_direct_fraction':supported/len(kept) if kept else None}
    return {'threshold':threshold,'training_direct_retention_target':retention,'training':summarize(training),
            'newer_development_sample':summarize(evaluation),'threshold_source':'older_development_pairs_only','release_ready':False}


def collect_pairs(matrix,cohort,references):
    matrix=Path(matrix);rows=json.loads((matrix/'runs.json').read_text())
    labels=json.loads((matrix/'ai-anchor-reviews.json').read_text())
    label_map={(r['profile_id'],r['employer_id']):r for r in labels};result=[]
    for row in rows:
        for position,match in enumerate(row['results'],1):
            label=label_map.get((row['id'],match['employer_id']))
            if not label or label['label']=='unjudged':continue
            if label.get('reviewer_type')!='ai':raise ValueError('This diagnostic requires explicitly AI-labelled pairs')
            reference=match['explanation']['derived_relationship']['occupation_reference']
            if reference not in references:raise ValueError('Unknown occupation reference')
            if label.get('source_hash') and label['source_hash']!=digest(match['explanation']):raise ValueError('Reviewed evidence changed')
            if label.get('ranking_version') and label['ranking_version']!=row['versions']['ranking']:raise ValueError('Reviewed ranker changed')
            result.append({'cohort':cohort,'matrix':matrix.name,'profile_id':row['id'],'employer_id':match['employer_id'],
                           'position':position,'label':label['label'],'reference_id':reference,'intent':match['features']['intent'],
                           'kind':match['explanation']['basis'],'sources':match['explanation']['sources'],
                           'versions':row['versions'],'evidence_hash':digest(match['explanation'])})
    return result


class Encoder:
    def __init__(self,name,cache):
        self.spec=MODELS[name];self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True);self.model=None
    def encode(self,texts):
        path=self.cache/(digest([VERSION,self.spec,texts])+'.npz')
        if path.exists():
            vectors=np.load(path)['vectors']
            if vectors.shape!=(len(texts),384) or not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4):raise ValueError('Invalid cached vectors')
            return vectors
        if self.model is None:
            import torch
            from sentence_transformers import SentenceTransformer
            torch.set_num_threads(2)
            self.model=SentenceTransformer(self.spec['name'],revision=self.spec['revision'],device='cpu',
                trust_remote_code=False,local_files_only=True,model_kwargs={'use_safetensors':True})
        chunks=[];owners=[]
        for i,text in enumerate(texts):
            ids=self.model.tokenizer.encode(text,add_special_tokens=False)
            for start in range(0,max(1,len(ids)),self.spec['chunk_tokens']):
                chunks.append(self.model.tokenizer.decode(ids[start:start+self.spec['chunk_tokens']]))
                owners.append(i)
        vectors=self.model.encode(chunks,batch_size=32,normalize_embeddings=True,show_progress_bar=False,convert_to_numpy=True)
        pooled=np.asarray([vectors[np.asarray(owners)==i].mean(axis=0) for i in range(len(texts))]);norms=np.linalg.norm(pooled,axis=1,keepdims=True)
        if not np.isfinite(pooled).all() or (norms<=0).any():raise ValueError('Invalid encoder output')
        pooled=(pooled/norms).astype(np.float32)
        if pooled.shape!=(len(texts),384):raise ValueError('Unexpected dimensions')
        np.savez_compressed(path,vectors=pooled)
        return pooled


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-folder',required=True)
    parser.add_argument('--training-matrix',action='append',required=True);parser.add_argument('--evaluation-matrix',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args();folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    references=json.loads((Path(args.model_folder)/'references.json').read_text());reference_map={r['id']:r for r in references}
    pairs=[p for matrix in args.training_matrix for p in collect_pairs(matrix,'older_development',reference_map)]
    pairs+=collect_pairs(args.evaluation_matrix,'newer_development',reference_map)
    if not pairs:raise ValueError('No reviewed evidence pairs')
    if len({digest(p['versions']) for p in pairs})!=1:raise ValueError('Compare one frozen matcher/model/register version')
    manifest={'version':VERSION,'implementation_hash':digest(Path(__file__).read_text()),'reference_hash':digest(references),
              'input_pairs_hash':digest(pairs),'models':MODELS,'source_model_folder':Path(args.model_folder).name,
              'versions':pairs[0]['versions'],'independent_human_reviews':0,'labels_supplied_to_encoder':False,'application_changes':False}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2));scores={};pair_hashes={}
    parents=np.array([r['id'].rsplit(':',1)[-1][:4] for r in references]);ref_index={r['id']:i for i,r in enumerate(references)}
    for name,model in MODELS.items():
        started=time.monotonic();encoder=Encoder(name,folder/'vectors');prefix=model['query_prefix']
        texts=list(dict.fromkeys([prefix+r['text'] for r in references]+[s['excerpt'] for p in pairs for s in p['sources']]+[span for p in pairs for s in p['sources'] for span in s.get('matched_spans',[])]))
        vectors=encoder.encode(texts);by_text=dict(zip(texts,vectors));ref_vectors=np.asarray([by_text[prefix+r['text']] for r in references]);output=[]
        for pair in pairs:
            excerpts=list(dict.fromkeys(s['excerpt'] for s in pair['sources']))
            vector=np.asarray([by_text[s] for s in excerpts]).mean(axis=0);vector/=np.linalg.norm(vector)
            similarities=ref_vectors@vector;ref=ref_index[pair['reference_id']];other=similarities[parents!=parents[ref]];own=similarities[parents==parents[ref]]
            target=float(similarities[ref]);best=int(np.argmax(similarities))
            spans=list(dict.fromkeys(span for source in pair['sources'] for span in source.get('matched_spans',[])))
            if not spans:raise ValueError('A professional evidence pair must retain its matched spans')
            span_scores=np.asarray([ref_vectors@by_text[span] for span in spans])
            span_margin=max(float(values[parents==parents[ref]].max()-values[parents!=parents[ref]].max()) for values in span_scores)
            span_similarity=max(float(values[ref]) for values in span_scores)
            output.append({**pair,'definition_similarity':target,'occupation_family_margin':float(own.max()-other.max()),
                           'specific_reference_margin':float(target-other.max()),'span_definition_similarity':span_similarity,'span_family_margin':span_margin,'facet_or_source_family_margin':max(span_margin,float(own.max()-other.max())),'best_reference_id':references[best]['id'],
                           'best_reference_label':references[best]['label'],'best_reference_similarity':float(similarities[best])})
        older=[r for r in output if r['cohort']=='older_development'];newer=[r for r in output if r['cohort']=='newer_development']
        fields=['definition_similarity','occupation_family_margin','specific_reference_margin','span_definition_similarity','span_family_margin','facet_or_source_family_margin']
        scores[name]={'modelspec':model,'older_pairs':len(older),'newer_pairs':len(newer),
                      'pair_feature_auc':{field:{'older_development':auc(older,field),'newer_development':auc(newer,field)} for field in fields},
                      'calibration':{field:calibration(older,newer,field) for field in fields},
                      'elapsed_seconds_including_cache_lookup':round(time.monotonic()-started,3)}
        pair_hashes[name]=digest(output)
        (folder/(name+'-pairs.json')).write_text(json.dumps(output,indent=2));print(json.dumps({'encoder':name,**scores[name]}),flush=True)
    summary={'version':VERSION,'manifest_hash':digest(manifest),'pair_output_hashes':pair_hashes,'pairs':len(pairs),'labels':dict(Counter(p['label'] for p in pairs)),'models':scores,
             'release_ready':False,'retrieval_precision_measured':False,'independent_human_reviews':0,
             'note':'Feature discrimination and cross-sample threshold transfer on AI development labels. Existing returned pairs, not rerun retrieval; post-filter results do not establish top-K accuracy. No live matcher or index changed.'}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2))
    render_report(folder,summary)


def render_report(folder,summary):
    esc=lambda value:html.escape(str(value))
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>SponsorReach local encoder comparison</title><style>body{font:16px/1.5 system-ui;color:#123e50;background:#f7f9f8;max-width:1050px;margin:32px auto;padding:0 20px;overflow-wrap:anywhere}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;background:white}th,td{padding:12px;text-align:left;border-bottom:1px solid #dbe6e8;vertical-align:top}a{color:#087e76}</style><h1>Local encoder comparison</h1>'''
    first=next(iter(summary['models'].values()))
    page+='<p>'+esc(summary['pairs'])+' AI-labelled development pairs. Cutoffs use '+esc(first['older_pairs'])+' older pairs; their transfer is checked on '+esc(first['newer_pairs'])+' newer pairs. Neither sample is independent human validation.</p><p>Models encode official occupation definitions and exact employer source spans locally. No provider API calls, account changes, employer edits or search-index replacement.</p><p>Whole lists can hide minority roles. Matched-span tests check this separately, but do not establish that a listed activity is performed by the employer.</p><div class="scroll"><table><thead><tr><th>Encoder / evidence view</th><th>Older sample: supported pairs rejected</th><th>Newer sample: supported pairs rejected</th><th>Newer sample: irrelevant pairs rejected</th><th>Newer sample: related / insufficient rejected</th></tr></thead><tbody>'
    for name,values in summary['models'].items():
        for field,result in values['calibration'].items():
            if result['threshold'] is None:
                page+='<tr><td>'+esc(name+' / '+field)+'</td><td colspan="4">Insufficient calibration labels</td></tr>'
                continue
            older=result['training']['rejected'];newer=result['newer_development_sample']['rejected']
            total=lambda sample,label:sample['retained'].get(label,0)+sample['rejected'].get(label,0)
            old_total=total(result['training'],'direct');new_total=total(result['newer_development_sample'],'direct')
            irrelevant=total(result['newer_development_sample'],'irrelevant')
            weak=sum(total(result['newer_development_sample'],label) for label in ['related','insufficient_evidence'])
            page+='<tr>'+''.join('<td>'+esc(value)+'</td>' for value in [name+' / '+field.replace('_',' '),str(older.get('direct',0))+' / '+str(old_total),str(newer.get('direct',0))+' / '+str(new_total),str(newer.get('irrelevant',0))+' / '+str(irrelevant),str(newer.get('related',0)+newer.get('insufficient_evidence',0))+' / '+str(weak)])+'</tr>'
    page+='</tbody></table></div><p>Higher rejection counts are not automatically better: losing supported pairs reduces useful coverage. These checks concern existing returned pairs. They do not measure rerun top-three precision, NDCG or retrieval recall.</p><p>No encoder change or new gate is enabled. A full retrieval comparison and stronger professional evidence are still required before promotion.</p><p><a href="summary.json">All diagnostic scores and cutoffs</a> · <a href="manifest.json">Pinned inputs and model versions</a> · <a href="minilm-pairs.json">MiniLM pair features</a> · <a href="bge-pairs.json">BGE pair features</a></p></html>'
    (Path(folder)/'report.html').write_text(page)


if __name__=='__main__':main()
