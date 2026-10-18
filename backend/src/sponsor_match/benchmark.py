"""Career-profile benchmark with explicit separation of checks and relevance labels."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
import html
import json
from pathlib import Path
import time
from .evaluate import profiles, metrics
from .models import Profile
from .search import Matcher
from .ranking import sponsor_valid, usable_channels
from .intelligence import accepted


def percentile(values, p):
    values = sorted(values)
    if not values:
        return None
    at = (len(values)-1)*p
    lower = int(at)
    return round(values[lower] + (values[min(lower+1,len(values)-1)]-values[lower])*(at-lower), 3)


def prospect_profiles():
    result = profiles()
    # Adversarial backgrounds cannot create an unsupported corporate function.
    extra = [
        ('niche_materials','Materials science','Quantum lattice researcher',False),
        ('broad_analyst','Economics','Analyst',False),
        ('broad_engineer','Engineering','Engineer',False),
        ('retail_hr','Retail management','HR specialist',False),
        ('construction_legal','Construction management','Solicitor',False),
        ('retail_marketing','Retail management','Marketing specialist',False),
        ('renewable_legal','Renewable energy','Legal associate',False),
        ('mechanical_sales_off','Mechanical Engineering','Mechanical engineer',False),
        ('mechanical_sales_on','Mechanical Engineering','Mechanical engineer',True),
        ('software_synonym','Computer science','Software engineer',False),
        ('accounting_synonym','Accounting','Trainee accountant',False),
        ('senior_software','Computer science','Senior software engineer',False),
    ]
    base = Profile.model_validate(result[0]['profile'])
    for pid,background,role,related in extra:
        p=base.model_copy(deep=True)
        p.background.subject=background;p.background.specialization=''
        p.role_intents=[p.role_intents[0].model_copy(update={'raw_label':role,'concept_id':None,'confirmed':True})]
        p.related_roles_enabled=related;p.skills=[];p.location.preferred_regions=[]
        result.append({'id':'adversarial:'+pid,'occupation_family':'adversarial','synthetic':True,'profile':p.model_dump()})
    multi=base.model_copy(deep=True);multi.background.subject='Computer science and accounting';multi.skills=[]
    multi.role_intents=[multi.role_intents[0].model_copy(update={'raw_label':label,'concept_id':None,'confirmed':True}) for label in ['Software engineer','Accountant','Marketing specialist']]
    result.append({'id':'adversarial:multiple_intents','occupation_family':'adversarial','synthetic':True,'profile':multi.model_dump()})
    return result


def run_benchmark(db, settings, output, concurrency=2, labels=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    # Real employers only; never mistake a demo fixture for real catalogue coverage.
    settings=replace(settings,environment='production')
    matcher=Matcher(db,settings)
    taxonomy=db.taxonomy()
    cases=prospect_profiles()
    started=datetime.now(UTC)
    def run(case):
        profile=Profile.model_validate(case['profile'])
        normalization=taxonomy.normalize(profile)
        row={**case,'clarification':normalization['clarification']}
        if normalization['clarification']:
            return {**row,'status':'needs_clarification','results':[],'elapsed_ms':0}
        begin=time.perf_counter()
        try:
            results,mode,versions=matcher.search(profile)
            elapsed=(time.perf_counter()-begin)*1000
            employers={e.id:e for e in db.employers([r.employer_id for r in results])}
            rendered=[]
            for rank,result in enumerate(results,1):
                employer=employers[result.employer_id]
                claims={c.id:c for c in employer.claims}
                cited=[claims[c] for c in result.explanation['claim_ids'] if c in claims]
                checks={
                    'real_employer':not employer.is_demo,
                    'accepted_identity':employer.identity_status=='accepted',
                    'current_sponsor':sponsor_valid(employer,versions['snapshot']),
                    'useful_channel':bool(usable_channels(employer)),
                    'evidence_references_exist':len(cited)==len(result.explanation['claim_ids']) and bool(cited),
                    'evidence_accepted':bool(cited) and all(accepted(c) for c in cited),
                    'related_opt_in':result.group!='related' or profile.related_roles_enabled,
                }
                rendered.append({'employer_id':employer.id,'employer_name':employer.name,'rank':rank,'group':result.group,'intent':result.features['intent'],'explanation':result.explanation,'checks':checks})
            return {**row,'status':'completed','elapsed_ms':round(elapsed,3),'mode':mode,'versions':versions,'results':rendered}
        except Exception as exc:
            return {**row,'status':'failed','error_type':type(exc).__name__,'elapsed_ms':round((time.perf_counter()-begin)*1000,3),'results':[]}
    with ThreadPoolExecutor(max_workers=max(1,min(4,concurrency))) as executor:
        runs=list(executor.map(run,cases))
    (output/'prospects.json').write_text(json.dumps(cases,indent=2)+'\n')
    (output/'runs.json').write_text(json.dumps(runs,indent=2,default=str)+'\n')
    rankings={r['id']:[e['employer_id'] for e in r['results'] if e['group']=='direct'] for r in runs if r['status']=='completed'}
    (output/'rankings.json').write_text(json.dumps(rankings,indent=2)+'\n')
    review=[{'profile_id':r['id'],'employer_id':e['employer_id'],'employer_name':e['employer_name'],'rank':e['rank'],'label':'unjudged','explanation_supported':None,'channel_useful':None,'vacancy_claim_supported':None} for r in runs for e in r['results'][:10]]
    (output/'review-template.json').write_text(json.dumps(review,indent=2)+'\n')
    family=defaultdict(list)
    for r in runs:
        family[r['occupation_family']].append(r)
    checks=Counter();violations=[]
    for r in runs:
        for e in r['results']:
            for name,passed in e['checks'].items():
                checks[name+('_passed' if passed else '_failed')]+=1
                if not passed:violations.append({'profile_id':r['id'],'employer_id':e['employer_id'],'check':name})
    completed=[r for r in runs if r['status']=='completed']
    by_id={r['id']:r for r in runs}
    direct_ids=lambda pid:{e['employer_id'] for e in by_id[pid]['results'] if e['group']=='direct'}
    metamorphic={
        'software_stage_prefix_preserves_matches':direct_ids('adversarial:software_synonym')==direct_ids('adversarial:senior_software'),
        'related_opt_in_preserves_direct_matches':direct_ids('adversarial:mechanical_sales_off')==direct_ids('adversarial:mechanical_sales_on'),
        'unknown_niche_abstains':not by_id['adversarial:niche_materials']['results'],
        'broad_titles_require_clarification':all(by_id['adversarial:'+pid]['status']=='needs_clarification' for pid in ['broad_analyst','broad_engineer']),
    }
    for name,passed in metamorphic.items():
        if not passed:violations.append({'check':name})
    labels=json.loads(Path(labels).read_text()) if labels else []
    quality={f'k{k}':metrics(rankings,labels,k) for k in [3,10]}
    report={
        'started_at':started.isoformat(),'finished_at':datetime.now(UTC).isoformat(),'profiles':len(runs),
        'statuses':dict(Counter(r['status'] for r in runs)),
        'nonempty_direct_profiles':sum(any(e['group']=='direct' for e in r['results']) for r in completed),
        'profiles_with_related_results':sum(any(e['group']=='related' for e in r['results']) for r in completed),
        'abstaining_profiles':sum(not r['results'] for r in completed),
        'profiles_with_three_direct':sum(sum(e['group']=='direct' for e in r['results'])>=3 for r in completed),
        'latency_ms':{f'p{int(p*100)}':percentile([r['elapsed_ms'] for r in completed],p) for p in [.5,.95,.99]},
        'automated_checks':dict(checks),'metamorphic_checks':metamorphic,'violations':violations,'quality_metrics':quality,
        'families':{name:{'label':taxonomy.by_id[name].label if name in taxonomy.by_id else 'Adversarial cases','profiles':len(items),'with_direct_results':sum(any(e['group']=='direct' for e in r['results']) for r in items),'max_direct_results':max((sum(e['group']=='direct' for e in r['results']) for r in items),default=0),'p95_ms':percentile([r['elapsed_ms'] for r in items if r['status']=='completed'],.95)} for name,items in family.items()},
        'measurement_scope':'Local matching engine with real employer data; excludes HTTP gateway, queue delay, email and remote network latency. Cache may be warm.',
        'quality_note':'Automated evidence consistency is not independently judged professional relevance. Unjudged pairs remain unjudged. No precision/recall or launch-quality claim without labels.'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    render_report(output,report,runs)
    return report


def render_report(output,report,runs):
    esc=lambda value:html.escape(str(value))
    rows=''.join(f'<tr><td>{esc(r["label"])}</td><td>{r["profiles"]}</td><td>{r["with_direct_results"]}</td><td>{r["max_direct_results"]}</td><td>{r["p95_ms"]}</td></tr>' for name,r in report['families'].items())
    labels=['unjudged','direct','related','insufficient_evidence','irrelevant','wrong_entity']
    detail=''; review=[]
    for r in runs:
        detail+='<details class="prospect"><summary>'+esc(r['id'])+' · '+esc(r['profile']['role_intents'][0]['raw_label'])+' · '+str(len(r['results']))+' results</summary><p>'+esc(r['profile']['background']['subject'])+' · '+esc(r.get('clarification') or r['status'])+'</p>'
        for e in r['results'][:10]:
            index=len(review)
            review.append({'profile_id':r['id'],'employer_id':e['employer_id'],'employer_name':e['employer_name'],'label':'unjudged','explanation_supported':None})
            options=''.join('<option value="'+v+'">'+v.replace('_',' ').capitalize()+'</option>' for v in labels)
            detail+='<article><h3>'+str(e['rank'])+'. '+esc(e['employer_name'])+' <small>'+esc(e['group'])+'</small></h3><p>'+esc(e['explanation']['text'])+'</p>'
            detail+=''.join('<blockquote>'+esc(s['excerpt'])+'</blockquote>'+('<a href="'+esc(s['url'])+'" target="_blank" rel="noopener noreferrer">Employer source</a>' if s['url'].startswith(('https://','http://')) else '<small>Provided CSV record</small>') for s in e['explanation']['sources'])
            detail+=f'<p><label>Your relevance judgment <select data-review="{index}">{options}</select></label> <label>Explanation supported? <select data-support="{index}"><option value="">Unreviewed</option><option value="yes">Yes</option><option value="no">No</option></select></label></p></article>'
        detail+='</details>'
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SponsorReach matching evaluation</title><style>body{font:16px/1.5 system-ui;background:#f4f8f7;color:#123e50;max-width:1100px;margin:40px auto;padding:0 24px}h1{font-size:38px}small{color:#55707b}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;text-align:left;border-bottom:1px solid #dbe6e8}details{background:white;border:1px solid #dbe6e8;border-radius:10px;padding:16px;margin:10px 0}summary{cursor:pointer;font-weight:600}article{padding:16px;border-top:1px solid #dbe6e8}blockquote{border-left:3px solid #15a095;margin:8px 0;padding:8px 16px}a{color:#087f76}.note{background:#e0f0ed;padding:20px;border-radius:10px}</style>'''
    document+='<h1>SponsorReach · matching evaluation</h1><p>'+esc(report['finished_at'])+'</p><p class="note">'+esc(report['quality_note'])+'</p><p>'+str(report['profiles'])+' synthetic prospects · '+str(report['nonempty_direct_profiles'])+' with direct matches · '+str(report['abstaining_profiles'])+' abstentions · '+str(len(report['violations']))+' automated consistency violations.</p><p>'+esc(report['measurement_scope'])+'</p><h2>Occupation coverage</h2><table><tr><th>Family</th><th>Profiles</th><th>With matches</th><th>Most direct matches</th><th>p95 ms</th></tr>'+rows+'</table><h2>Inspect results and evidence</h2><p>Judgments stay in this browser until exported. Export the labels to calculate relevance metrics separately.</p><p><input id="filter" aria-label="Filter profiles" placeholder="Find a role or profile"> <button id="export">Export review labels</button> <span id="count"></span></p>'+detail
    document+='<script>const review='+json.dumps(review).replace('<','\\u003c')+';const storageKey='+json.dumps('sponsorreach-review:'+report['finished_at'])+''';
    try { const stored=JSON.parse(localStorage.getItem(storageKey)); if(Array.isArray(stored)) stored.forEach((s,i)=>{if(review[i]&&s.profile_id===review[i].profile_id&&s.employer_id===review[i].employer_id) Object.assign(review[i],s);}); } catch {}
    function save(){document.getElementById('count').textContent=review.filter(r=>r.label!=='unjudged').length+' pairs judged';try{localStorage.setItem(storageKey,JSON.stringify(review));}catch{}}
    document.querySelectorAll('[data-review]').forEach(el=>{el.value=review[+el.dataset.review].label;el.onchange=()=>{review[+el.dataset.review].label=el.value;save();};});
    document.querySelectorAll('[data-support]').forEach(el=>{const v=review[+el.dataset.support].explanation_supported;el.value=v===null?'':v?'yes':'no';el.onchange=()=>{review[+el.dataset.support].explanation_supported=el.value===''?null:el.value==='yes';save();};});
    document.getElementById('filter').oninput=e=>document.querySelectorAll('.prospect').forEach(el=>{el.hidden=!el.querySelector('summary').textContent.toLowerCase().includes(e.target.value.toLowerCase());});
    document.getElementById('export').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify(review,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='sponsorreach-review-labels.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};save();</script></html>'''
    (output/'report.html').write_text(document)
