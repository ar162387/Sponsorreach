"""Offline relevance debugger: freeze runs, review pooled results, score and compare."""
import argparse
import json
from pathlib import Path
from sponsor_match.evaluation_lab import freeze, score, agreement


def render_issues(frozen, result, path):
    import html
    from urllib.parse import quote
    esc=lambda v:html.escape(str(v))
    link=lambda pid:'<a href="report.html#'+quote(pid,safe='')+'">'+esc(pid)+'</a>'
    fmt=lambda v:'unjudged' if v is None else f'{v:.1%}'
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SponsorReach quality failures</title><style>body{font:15px/1.5 system-ui;color:#163c49;background:#f3f7f6;max-width:1250px;margin:30px auto;padding:0 24px}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{padding:12px;border-bottom:1px solid #d9e5e6;text-align:left;vertical-align:top}a{color:#087e78}small{color:#58727b}section{padding:20px;background:white;border-radius:12px;margin:18px 0}</style><h1>Search-quality failure console</h1><p><a href="report.html">Open the review lab</a></p>'''
    document+='<p>Review type: <strong>'+esc(result['reviewer_type'])+'</strong> · '+str(result['judged_pairs'])+' judged pairs. Development findings; no automatic release approval.</p><h2>Where the reviewed searches differ</h2><table><tr><th>Search</th>'
    for name in result['runs']:document+='<th>'+esc(name)+'<br><small>P@3 / task P@3</small></th>'
    document+='</tr>'
    for pid,profile in frozen['profiles'].items():
        if not any(run['per_query'][pid]['3']['precision_fixed_slots'] is not None for run in result['runs'].values() if pid in run['per_query']):continue
        document+='<tr><td>'+link(pid)+'<br><small>'+esc(' / '.join(r['raw_label'] for r in profile['profile'].get('role_intents',[])))+'</small></td>'
        for run in result['runs'].values():
            values=run['per_query'].get(pid,{}).get('3',{})
            document+='<td>'+fmt(values.get('precision_fixed_slots'))+' / '+fmt(values.get('task_precision_fixed_slots'))+'</td>'
        document+='</tr>'
    document+='</table><h2>Reviewed failures</h2>'
    names={(p['profile_id'],p['employer_id']):p['employer_name'] for p in frozen['packet']}
    for failure in result['review_failures']:
        document+='<section>'+link(failure['profile_id'])+'<h3>'+esc(names[failure['profile_id'],failure['employer_id']])+'</h3><strong>'+esc(failure['failure'])+'</strong><p>'+esc(failure['note'])+'</p></section>'
    document+='<h2>Missing judged-relevant employers</h2><p>This locates misses within the judged pool, not every possible relevant company. A gate rejection may be legitimate; inspect its evidence before changing the gate.</p><table><tr><th>Run / search</th><th>Employer</th><th>Stage</th><th>Gate reason</th></tr>'
    for issue in result['diagnostics']:
        document+='<tr><td>'+esc(issue['run'])+'<br>'+link(issue['profile_id'])+'</td><td>'+esc(names.get((issue['profile_id'],issue['employer_id']),issue['employer_id']))+'</td><td>'+esc(issue['failure'])+'</td><td>'+esc(issue.get('gate_reason') or '')+'</td></tr>'
    path.write_text(document+'</table></html>')


def render(frozen, path, initial_reviews=None):
    # The CLI snapshot retains complete traces. The browser shares repeated
    # employer evidence instead of downloading the same record for every query.
    from sponsor_match.intelligence import digest
    evidence={};packet=[]
    for pair in frozen['packet']:
        contexts={}
        for name,context in pair['contexts'].items():
            source={k:context[k] for k in ['claims','channels']};reference=digest(source);evidence[reference]=source
            contexts[name]={k:v for k,v in context.items() if k not in source}|{'evidence_ref':reference}
        packet.append({**pair,'contexts':contexts})
    runs={name:[{k:v for k,v in row.items() if k not in {'retrieval_ids','branch_ids','gate_rejections'}} for row in rows] for name,rows in frozen['runs'].items()}
    data=json.dumps({**frozen,'packet':packet,'runs':runs,'evidence':evidence},separators=(',',':')).replace('<','\\u003c')
    template='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>SponsorReach relevance lab</title>
<style>body{font:15px/1.55 system-ui;background:#f3f7f6;color:#163c49;max-width:1240px;margin:32px auto;padding:0 24px}h1{font-size:38px;margin-bottom:0}h2{margin-bottom:8px}small,.muted{color:#58727b}section,article{background:white;border:1px solid #d9e5e6;border-radius:14px;padding:20px;margin:14px 0}button,select,input{font:inherit;border:1px solid #abc3c8;border-radius:7px;padding:8px;background:white;color:inherit}button{cursor:pointer}.primary{background:#087e78;color:white;border:0}blockquote{border-left:3px solid #08a194;padding:8px 16px;margin:12px 0;background:#f3f8f7}pre{white-space:pre-wrap;overflow-wrap:anywhere}.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #e3ecec;text-align:left}.notice{background:#e5f2ef;padding:16px;border-radius:8px}.badge{border-radius:20px;background:#e7f4f1;padding:4px 10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:700px){.grid{grid-template-columns:1fr}}a{color:#087e78}textarea{width:100%;min-height:55px;box-sizing:border-box;font:inherit;border:1px solid #abc3c8;border-radius:6px}label{display:block;margin:8px 0}summary{cursor:pointer}#progress{font-weight:600}</style>
<header><small>SPONSORREACH / SEARCH QUALITY</small><h1>Relevance lab</h1><p>Inspect the company evidence. Judge the fit. Find which searches need fixing.</p><a href="issues.html">Open the failure console</a></header>
<p class="notice">This is a private, local development report. Internal ranking scores are ordering signals, not accuracy or sponsorship probabilities. Reviews are blinded to system name, score and rank. Unreviewed results stay unknown. AI reviews remain development diagnostics.</p>
<section><h2>Paired scoreboard</h2><p>Uses the same fully judged searches across all compared runs for each metric. Query counts can differ between metrics. Updates from your selected review type. P@K uses K fixed preview/list slots, including unfilled slots. NDCG needs the entire pooled query judged. Coverage and empty-result counts remain visible.</p><div id="board"></div><small>Development sample; no automatic release approval. Run the CLI scorer for per-query/family metrics, paired bootstrap intervals and a machine-readable failure list.</small></section>
<section><div class="toolbar"><label>Reviewer <input id="reviewer" placeholder="Your reviewer ID"></label><label>Review type <select id="kind"><option value="human">Human review</option><option value="ai_development">AI development review</option></select></label><button class="primary" id="export">Export reviews</button><label>Import reviews <input id="import" type="file" accept="application/json"></label></div><p id="progress"></p><p id="message" role="status"></p></section>
<section><div class="toolbar"><input id="filter" placeholder="Search roles, skills or profile IDs" aria-label="Filter searches"><select id="query" aria-label="Select search"></select><button id="previous">Previous</button><button id="next">Next</button></div><div id="profile"></div></section><div id="pairs"></div>
<script id="dataset" type="application/json">DATASET</script><script>
const f=JSON.parse(document.querySelector('#dataset').textContent), key='sr-relevance-lab:'+f.hash, esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
for(const pair of f.packet)for(const context of Object.values(pair.contexts))Object.assign(context,f.evidence[context.evidence_ref]);
const fields=['profile_id','employer_id','review_hash','label','reviewer_type','reviewer_id','failure','note','explanation_supported','channel_useful','task_fit'];
let reviews=f.packet.map(p=>Object.fromEntries(fields.map(k=>[k,p[k]])));for(const r of STARTING_REVIEWS){const i=reviews.findIndex(p=>p.review_hash===r.review_hash);if(i>=0)Object.assign(reviews[i],r);}let queries=Object.keys(f.profiles), selected=queries[0];try{const requested=decodeURIComponent(location.hash.slice(1));if(f.profiles[requested])selected=requested;}catch{}
try{const old=JSON.parse(localStorage.getItem(key));if(Array.isArray(old))for(const r of old){const i=reviews.findIndex(p=>p.review_hash===r.review_hash);if(i>=0)Object.assign(reviews[i],Object.fromEntries(fields.map(k=>[k,r[k]])));}}catch{}
const labels=['unjudged','direct','related','insufficient_evidence','irrelevant','wrong_entity'];const failures=['','wrong_entity','wrong_profession','weak_evidence','skill_ignored','role_ambiguity','channel_issue','explanation_issue','ranking_order','other'];
function eligible(r){return r.label!=='unjudged'&&r.reviewer_type===document.querySelector('#kind').value;}
function save(){localStorage.setItem(key,JSON.stringify(reviews));update();}
function update(){document.querySelector('#progress').textContent=reviews.filter(eligible).length+' / '+reviews.length+' pooled pairs reviewed in this review type';let table='<table><tr><th>Run</th><th>P@3</th><th>P@10</th><th>Task P@3</th><th>NDCG@10</th><th>Empty / profiles</th><th>Judged pool</th></tr>';
for(const [name,rows] of Object.entries(f.runs)){let values={3:[],10:[]},taskPs=[],nds=[],judged=0,total=0;for(const row of rows){const pool=f.packet.filter(p=>p.profile_id===row.id), labs=new Map(reviews.filter(r=>r.profile_id===row.id&&eligible(r)).map(r=>[r.employer_id,r.label]));judged+=labs.size;total+=pool.length;const taskReviews=new Map(reviews.filter(r=>r.profile_id===row.id&&eligible(r)).map(r=>[r.employer_id,r.task_fit]));const taskTop=row.ranking.slice(0,3);if(labs.size&&f.profiles[row.id].profile.skills?.length&&Object.values(f.runs).every(rs=>{const other=rs.find(x=>x.id===row.id);return other.status==='completed'&&other.ranking.slice(0,3).every(e=>labs.has(e)&&(labs.get(e)!=='direct'||taskReviews.get(e)));}))taskPs.push(taskTop.filter(e=>labs.get(e)==='direct'&&taskReviews.get(e)==='specific').length/3);for(const k of [3,10]){const top=row.ranking.slice(0,k);if(labs.size&&Object.values(f.runs).every(rs=>{const other=rs.find(x=>x.id===row.id);return other.status==='completed'&&other.ranking.slice(0,k).every(e=>labs.has(e));}))values[k].push(top.filter(e=>labs.get(e)==='direct').length/k);}if(pool.every(p=>labs.has(p.employer_id))){const gain=l=>l==='direct'?7:l==='related'?1:0, ideal=pool.map(p=>gain(labs.get(p.employer_id))).sort((a,b)=>b-a).slice(0,10).reduce((s,g,i)=>s+g/Math.log2(i+2),0),dcg=row.ranking.slice(0,10).reduce((s,e,i)=>s+gain(labs.get(e))/Math.log2(i+2),0);if(ideal)nds.push(dcg/ideal);}}
const fmt=a=>a.length?(100*a.reduce((s,x)=>s+x,0)/a.length).toFixed(1)+'% <small>('+a.length+' queries)</small>':'unjudged';table+='<tr><td>'+esc(name)+'</td><td>'+fmt(values[3])+'</td><td>'+fmt(values[10])+'</td><td>'+fmt(taskPs)+'</td><td>'+fmt(nds)+'</td><td>'+rows.filter(r=>!r.ranking.length).length+' / '+rows.length+'</td><td>'+judged+' / '+total+'</td></tr>';}
document.querySelector('#board').innerHTML=table+'</table>';}
function options(values,selected,emptyLabel='No failure marked'){return values.map(v=>'<option value="'+v+'" '+(v===selected?'selected':'')+'>'+esc(v.replaceAll('_',' ')||emptyLabel)+'</option>').join('');}
function render(){const p=f.profiles[selected];if(!p){document.querySelector('#profile').textContent='No profiles match this filter.';document.querySelector('#pairs').innerHTML='';return;}document.querySelector('#profile').innerHTML='<h2>'+esc(selected)+'</h2><small>'+esc(p.family)+' · '+esc(p.split)+'</small><pre>'+esc(JSON.stringify(p.profile,null,2))+'</pre>';
let out='';const pairs=f.packet.map((p,i)=>[p,i]).filter(([p])=>p.profile_id===selected).sort((a,b)=>a[0].review_hash.localeCompare(b[0].review_hash));for(const [pair,i] of pairs){const r=reviews[i];let contexts='';const presentations=Object.values(pair.contexts);if(parseInt(pair.review_hash.slice(0,2),16)%2)presentations.reverse();presentations.forEach((c,j)=>{contexts+='<div><strong>Evidence presentation '+String.fromCharCode(65+j)+'</strong><p>'+esc(c.explanation.text)+'</p>'+(c.explanation.sources||[]).map(s=>'<blockquote>'+esc(s.excerpt)+'</blockquote>').join('')+'<p><small>Recorded contact routes</small><br>'+(c.channels||[]).map(ch=>esc(ch.label||ch.kind)+': '+esc(ch.value)).join('<br>')+'</p></div>';});const sourceClaims=Array.from(new Map(Object.values(pair.contexts).flatMap(c=>c.claims||[]).filter(c=>c.attribution==='accepted').map(c=>[c.id,c])).values());const sourceContext='<details><summary>Complete recorded activity and role context</summary>'+sourceClaims.map(c=>'<blockquote><small>'+esc(c.kind)+'</small><br>'+esc(c.text)+'</blockquote>').join('')+'</details>';const technical='<details><summary>Technical trace (reveals versions, ranks and internal ordering scores)</summary><pre>'+esc(JSON.stringify(Object.fromEntries(Object.entries(pair.contexts).map(([name,c])=>[name,{rank:c.rank,ordering_score:c.score,features:c.features,versions:c.versions}])),null,2))+'</pre><small>Ordering scores are not accuracy or sponsorship probabilities.</small></details>';out+='<article data-index="'+i+'"><h2>'+esc(pair.employer_name)+'</h2><div class="grid">'+contexts+'</div>'+sourceContext+technical+'<div class="toolbar"><label>Professional relevance <select data-field="label">'+options(labels,r.label)+'</select></label><label>Failure reason <select data-field="failure">'+options(failures,r.failure||'')+'</select></label><label>Explicit task fit <select data-field="task_fit">'+options(['','specific','broad','contradicted'],r.task_fit||'','Unreviewed')+'</select></label></div><label>Why? Cite the task or evidence that supports your decision<textarea data-field="note">'+esc(r.note)+'</textarea></label><div class="toolbar">'+['explanation_supported','channel_useful'].map(field=>'<label>'+esc(field==='explanation_supported'?'All displayed explanations supported?':'Contact routes useful?')+' <select data-field="'+field+'"><option value="">Unreviewed</option><option value="true" '+(r[field]===true?'selected':'')+'>Yes</option><option value="false" '+(r[field]===false?'selected':'')+'>No</option></select></label>').join('')+'</div><small>Review evidence, not the apparent prestige of the employer. Related work is distinct from direct fit.</small></article>';}
document.querySelector('#pairs').innerHTML=out||'<p>No results were returned by the pooled runs for this search. This needs a coverage investigation, not invented relevance labels.</p>';
document.querySelectorAll('[data-field]').forEach(el=>el.onchange=()=>{const id=document.querySelector('#reviewer').value.trim();if(!id){document.querySelector('#message').textContent='Enter a reviewer ID before recording judgments.';render();return;}const r=reviews[+el.closest('article').dataset.index],field=el.dataset.field;r[field]=field==='task_fit'?(el.value||null):['explanation_supported','channel_useful'].includes(field)?el.value===''?null:el.value==='true':el.value;r.reviewer_id=id;r.reviewer_type=document.querySelector('#kind').value;save();});}
function filter(){const text=document.querySelector('#filter').value.toLowerCase();queries=Object.keys(f.profiles).filter(id=>(id+JSON.stringify(f.profiles[id].profile)).toLowerCase().includes(text));if(!queries.includes(selected))selected=queries[0];document.querySelector('#query').innerHTML=queries.map(id=>'<option '+(id===selected?'selected':'')+'>'+esc(id)+'</option>').join('');render();}
document.querySelector('#query').onchange=e=>{selected=e.target.value;render();};document.querySelector('#filter').oninput=filter;document.querySelector('#kind').onchange=()=>{update();render();};for(const [id,d]of[['previous',-1],['next',1]])document.querySelector('#'+id).onclick=()=>{selected=queries[Math.max(0,Math.min(queries.length-1,queries.indexOf(selected)+d))];filter();};
document.querySelector('#export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(reviews,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='sponsorreach-relevance-reviews.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.querySelector('#import').onchange=async e=>{try{const rows=JSON.parse(await e.target.files[0].text());if(!Array.isArray(rows)||rows.some(r=>!reviews.some(p=>p.review_hash===r.review_hash)||!labels.includes(r.label)))throw Error('Wrong packet or invalid labels');for(const r of rows){const i=reviews.findIndex(p=>p.review_hash===r.review_hash);reviews[i]=Object.fromEntries(fields.map(k=>[k,r[k]]));}save();render();document.querySelector('#message').textContent='Imported reviews. CLI validation remains authoritative.';}catch(err){document.querySelector('#message').textContent=String(err);}};filter();update();
</script></html>'''
    path.write_text(template.replace('STARTING_REVIEWS',json.dumps(initial_reviews or []).replace('<','\\u003c')).replace('DATASET',data))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    build=sub.add_parser('build');build.add_argument('--run',action='append',required=True,help='name=/path/to/runs.json');build.add_argument('--depth',type=int,default=10);build.add_argument('--output',required=True)
    scorer=sub.add_parser('score');scorer.add_argument('--benchmark',required=True);scorer.add_argument('--reviews',required=True);scorer.add_argument('--reviewer-type',choices=['human','ai_development'],default='human');scorer.add_argument('--split');scorer.add_argument('--output',required=True)
    agree=sub.add_parser('agreement');agree.add_argument('--benchmark',required=True);agree.add_argument('--first',required=True);agree.add_argument('--second',required=True);agree.add_argument('--output',required=True)
    sample=sub.add_parser('sample');sample.add_argument('--onboarding',default='data/onboarding');sample.add_argument('--occupations',type=int,default=80);sample.add_argument('--seed',default='sponsorreach-eval-1');sample.add_argument('--output',required=True)
    args=parser.parse_args();read=lambda p:json.loads(Path(p).read_text())
    if args.command=='sample':
        from sponsor_match.evaluation_sampling import sample_profiles
        folder=Path(args.onboarding);cases=sample_profiles(read(folder/'occupations.json'),read(folder/'skills.json'),args.occupations,args.seed)
        Path(args.output).write_text(json.dumps(cases,indent=2));print(json.dumps({'profiles':len(cases),'major_families':len({c['major_family'] for c in cases}),'families':len({c['family'] for c in cases}),'held_out_profiles':sum(c['split']=='held_out' for c in cases)}))
    elif args.command=='build':
        runs={}
        for entry in args.run:
            name,path=entry.split('=',1)
            if name in runs:raise ValueError('Run names must be unique')
            runs[name]=read(path)
        frozen=freeze(runs,args.depth);output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
        (output/'benchmark.json').write_text(json.dumps(frozen,indent=2));(output/'reviews.json').write_text(json.dumps([{k:p[k] for k in ['profile_id','employer_id','review_hash','label','reviewer_type','reviewer_id','failure','note','explanation_supported','channel_useful','task_fit']} for p in frozen['packet']],indent=2))
        initial=score(frozen,[])
        (output/'scorecard.json').write_text(json.dumps(initial,indent=2));render(frozen,output/'report.html');render_issues(frozen,initial,output/'issues.html')
        print(json.dumps({'profiles':len(frozen['profiles']),'pooled_pairs':len(frozen['packet']),'runs':list(runs),'report':str(output/'report.html')}))
    else:
        frozen=read(args.benchmark)
        result=score(frozen,read(args.reviews),args.reviewer_type,args.split) if args.command=='score' else agreement(frozen,read(args.first),read(args.second))
        Path(args.output).write_text(json.dumps(result,indent=2))
        if args.command=='score':render_issues(frozen,result,Path(args.output).parent/'issues.html')
        print(json.dumps({k:v for k,v in result.items() if k not in ['runs','diagnostics','disagreements','review_failures']},indent=2))


if __name__=='__main__':main()
