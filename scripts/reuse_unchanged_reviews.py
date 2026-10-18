"""Reuse relevance judgments only for identical profile/evidence pairs.

New or changed pairs remain unjudged. This does not create human judgments,
convert AI reviews to human reviews, or establish held-out accuracy.
"""
import argparse,json
from collections import Counter
from pathlib import Path
from sponsor_match.evaluate import metrics
from sponsor_match.intelligence import digest
from semantic_probe import summarize,report


def evidence_signature(result):
    explanation=result['explanation']
    return digest({'basis':explanation['basis'],'sources':explanation['sources'],'claim_ids':explanation['claim_ids'],'evidence_ids':explanation['evidence_ids']})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before',required=True);parser.add_argument('--after',required=True)
    parser.add_argument('--depth',type=int,choices=[3,10],required=True)
    args=parser.parse_args();before,after=Path(args.before),Path(args.after)
    previous={r['id']:r for r in json.loads((before/'runs.json').read_text())}
    labels={(r['profile_id'],r['employer_id']):r for r in json.loads((before/'ai-anchor-reviews.json').read_text())}
    if any(r.get('reviewer_type')!='ai' for r in labels.values()):raise ValueError('This tool accepts explicitly AI-labeled development reviews only')
    rows=json.loads((after/'runs.json').read_text());retained=[];unjudged=[]
    if not rows:raise ValueError('No completed profiles')
    versions={(r['versions']['ranking'],r['versions']['prospect_model']) for r in rows}
    if len(versions)!=1:raise ValueError('Mixed experiment versions')
    for row in rows:
        if row['variant']!='complete':continue
        old=previous.get(row['id'])
        if old is None or row['profile']!=old['profile']:raise ValueError('Profile changed; re-review separately')
        old_results={r['employer_id']:r for r in old['results']}
        for result in row['results'][:args.depth]:
            label=labels.get((row['id'],result['employer_id']));old_result=old_results.get(result['employer_id'])
            if label and old_result and evidence_signature(result)==evidence_signature(old_result):
                retained.append({**label,'ranking_version':row['versions']['ranking'],'reused_from':before.name,'unchanged_evidence_hash':evidence_signature(result)})
            else:unjudged.append({'profile_id':row['id'],'employer_id':result['employer_id'],'employer_name':result['employer_name'],'label':'unjudged','reason':'new_or_changed_evidence_pair'})
    (after/'ai-anchor-reviews.json').write_text(json.dumps(retained,indent=2))
    (after/'new-review-pairs.json').write_text(json.dumps(unjudged,indent=2))
    rankings={r['id']:r['ranking'] for r in rows if r['variant']=='complete'}
    quality={'ranking_version':rows[0]['versions']['ranking'],'source_model':rows[0]['versions']['prospect_model'],'reviewer_type':'ai','development_set':True,'independent_human_reviews':0,'judged_pairs':len(retained),'unjudged_pairs':len(unjudged),'labels':dict(Counter(r['label'] for r in retained)),'reused_from':before.name,'recall_measured':False,'release_ready':False,'note':'Existing AI development judgments reused only for unchanged profiles and evidence. New/changed pairs remain unjudged. Not independent human or held-out validation.'}
    summary=summarize(rows,retained)
    for depth in [3,10]:
        value=metrics(rankings,retained,depth) if depth<=args.depth else {'status':'not_evaluated','reason':'Only returned top-three pairs were judged.'}
        if depth<=args.depth:value['pooled_recall_at_200']=None
        quality['precision_at'+str(depth)]=value
        summary['anchor_precision_at'+str(depth)]=value
    (after/'ai-development-review.json').write_text(json.dumps(quality,indent=2))
    (after/'summary.json').write_text(json.dumps(summary,indent=2))
    for name in ['forms.json','selection.json']:
        if (before/name).exists():(after/name).write_bytes((before/name).read_bytes())
    report(after,rows,summary)
    print(json.dumps({'judged':len(retained),'unjudged':len(unjudged),'labels':quality['labels'],'precision_at3':quality['precision_at3']['precision_at_k']}))


if __name__=='__main__':main()
