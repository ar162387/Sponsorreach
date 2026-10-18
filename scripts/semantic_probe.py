"""Offline full-form semantic comparison; never creates accounts or sends email."""
import argparse
import html
import json
import time
from pathlib import Path

from sponsor_match.config import Settings
from sponsor_match.db import Database
from sponsor_match.evaluate import metrics
from sponsor_match.models import Profile
from sponsor_match.presentation import displayed_channels
from sponsor_match.semantic_search import SemanticMatcher
from sponsor_match.intelligence import digest


def review_packet(rows):
    packet=[]
    for row in rows:
        for position,result in enumerate(row['results'],1):
            signature=digest({'profile':row['profile'],'employer_id':result['employer_id'],'employer_name':result['employer_name'],'explanation':result['explanation'],'channels':result.get('channels',[]),'versions':row['versions'],'position':position})
            packet.append({'profile_id':row['id'],'employer_id':result['employer_id'],'ranking_version':row['versions']['ranking'],'source_model':row['versions'].get('prospect_model'),'register_snapshot':row['versions'].get('snapshot'),'position':position,'profile_hash':digest(row['profile']),'review_hash':signature,'label':'unjudged','explanation_supported':None,'channel_useful':None,'reviewer_type':'human'})
    return packet


def summarize(rows, labels):
    anchors=[row for row in rows if row['variant']=='complete']
    # Existing judgments concern the anchor profession; do not transfer them to
    # multi-intent/synonym profiles or pretend they are independent human review.
    judgments=[{'profile_id':row['id'],'employer_id':label['employer_id'],'label':label['label']}
               for row in anchors for label in labels if label['family']==row['family']]
    rankings={row['id']:row['ranking'] for row in anchors}
    comparisons=[]
    field_sensitivity={}
    for row in rows:
        anchor=next((a for a in anchors if a['family']==row['family']),None)
        if anchor is None:continue
        a,b=anchor['ranking'][:10],row['ranking'][:10]
        comparisons.append({'id':row['id'],'count':row['count'],'same_top3':a[:3]==b[:3],
                            'top10_jaccard':len(set(a)&set(b))/max(1,len(set(a)|set(b)))})
        field=field_sensitivity.setdefault(row['variant'],{'profiles':0,'top3_changed':0,'top10_changed':0,'count_changed':0})
        field['profiles']+=1
        field['top3_changed']+=int(a[:3]!=b[:3])
        field['top10_changed']+=int(a!=b)
        field['count_changed']+=int(row['count']!=anchor['count'])
    return {'ranking_version':rows[0]['versions']['ranking'] if rows else None,
            'profiles':len(rows),'families':len({r['family'] for r in rows}),
            'unique_employers_reached':len({eid for r in rows for eid in r['ranking']}),
            'existing_ai_judgments':len(judgments),'independent_human_judgments':0,
            'anchor_precision_at3':metrics(rankings,judgments,3),
            'anchor_precision_at10':metrics(rankings,judgments,10),
            'comparisons':comparisons,'field_sensitivity':field_sensitivity,'release_ready':False,
            'related_career_retrieval_implemented':False,
            'note':'Unjudged pairs remain unjudged. Existing AI judgments are diagnostic, not independent relevance validation.'}


