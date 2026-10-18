"""Offline NLI feasibility probe. Never changes the live matcher or sends profiles."""
import argparse,json,time
from pathlib import Path
import torch
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer,AutoModelForSequenceClassification

MODEL='cross-encoder/nli-deberta-v3-small'
REVISION='fa2804872c3b4bd748f38c0185cc85775361e735'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runs',required=True);parser.add_argument('--labels',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    root=snapshot_download(MODEL,revision=REVISION,allow_patterns=['model.safetensors','config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','added_tokens.json','spm.model'])
    torch.set_num_threads(2)
    tokenizer=AutoTokenizer.from_pretrained(root,local_files_only=True,trust_remote_code=False)
    model=AutoModelForSequenceClassification.from_pretrained(root,local_files_only=True,use_safetensors=True,trust_remote_code=False).eval()
    print(json.dumps({'model':MODEL,'revision':REVISION,'labels':model.config.id2label}),flush=True)
    rows=json.loads(Path(args.runs).read_text());labels={(r['profile_id'],r['employer_id']):r['label'] for r in json.loads(Path(args.labels).read_text())}
    pairs=[];meta=[]
    for row in rows:
        if row['variant']!='complete':continue
        role=row['profile']['role_intents'][0]['raw_label']
        for result in row['results']:
            explanation=result['explanation'];source=explanation['sources'][0]
            if explanation['basis']=='historical_role':premise='This employer previously recorded the following job title: '+', '.join(source['matched_spans'])
            else:premise="This employer's reported business activities or professional functions are: "+source['excerpt']
            hypothesis='The employer has evidence of professional work as a '+role.lower()+'.'
            pairs.append((premise,hypothesis));meta.append({'profile_id':row['id'],'employer_id':result['employer_id'],'employer_name':result['employer_name'],'label':labels.get((row['id'],result['employer_id']),'unjudged'),'premise':premise,'hypothesis':hypothesis})
    started=time.monotonic()
    with torch.inference_mode():
        for start in range(0,len(pairs),8):
            batch=pairs[start:start+8]
            encoded=tokenizer([p[0] for p in batch],[p[1] for p in batch],padding=True,truncation='only_first',max_length=384,return_tensors='pt')
            probabilities=torch.softmax(model(**encoded).logits,dim=1).tolist()
            for row,scores in zip(meta[start:start+8],probabilities):row['scores']=dict(zip(['contradiction','entailment','neutral'],scores));row['predicted']=max(row['scores'],key=row['scores'].get)
    summary={'model':MODEL,'revision':REVISION,'pairs':len(meta),'elapsed_seconds':round(time.monotonic()-started,2),'model_card':'https://huggingface.co/'+MODEL,'promoted':False,'note':'General NLI feasibility only; model confidence is not professional relevance probability.'}
    for label in sorted({r['label'] for r in meta}):
        selected=[r for r in meta if r['label']==label];summary[label]={'pairs':len(selected),'entailed':sum(r['predicted']=='entailment' for r in selected)}
    (output/'predictions.json').write_text(json.dumps(meta,indent=2));(output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
