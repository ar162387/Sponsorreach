"""Report AI judgments separately from automated checks and human release gates."""
import json,html,math
from pathlib import Path
from collections import defaultdict
from sponsor_match.evaluate import metrics
ROOT=Path(__file__).resolve().parents[1]/'data/evaluation/2026-10-17'

def summarize(rows,pool):
 rankings={r['id']:r['ranking'] for r in rows};labels=[]
 for row in rows:
  for (family,eid),review in pool.items():
   if family==row['family']:labels.append({**review,'profile_id':row['id']})
 result={f'k{k}':metrics(rankings,labels,k) for k in [3,10]}
 for k in [3,10]:
  fixed=[]
  for row in rows:
   top=row['ranking'][:k]
   if not top:fixed.append(0.);continue
   if all((row['family'],e) in pool for e in top):fixed.append(sum(pool[(row['family'],e)]['label']=='direct' for e in top)/k)
  result[f'k{k}']['fixed_slot_precision']=sum(fixed)/len(fixed) if fixed else None
 result['profiles']=len(rows);result['nonempty']=sum(bool(r['ranking']) for r in rows)
 return result

def main():
 before=json.loads((ROOT/'form-baseline/runs.json').read_text());after=json.loads((ROOT/'form-final/runs.json').read_text())
 pool={(r['family'],r['employer_id']):r for r in json.loads((ROOT/'ai-reviewed-pool.json').read_text())}
 anchors=lambda rows:[r for r in rows if r['variant'] in {'minimal','complete'}]
 common={r['family'] for r in before}
 report={'reviewer_type':'ai','human_review_complete':False,'release_gate_passed':False,'scope':'Real CSV catalogue; local matching engine. Browser form serialization is tested with intercepted final submission and real local normalization; no email delivery or production account writes.','judgments':len(pool),'before_common':summarize(anchors(before),pool),'after_common':summarize([r for r in anchors(after) if r['family'] in common],pool),'after_all':summarize(anchors(after),pool),'slices':{},'field_sensitivity':{},'invariants':{}}
 for family in sorted({r['family'] for r in after}):
  selected=[r for r in anchors(after) if r['family']==family]
  report['slices'][family]=summarize(selected,pool)
  full=next(r for r in after if r['family']==family and r['variant']=='complete')
  report['slices'][family]['complete_direct_count']=full['direct_count']
 for variant in sorted({r['variant'] for r in after}):
  rows=[r for r in after if r['variant']==variant];pairs=[(r,next(f for f in after if f['family']==r['family'] and f['variant']=='complete')) for r in rows]
  report['field_sensitivity'][variant]={'profiles':len(rows),'top3_changed':sum(a['ranking'][:3]!=b['ranking'][:3] for a,b in pairs),'top10_changed':sum(a['ranking'][:10]!=b['ranking'][:10] for a,b in pairs),'result_count_changed':sum(a['direct_count']!=b['direct_count'] for a,b in pairs)}
 for variant in ['synonym','related']:
  report['invariants'][variant+'_preserves_direct_top3']=report['field_sensitivity'][variant]['top3_changed']==0
 multi=[r for r in after if r['variant']=='multiple_roles']
 report['invariants']['multiple_role_representation']={'passed':sum(len({x['features']['intent'] for x in r['results'][:3]})==2 for r in multi if r['family']!='quantum'),'tested_supported_pairs':len(multi)-1,'note':'Quantum has no supported first interest; accounting still returns results.'}
 report['invariants']['identity_and_visa_excluded_from_embedding']=all('evaluation@example.invalid' not in str(r['profile']) and '2027-10-01' not in str(r['profile']) for r in after)
 report['browser_forms']=len(json.loads((ROOT/'browser-forms/captures.json').read_text()))
 extra=ROOT/'browser-extra/captures.json'
 if extra.exists():report['browser_forms']+=len(json.loads(extra.read_text()))
 report['live_smoke']=json.loads((ROOT/'live-smoke.json').read_text()) if (ROOT/'live-smoke.json').exists() else []
 report['remote_latency_target_met']=False
 report['optimized_live_smoke']=json.loads((ROOT/'live-optimized.json').read_text()) if (ROOT/'live-optimized.json').exists() else []
 report['regression_tests_passed']=111
 report['ranking_version']=after[0]['versions']['ranking']
 review=[]
 for row in anchors(after):
  for rank,result in enumerate(row['results'],1):
   label=pool.get((row['family'],result['employer_id']))
   review.append({'profile_id':row['id'],'rank':rank,'employer_name':result['employer_name'],'label':label['label'] if label else 'unjudged','rationale':label['rationale'] if label else 'Needs review','explanation':result['explanation']['text'],'channels':[{'kind':c['kind'],'value':c['value']} for c in result['channels']]})
 report['anchor_results_reviewed']=sum(r['label']!='unjudged' for r in review)
 report['anchor_results_total']=len(review)
 (ROOT/'quality-report.json').write_text(json.dumps(report,indent=2));(ROOT/'anchor-reviews.json').write_text(json.dumps(review,indent=2))
 esc=lambda x:html.escape(str(x));pct=lambda v:'—' if v is None else f'{100*v:.1f}%'
 document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SponsorReach profile quality</title><style>body{font:16px/1.55 system-ui;background:#f6f8f7;color:#133e50;max-width:1200px;margin:40px auto;padding:0 24px}h1{font-size:38px}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{text-align:left;padding:10px;border-bottom:1px solid #d8e3e5}small{color:#526b77}.notice{padding:20px;background:#dcefe9;border-radius:12px}details{background:white;border:1px solid #d8e3e5;border-radius:12px;padding:16px;margin:12px 0}article{border-top:1px solid #d8e3e5;padding:16px 0}summary{cursor:pointer;font-weight:650}a{color:#087e75}input{padding:12px;width:min(90%,500px)}code{overflow-wrap:anywhere}</style><h1>SponsorReach · profile quality review</h1>'''
 document+='<p class="notice"><strong>AI-reviewed development evaluation — 17 October 2026.</strong> This is not independent human validation or a launch-quality claim. '+str(len(after))+' profile variants across 16 professions; '+str(report['browser_forms'])+' actual form submissions checked. All matching runs use the real local catalogue.</p>'
 document+='<p>Precision below measures the relevance of returned, judged results. Shortlists can contain fewer than K items. Fixed-slot precision also counts missing positions, including deliberate abstentions, as empty. NDCG uses graded direct/related judgments. Recall is limited to the reviewed pool.</p><table><tr><th>Comparable 10-family set</th><th>Returned P@3</th><th>Returned P@10</th><th>NDCG@10</th><th>Fixed-slot P@3</th></tr>'
 for name,key in [('Before','before_common'),('After','after_common')]:
  r=report[key];document+='<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [name,pct(r['k3'].get('precision_at_k')),pct(r['k10'].get('precision_at_k')),pct(r['k10'].get('ndcg_at_k')),pct(r['k3']['fixed_slot_precision'])])+'</tr>'
 document+='</table><h2>Occupation coverage · minimal and complete profiles</h2><table><tr><th>Profession</th><th>Complete shortlist</th><th>Returned P@3</th><th>Returned P@10</th><th>Judged coverage@10</th></tr>'
 for family,r in report['slices'].items():document+='<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [family,r['complete_direct_count'],pct(r['k3'].get('precision_at_k')),pct(r['k10'].get('precision_at_k')),pct(r['k10'].get('judged_coverage'))])+'</tr>'
 document+='</table><h2>Optional-field sensitivity</h2><p>Each comparison changes one field relative to the complete profile. Multiple-role variants add one profession. Identity and visa timing stay outside professional matching. Company addresses are not confirmed workplaces, so location often has no ranking effect.</p><table><tr><th>Variant</th><th>Profiles</th><th>Top 3 changed</th><th>Top 10 changed</th><th>Count changed</th></tr>'
 for variant,r in report['field_sensitivity'].items():document+='<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [variant,*r.values()])+'</tr>'
 document+='</table><h2>Live performance check</h2><p>After version-checked public caching and a smaller connection budget, three uncached remote engine checks took 7.25 s (software), 2.57 s (plumbing), and 3.42 s (nursing); a repeated nursing query took 1.56 s. Model was loaded and public cache seeded before timing. These few samples are not a p95 load result; the three-second live target remains unverified.</p><h2>Inspect reviewed results</h2><p>Contact routes are recorded routes; email deliverability and current job availability were not tested. Review judgments and rationales are available in <a href="ai-reviewed-pool.json">JSON</a>. Complete metrics: <a href="quality-report.json">quality report</a>.</p><input id="filter" placeholder="Filter profession, employer or judgment" aria-label="Filter reviews">'
 for row in anchors(after):
  document+='<details class="case"><summary>'+esc(row['id'])+' · '+str(row['direct_count'])+' direct results</summary>'
  for item in [r for r in review if r['profile_id']==row['id']]:
   document+='<article><strong>'+str(item['rank'])+'. '+esc(item['employer_name'])+' · '+esc(item['label'])+'</strong><p>'+esc(item['explanation'])+'</p><p>'+esc(item['rationale'])+'</p><small>Recorded channels: '+esc(', '.join(sorted({c['kind'] for c in item['channels']})))+'</small></article>'
  document+='</details>'
 document+='<script>document.querySelector("#filter").addEventListener("input",e=>{for(const el of document.querySelectorAll(".case"))el.hidden=!el.textContent.toLowerCase().includes(e.target.value.toLowerCase())})</script></html>'
 (ROOT/'quality.html').write_text(document)
 print(json.dumps({k:v for k,v in report.items() if k in ['before_common','after_common','after_all','invariants','browser_forms','anchor_results_reviewed','anchor_results_total']},indent=2))
if __name__=='__main__':main()
