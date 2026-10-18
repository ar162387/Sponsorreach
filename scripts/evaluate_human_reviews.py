"""Score explicit human exports against the exact frozen review packet.

No DB/auth/network access. Self-reported browser reviews are not a held-out
release audit; wrong-version, changed-source and conflicting labels fail closed.
"""
import argparse,json
from pathlib import Path
from collections import Counter
from sponsor_match.intelligence import digest
from sponsor_match.evaluate import metrics
from semantic_probe import review_packet

LABELS={'unjudged','direct','related','insufficient_evidence','irrelevant','wrong_entity'}


def score_reviews(rows,reviews):
    if not rows or not isinstance(reviews,list):raise ValueError('Provide completed matrix rows and a review array')
    if len({row['id'] for row in rows})!=len(rows):raise ValueError('Matrix profile IDs must be unique')
    expected={(r['profile_id'],r['employer_id']):r for r in review_packet(rows)}
    contexts={(row['id'],result['employer_id']):{'profile':row['profile'],'employer_name':result['employer_name'],'explanation':result['explanation'],'channels':result.get('channels',[]),'versions':row['versions']} for row in rows for result in row['results']}
    accepted={}
    for item in reviews:
        if not isinstance(item,dict):raise ValueError('Each review must be an object')
        pair=(item.get('profile_id'),item.get('employer_id'));current=expected.get(pair)
        if not current or item.get('review_hash')!=current['review_hash']:raise ValueError('Review does not describe this exact profile, evidence and version; use its original report or review again')
        if any(item.get(field)!=current[field] for field in ['ranking_version','source_model','register_snapshot','position','profile_hash']):raise ValueError('Review metadata does not describe its frozen review packet')
        if any(field in item and item[field]!=value for field,value in contexts[pair].items()) or ('rank' in item and item['rank']!=current['position']):raise ValueError('Offline review context changed; use the original frozen context')
        if item.get('reviewer_type')!='human':raise ValueError('AI judgments cannot be imported as human reviews')
        if item.get('label') not in LABELS:raise ValueError('Unknown relevance judgment')
        for field in ['explanation_supported','channel_useful']:
            if item.get(field) is not None and type(item[field]) is not bool:raise ValueError('Review flags must be boolean or unreviewed')
        value={**current,'label':item['label'],'explanation_supported':item.get('explanation_supported'),'channel_useful':item.get('channel_useful')}
        if pair in accepted and accepted[pair]!=value:raise ValueError('Conflicting reviews require adjudication')
        accepted[pair]=value
    labels=list(accepted.values());judged=[r for r in labels if r['label']!='unjudged']
    rankings={r['id']:r['ranking'] for r in rows}
    results={}
    for k in [3,10]:
        result=metrics(rankings,labels,k);result['pooled_recall_at_200']=None
        results['precision_at'+str(k)]=result
    support=[r['explanation_supported'] for r in labels if r['explanation_supported'] is not None]
    channels=[r['channel_useful'] for r in labels if r['channel_useful'] is not None]
    return {'review_packet_hash':digest(review_packet(rows)),'ranking_versions':sorted({r['versions']['ranking'] for r in rows}),'source_models':sorted({r['versions'].get('prospect_model') or 'unknown' for r in rows}),'reviewer_type':'human_self_reported','development_set':True,'reviewer_identity_independently_verified':False,'judged_pairs':len(judged),'labels':dict(Counter(r['label'] for r in judged)),'metrics':results,'explanation_reviews':len(support),'explanation_support_rate':sum(support)/len(support) if support else None,'channel_reviews':len(channels),'channel_usefulness_rate':sum(channels)/len(channels) if channels else None,'wrong_entity_rate':sum(r['label']=='wrong_entity' for r in judged)/len(judged) if judged else None,'recall_measured':False,'release_ready':False,'note':'Exact-version self-reported human review of a development sample. Unjudged pairs stay unjudged; missing support/channel marks are unknown. Current-head reviews cannot establish retrieval recall, and this is not held-out release validation.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--matrix',required=True);parser.add_argument('--reviews',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();rows=json.loads((Path(args.matrix)/'runs.json').read_text());reviews=json.loads(Path(args.reviews).read_text())
    result=score_reviews(rows,reviews);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()