def report(output,rows,summary):
    esc=lambda value:html.escape(str(value))
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SponsorReach semantic experiment</title><style>body{font:16px/1.5 system-ui;background:#f7f9f8;color:#123e50;max-width:1100px;margin:32px auto;padding:0 20px}article{background:white;border:1px solid #dbe6e8;border-radius:12px;padding:20px;margin:16px 0}summary{cursor:pointer;font-weight:650}li{margin:14px 0}small{color:#526b77}input{padding:10px;width:90%}</style><h1>Semantic matcher · offline experiment</h1>'''
    document+='<p>'+esc(summary['profiles'])+' profiles · '+esc(summary['unique_employers_reached'])+' employers reached. Not promoted to live search.</p><p>Existing AI judgments are diagnostic. New pairs still need independent review. Coverage is not relevance accuracy.</p><p><a href="summary.json">Metrics and form sensitivity</a> · <a href="review-packet.json">Unjudged review packet</a> · <a href="runs.json">All profile inputs and results</a></p><input id="q" aria-label="Filter profiles" placeholder="Filter by role or variant">'
    if (output/'ai-development-review.json').exists():
        review=json.loads((output/'ai-development-review.json').read_text())
        document+='<p>AI development review: '+esc(review['judged_pairs'])+' anchor pairs inspected. '+esc(review['labels'])+'. <a href="ai-development-review.json">Slice metrics and limitations</a> · <a href="ai-anchor-reviews.json">Individual judgments</a>. These are development diagnostics, not held-out or independent human accuracy.</p>'
    packet=review_packet(rows)
    contexts=[{'profile':row['profile'],'employer_name':result['employer_name'],'explanation':result['explanation'],'channels':result.get('channels',[]),'versions':row['versions']}
              for row in rows for result in row['results']]
    (output/'review-packet.json').write_text(json.dumps([{**item,**context,'rank':item['position']} for item,context in zip(packet,contexts)],indent=2))
    packet_index=0
    document+='<p><button id="export">Export my review labels</button> <span id="count"></span></p>'
    for row in rows:
        document+='<article><details><summary>'+esc(row['id'])+' · '+esc(row['count'])+' results</summary><pre style="white-space:pre-wrap">'+esc(json.dumps(row['profile'],indent=2))+'</pre><ol>'
        for result in row['results']:
            document+='<li><strong>'+esc(result['employer_name'])+'</strong><p>'+esc(result['explanation']['text'])+'</p>'
            for source in result['explanation']['sources']:
                document+='<small>'+esc(source['kind'])+' · '+esc(source['excerpt'])+'</small>'
            document+='<p>Recorded contact routes: '+esc(' · '.join(c['label']+': '+c['value'] for c in result.get('channels',[])))+'</p>'
            index=packet_index;packet_index+=1
            options=''.join('<option value="'+value+'">'+esc(value.replace('_',' '))+'</option>' for value in ['unjudged','direct','related','insufficient_evidence','irrelevant','wrong_entity'])
            document+='<p><label>Relevance <select data-review="'+str(index)+'">'+options+'</select></label> <label>Explanation supported? <select data-support="'+str(index)+'"><option value="">Unreviewed</option><option value="yes">Yes</option><option value="no">No</option></select></label> <label>Contact routes useful? <select data-channel="'+str(index)+'"><option value="">Unreviewed</option><option value="yes">Yes</option><option value="no">No</option></select></label></p></li>'
        document+='</ol></details></article>'
    document+='<script>document.querySelector("#q").addEventListener("input",e=>{for(const row of document.querySelectorAll("article"))row.hidden=!row.textContent.toLowerCase().includes(e.target.value.toLowerCase())})</script>'
    document+='<script>const review='+json.dumps(packet).replace('<','\\u003c')+';const storageKey='+json.dumps('sponsorreach-semantic-review:v2:'+digest(packet))+''';
    const allowedLabels=new Set(['unjudged','direct','related','insufficient_evidence','irrelevant','wrong_entity']);
    try{const saved=JSON.parse(localStorage.getItem(storageKey));if(Array.isArray(saved))saved.forEach((s,i)=>{if(review[i]&&s.review_hash===review[i].review_hash&&s.profile_id===review[i].profile_id&&s.employer_id===review[i].employer_id){if(allowedLabels.has(s.label))review[i].label=s.label;for(const field of ['explanation_supported','channel_useful'])if(s[field]===null||typeof s[field]==='boolean')review[i][field]=s[field]}})}catch{}
    function save(){document.querySelector('#count').textContent=review.filter(r=>r.label!=='unjudged').length+' pairs reviewed';try{localStorage.setItem(storageKey,JSON.stringify(review))}catch{}}
    document.querySelectorAll('[data-review]').forEach(el=>{el.value=review[+el.dataset.review].label;el.onchange=()=>{review[+el.dataset.review].label=el.value;save()}});
    document.querySelectorAll('[data-support]').forEach(el=>{const r=review[+el.dataset.support];el.value=r.explanation_supported===true?'yes':r.explanation_supported===false?'no':'';el.onchange=()=>{r.explanation_supported=el.value===''?null:el.value==='yes';save()}});
    document.querySelectorAll('[data-channel]').forEach(el=>{const r=review[+el.dataset.channel];el.value=r.channel_useful===true?'yes':r.channel_useful===false?'no':'';el.onchange=()=>{r.channel_useful=el.value===''?null:el.value==='yes';save()}});
    document.querySelector('#export').onclick=()=>{const link=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(review,null,2)],{type:'application/json'}));link.href=url;link.download='sponsorreach-human-review.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};save();</script></html>'''
    document=document.replace('<title>','<link rel="icon" href="data:,"><title>',1).replace('padding:0 20px}','padding:0 20px;overflow-wrap:anywhere}',1)
    (output/'report.html').write_text(document)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model-folder',required=True)
    parser.add_argument('--profiles',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--all-variants',action='store_true')
    parser.add_argument('--labels')
    args=parser.parse_args()
    settings=Settings.from_env();db=Database(settings.database_url);db.open()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    try:
        matcher=SemanticMatcher(db,settings,args.model_folder)
        cases=json.loads(Path(args.profiles).read_text());rows=[]
        selected=[case for case in cases if args.all_variants or case['variant']=='complete']
        for case in selected:
            start=time.monotonic()
            results,mode,versions=matcher.search(Profile.model_validate(case['profile']))
            employers={e.id:e for e in db.employers([r.employer_id for r in results[:10]])}
            row={key:case[key] for key in ['id','profile','family','variant']}
            row.update(mode=mode,versions=versions,count=len(results),elapsed_ms=round((time.monotonic()-start)*1000,2),
                       results=[{'employer_id':r.employer_id,'employer_name':employers[r.employer_id].name,
                                 'group':r.group,'explanation':r.explanation,'features':r.features,'channels':displayed_channels(employers[r.employer_id])} for r in results[:10]],
                       ranking=[r.employer_id for r in results])
            rows.append(row)
            if case['variant']=='complete' or len(rows)%25==0:
                print(json.dumps({'completed':len(rows),'family':case['family'],'variant':case['variant'],'count':len(results),'top3':[r['employer_name'] for r in row['results'][:3]]}),flush=True)
            # Save progress so a later failed profile does not erase completed work.
            (output/'runs.json').write_text(json.dumps(rows,indent=2))
        labels=json.loads(Path(args.labels).read_text()) if args.labels else []
        summary=summarize(rows,labels)
        (output/'summary.json').write_text(json.dumps(summary,indent=2))
        report(output,rows,summary)
    finally:db.close()


if __name__=='__main__':main()
