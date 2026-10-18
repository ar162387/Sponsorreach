"""Versioned exposure accounting and data-driven synthetic prospect iteration.

Coverage is not relevance accuracy. Profiles are evaluated through the actual
matcher; no target employer ID is passed into retrieval or ranking.
"""
from collections import Counter,defaultdict
from dataclasses import asdict
from contextlib import contextmanager
from datetime import datetime,UTC
from pathlib import Path
import gzip,html,json,sqlite3,time
from uuid import uuid4
from .intelligence import accepted,digest
from .models import Employer,Profile
from .prospects import profile_for
from .ranking import sponsor_valid,usable_channels,RANKING_VERSION
from .search import Matcher
from .taxonomy import key

PROPOSAL_VERSION='multi-occupation-evidence-5'


def profile_clarification(profile,taxonomy):
    normalized=taxonomy.normalize(profile)
    if normalized['clarification']:return normalized['clarification']
    if profile.explore or any(not role.confirmed for role in profile.role_intents):return 'Confirm the career interests before matching.'
    return None


def expand_activity_hypotheses(model_folder,groups,links,parents_per_activity=3):
    """Alternative occupations are query hypotheses, never accepted job claims."""
    import numpy as np
    model_folder=Path(model_folder)
    files=['references.json','reference-vectors.npz','term-vectors.npz','corpus.json.gz']
    if not all((model_folder/name).exists() for name in files):return groups,links,{'available':False}
    references=json.loads((model_folder/'references.json').read_text())
    reference_vectors=np.load(model_folder/'reference-vectors.npz')['vectors']
    data=np.load(model_folder/'term-vectors.npz');vectors=data['vectors'];term_ids=data['term_ids'].tolist()
    with gzip.open(model_folder/'corpus.json.gz','rt') as f:corpus=json.load(f)
    alternatives={}
    for start in range(0,len(term_ids),512):
        scores=vectors[start:start+512]@reference_vectors.T
        for offset,similarities in enumerate(scores):
            tid=term_ids[start+offset]
            if corpus['terms'][tid]['kind']!='activity':continue
            chosen=[];parents=set();floor=max(.43,float(similarities.max())-.10)
            for i in np.argsort(-similarities):
                if float(similarities[i])+1e-6<floor:break
                ref=references[int(i)];parent=ref['id'].rsplit(':',1)[-1][:4]
                if parent in parents:continue
                parents.add(parent);chosen.append((ref,float(similarities[i])))
                if len(chosen)>=parents_per_activity:break
            if chosen:alternatives[tid]=chosen
    result_groups=dict(groups);result_links=list(links)
    seen={(l['employer_id'],l['claim_id'],l['group_id'],key(l['span'])) for l in links}
    added=0
    for observation in corpus['observations']:
        if observation['kind']!='activity':continue
        for reference,similarity in alternatives.get(observation['term_id'],[]):
            gid=reference['id'];span=observation['text']
            fingerprint=(observation['employer_id'],observation['claim_id'],gid,key(span))
            if fingerprint in seen:continue
            seen.add(fingerprint);added+=1
            result_groups.setdefault(gid,{'id':gid,'label':reference['label'][:120],'description':reference['description'],'reference_id':gid})
            result_links.append({**observation,'group_id':gid,'span':span,'similarity':similarity,
                                 'mapping_status':'derived_not_reviewed','proposal_basis':'alternative_occupation_proximity'})
    return result_groups,result_links,{'available':True,'parents_per_activity':parents_per_activity,'maximum_best_similarity_gap':.10,'added_links':added,'groups':len(result_groups),'activity_terms_with_hypotheses':len(alternatives)}

class CoverageLedger:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript('''create table if not exists runs(id text primary key,created_at text,metadata text);
            create table if not exists profiles(run_id text,profile_id text,iteration integer,payload text,origin text,primary key(run_id,profile_id));
            create table if not exists hits(run_id text,profile_id text,employer_id text,rank integer,group_name text,primary key(run_id,profile_id,employer_id));
            create index if not exists employer_exposure on hits(employer_id,run_id,rank);
            create table if not exists outcomes(run_id text,employer_id text,payload text,primary key(run_id,employer_id));''')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path)
        try:
            with c:yield c
        finally:c.close()
    def start(self,metadata,idempotency_key=None):
        run_id=idempotency_key or uuid4().hex
        with self.connect() as c:c.execute('insert or ignore into runs values(?,?,?)',(run_id,datetime.now(UTC).isoformat(),json.dumps(metadata)))
        return run_id
    def profile_counts(self,run_id):
        with self.connect() as c:
            total,baseline,generated=c.execute('select count(*),coalesce(sum(iteration=0),0),coalesce(sum(iteration>0),0) from profiles where run_id=?',(run_id,)).fetchone()
        return {'total':total,'baseline':baseline,'generated':generated}
    def record(self,run_id,profile,results,iteration,origin):
        pid=digest(profile)
        with self.connect() as c:
            c.execute('insert or ignore into profiles values(?,?,?,?,?)',(run_id,pid,iteration,json.dumps(profile),json.dumps(origin)))
            c.executemany('insert or ignore into hits values(?,?,?,?,?)',[(run_id,pid,str(r['employer_id']),i+1,r.get('group','direct')) for i,r in enumerate(results)])
        return pid
    def exposures(self,run_id):
        result={}
        with self.connect() as c:
            for eid,total,preview,top10,best,profiles in c.execute('select employer_id,count(*),sum(rank<=3),sum(rank<=10),min(rank),count(distinct profile_id) from hits where run_id=? group by employer_id',(run_id,)):
                result[eid]={'appearances':total,'preview_appearances':preview,'top10_appearances':top10,'best_rank':best,'distinct_profiles':profiles}
        return result

    def best_profiles(self,run_id):
        with self.connect() as c:
            rows=c.execute('''with ranked as (
                select employer_id,profile_id,rank,row_number() over(partition by employer_id order by rank,profile_id) n
                from hits where run_id=?)
                select r.employer_id,r.profile_id,r.rank,p.payload from ranked r
                join profiles p on p.run_id=? and p.profile_id=r.profile_id where r.n=1''',(run_id,run_id)).fetchall()
        return {eid:{'profile_id':pid,'rank':rank,'profile':json.loads(payload)} for eid,pid,rank,payload in rows}
    def finalize(self,run_id,rows):
        with self.connect() as c:
            c.executemany('insert or replace into outcomes values(?,?,?)',[(run_id,r['employer_id'],json.dumps(r)) for r in rows])
            metadata=json.loads(c.execute('select metadata from runs where id=?',(run_id,)).fetchone()[0]);metadata['status']='finished';metadata['finished_at']=datetime.now(UTC).isoformat()
            c.execute('update runs set metadata=? where id=?',(json.dumps(metadata),run_id))

    def saved_run(self,run_id):
        with self.connect() as c:
            meta=c.execute('select metadata from runs where id=?',(run_id,)).fetchone()
            if not meta:raise ValueError('Unknown coverage run')
            profiles=[]
            for pid,iteration,payload,origin in c.execute('select profile_id,iteration,payload,origin from profiles where run_id=?',(run_id,)).fetchall():
                hits=[{'employer_id':r[0],'group':r[1]} for r in c.execute('select employer_id,group_name from hits where run_id=? and profile_id=? order by rank',(run_id,pid))]
                profiles.append({'profile_id':pid,'iteration':iteration,'profile':json.loads(payload),'origin':json.loads(origin),'results':hits})
            return json.loads(meta[0]),profiles


def import_benchmarks(ledger,folders,allowed_ids):
    exposures=Counter();preview=Counter();top10=Counter();runs=[]
    for folder in folders:
        path=Path(folder)/'runs.json'
        if not path.exists():path=Path(folder)/'generated-profiles.json'
        if not path.exists():continue
        records=json.loads(path.read_text());run=ledger.start({'origin':'imported_benchmark','path':str(path),'versions':records[0].get('versions',{}) if records else {}},digest(['benchmark',records]))
        if run in runs:continue
        runs.append(run)
        for row in records:
            if 'profile' not in row:continue
            profile=Profile.model_validate(row['profile']).model_dump(mode='json')
            results=row.get('results',[])
            if row.get('ranking'):results=[{'employer_id':eid,'group':'direct'} for eid in row['ranking']]
            results=[r for r in results if str(r['employer_id']) in allowed_ids]
            ledger.record(run,profile,results,0,{'kind':'existing_test','source_profile_id':row.get('id')})
        for eid,e in ledger.exposures(run).items():
            exposures[eid]+=e['appearances'];preview[eid]+=e['preview_appearances'];top10[eid]+=e['top10_appearances']
    return exposures,preview,top10,runs


def coverage_loop(db,settings,model_folder,output,baselines=(),max_profiles=200,round_size=25,rounds=8,progress=lambda _:None,resume=None,strategy='current'):
    if strategy not in {'current','semantic'}:raise ValueError('Unknown coverage strategy')
    model_folder=Path(model_folder);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((model_folder/'manifest.json').read_text());groups={g['id']:g for g in json.loads((model_folder/'groups.json').read_text())}
    expected=json.loads((model_folder/'employer-versions.json').read_text())
    employers=db.employers([str(r['id']) for r in db.rows("select id from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv' order by id")])
    current={e.id:e.version for e in employers}
    if current!=expected:raise ValueError('Prospect model does not match this employer snapshot; rebuild before evaluating coverage')
    with gzip.open(model_folder/'links.json.gz','rt') as f:links=json.load(f)
    groups,links,proposal_expansion=expand_activity_hypotheses(model_folder,groups,links)
    from .discovery_profiles import DiscoveryProfiles,interest_variants
    discovery=DiscoveryProfiles(model_folder);official_profiles,official_baseline=discovery.official_baseline()
    by_employer=defaultdict(list)
    for link in links:by_employer[link['employer_id']].append(link)
    ledger=CoverageLedger(output.parent/'coverage.sqlite3');baseline,baseline_preview,baseline_top10,prior_runs=import_benchmarks(ledger,baselines,set(current))
    index=db.one('select id,model,taxonomy_version from sm.search_index_versions where active')
    if strategy=='semantic':
        from .semantic_search import SemanticMatcher
        matcher=SemanticMatcher(db,settings,model_folder);ranking_version=matcher.ranking_version
    else:matcher=Matcher(db,settings);ranking_version=RANKING_VERSION
    source_names=['semantic_search.py','role_information.py','occupation_titles.py','exposure_order.py','ranking.py','intelligence.py','providers.py','models.py','taxonomy.py','prospects.py'] if strategy=='semantic' else ['ranking.py','search.py']
    ranking_sources={name:(Path(__file__).parent/name).read_text() for name in source_names}
    proposal_sources={name:(Path(__file__).parent/name).read_text() for name in ['coverage.py','discovery_profiles.py']}
    run_metadata={'origin':'corpus_discovery_loop','proposal_version':PROPOSAL_VERSION,'proposal_expansion':proposal_expansion,'ranking_source_hash':digest(ranking_sources),'strategy':strategy,'model_version':manifest['version'],'ranking_version':ranking_version,'index':str(index['id']) if index else None,'source_hash':digest(current),'baseline_runs':prior_runs,'snapshot':db.active_snapshot(),'evaluated_date':datetime.now(UTC).date().isoformat(),'status':'running'}
    run_metadata.update(proposal_source_hash=digest(proposal_sources),official_occupation_baseline=official_baseline)
    if resume:
        previous,saved=ledger.saved_run(resume)
        if any(previous.get(k)!=run_metadata.get(k) for k in ['proposal_version','proposal_source_hash','official_occupation_baseline','ranking_source_hash','model_version','ranking_version','index','source_hash','snapshot','evaluated_date']):raise ValueError('Resume requires the same proposal algorithm, model, ranking, index and employer versions')
        run_id=resume
    else:
        run_id=ledger.start(run_metadata);saved=[]
        (output/'run-metadata.json').write_text(json.dumps(run_metadata,indent=2))
        for name,content in ranking_sources.items():(output/('frozen-'+name)).write_text(content)
        (output/'proposal-source').mkdir(exist_ok=True)
        for name,content in proposal_sources.items():(output/'proposal-source'/name).write_text(content)
    snapshot=db.active_snapshot();tested=set();coverage=set();iteration_reports=[];generated=[];errors=[];clarifications={}
    clarification_path=output/'profile-clarifications.json'
    if resume and clarification_path.exists():clarifications={r['profile_id']:r for r in json.loads(clarification_path.read_text())}
    taxonomy=db.taxonomy()
    saved_by_id={row['profile_id']:row for row in saved}
    tested={row['profile_id'] for row in saved if row['iteration']>0}
    generated=[row for row in saved if row['iteration']>0]
    for row in saved:coverage.update(r['employer_id'] for r in row['results'])
    baseline_profiles={};official_origins=defaultdict(list)
    for folder in baselines:
        path=Path(folder)/'runs.json'
        if not path.exists():path=Path(folder)/'generated-profiles.json'
        if not path.exists():continue
        for row in json.loads(path.read_text()):
            if 'profile' in row:
                p=Profile.model_validate(row['profile']);baseline_profiles[digest(p.model_dump(mode='json'))]=p
    for item in official_profiles:
        p=item['profile'];fingerprint=digest(p.model_dump(mode='json'))
        baseline_profiles.setdefault(fingerprint,p);official_origins[fingerprint].append(item['reference_id'])
    for i,(fingerprint,profile) in enumerate(baseline_profiles.items(),1):
        question=profile_clarification(profile,taxonomy)
        if question:
            clarifications[fingerprint]={'profile_id':fingerprint,'phase':'baseline','profile':profile.model_dump(mode='json'),'clarification':question}
            continue
        if fingerprint in saved_by_id:continue
        results,mode,versions=matcher.search(profile)
        rendered=[asdict(r) for r in results if r.employer_id in current]
        ledger.record(run_id,profile.model_dump(mode='json'),rendered,0,{'kind':'official_occupation_baseline' if fingerprint in official_origins else 'baseline_rerun_current_version','reference_ids':official_origins.get(fingerprint,[]),'versions':versions})
        coverage.update(r['employer_id'] for r in rendered)
        if i%50==0:progress({'baseline_profiles_rerun':i,'current_baseline_reached':len(coverage)})
    if saved:
        current_baseline={r['employer_id'] for row in saved if row['iteration']==0 for r in row['results']}
    else:current_baseline=set(coverage)
    seen_profile_fingerprints=set(baseline_profiles)|tested|set(clarifications)
    initially_qualified={e.id for e in employers if e.identity_status=='accepted' and sponsor_valid(e,snapshot) and usable_channels(e) and any(accepted(c) for c in e.claims)}
    stop='round_limit'
    start_iteration=max((row['iteration'] for row in saved),default=0)+1
    previous_summary=output/'summary.json'
    if resume and previous_summary.exists():iteration_reports=json.loads(previous_summary.read_text()).get('rounds',[])
    for iteration in range(start_iteration,start_iteration+rounds):
        proposals={}
        for employer in employers:
            if employer.id in coverage or employer.id not in initially_qualified:continue
            candidates=sorted(by_employer[employer.id],key=lambda item:(item['kind']=='role',item['similarity']),reverse=True)
            for link in candidates:
                group=groups[link['group_id']]
                activities=discovery.contexts_for(employer.name,link,group)
                for variant in interest_variants(group,link,activities):
                    p=variant['profile'];fingerprint=digest(p.model_dump(mode='json'))
                    if fingerprint in seen_profile_fingerprints:continue
                    question=profile_clarification(p,taxonomy)
                    if question:
                        clarifications[fingerprint]={'profile_id':fingerprint,'phase':'generated','profile':p.model_dump(mode='json'),'clarification':question}
                        seen_profile_fingerprints.add(fingerprint)
                        continue
                    entry=proposals.setdefault(fingerprint,{'profile':p,'group_id':group['id'],'variant':variant['variant'],'evidence_ids':set(),'seed_employers':set()})
                    entry['seed_employers'].add(employer.id);entry['evidence_ids'].update(variant['evidence_ids'])
        if not proposals:stop='no_novel_evidence_supported_profiles';break
        ranked=sorted(proposals.items(),key=lambda pair:(-len(pair[1]['seed_employers']),pair[0]))
        batch=ranked[:min(round_size,max_profiles-len(tested))] if max_profiles else ranked[:round_size]
        if not batch:stop='profile_budget';break
        before=len(coverage)
        for fingerprint,entry in batch:
            tested.add(fingerprint);seen_profile_fingerprints.add(fingerprint);profile=entry['profile'];start=time.monotonic()
            try:
                results,mode,versions=matcher.search(profile)
                rendered=[asdict(r) for r in results if r.employer_id in current]
                ledger.record(run_id,profile.model_dump(mode='json'),rendered,iteration,{'kind':'evidence_derived_synthetic','variant':entry['variant'],'candidate_qualification_claims':False,'group_id':entry['group_id'],'seed_employers':sorted(entry['seed_employers']),'evidence_ids':sorted(entry['evidence_ids']),'target_used_by_matcher':False,'versions':versions})
                coverage.update(r['employer_id'] for r in rendered)
                generated.append({'profile_id':fingerprint,'iteration':iteration,'group_id':entry['group_id'],'variant':entry['variant'],'evidence_ids':sorted(entry['evidence_ids']),'candidate_qualification_claims':False,'profile':profile.model_dump(mode='json'),'results':[{'employer_id':r['employer_id'],'group':r['group'],'score':r['score']} for r in rendered],'seed_count':len(entry['seed_employers']),'seed_employers_reached':len(entry['seed_employers']&{r['employer_id'] for r in rendered}),'elapsed_ms':round((time.monotonic()-start)*1000,2),'mode':mode,'versions':versions})
            except Exception as exc:errors.append({'profile_id':fingerprint,'error_type':type(exc).__name__})
        report={'iteration':iteration,'profiles_tested':len(tested),'new_employers_reached':len(coverage)-before,'cumulative_employers_reached':len(coverage),'candidate_profile_hypotheses':len(proposals)}
        iteration_reports.append(report);progress(report)
        if initially_qualified<=coverage:stop='all_currently_qualified_employers_reached';break
        if max_profiles and len(tested)>=max_profiles:stop='profile_budget';break
    exposure=ledger.exposures(run_id);examples=ledger.best_profiles(run_id);outcomes=[]
    for employer in employers:
        e=exposure.get(employer.id,{});professional=any(accepted(c) for c in employer.claims)
        if employer.id in coverage:state='reached'
        elif employer.identity_status!='accepted':state='identity_not_accepted'
        elif not sponsor_valid(employer,snapshot):state='current_sponsor_linkage_required'
        elif not usable_channels(employer):state='useful_channel_required'
        elif not professional:state='professional_descriptors_required'
        elif employer.id not in by_employer:state='no_supported_prospect_mapping_yet'
        else:state='not_yet_reached_by_tested_profiles'
        outcomes.append({'employer_id':employer.id,'name':employer.name,'employer_version':employer.version,'state':state,'baseline_appearances':baseline.get(employer.id,0),'new_appearances':e.get('appearances',0),'preview_appearances':e.get('preview_appearances',0),'top10_appearances':e.get('top10_appearances',0),'best_new_rank':e.get('best_rank'),'example_profile':examples.get(employer.id),'prospect_group_ids':sorted({l['group_id'] for l in by_employer.get(employer.id,[])})})
    ledger.finalize(run_id,outcomes)
    states=Counter(r['state'] for r in outcomes)
    summary={'run_id':run_id,'strategy':strategy,'model_version':manifest['version'],'ranking_version':ranking_version,'employers':len(employers),'historical_baseline_reached':len(baseline),'baseline_reached':len(current_baseline),'baseline_profiles_rerun':len(baseline_profiles),'regressed_historical_employers':len(set(baseline)-coverage),'generated_profiles':len(tested),'newly_reached':len(coverage-current_baseline),'total_reached':len(coverage),'preview_reached':sum(r['preview_appearances']>0 for r in outcomes),'top10_reached':sum(r['top10_appearances']>0 for r in outcomes),'not_yet_reached':len(set(current)-coverage),'outcome_counts':dict(states),'stop_reason':stop,'rounds':iteration_reports,'errors':errors,'full_goal_achieved':len(coverage)==len(employers),'quality_accuracy_measured':False,'coverage_is_not_relevance_accuracy':True}
    counts=ledger.profile_counts(run_id)
    summary.update(profiles_evaluated=counts['total'],baseline_profiles_evaluated=counts['baseline'],needs_clarification_profiles=len(clarifications),profile_readiness_policy='api-confirmed-profile-1')
    clarification_path.write_text(json.dumps(list(clarifications.values()),indent=2))
    (output/'summary.json').write_text(json.dumps(summary,indent=2));(output/'employer-coverage.json').write_text(json.dumps(outcomes,indent=2));(output/'generated-profiles.json').write_text(json.dumps(generated,indent=2));render_coverage(output,summary,outcomes,generated)
    run_metadata.update(status='completed_with_errors' if errors else 'completed',run_id=run_id,stop_reason=stop)
    (output/'run-metadata.json').write_text(json.dumps(run_metadata,indent=2))
    return summary


def render_coverage(output,summary,outcomes,generated):
    esc=lambda value:html.escape(str(value))
    document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SponsorReach employer reachability</title><style>body{font:16px/1.5 system-ui;color:#123e50;background:#f6f8f7;max-width:1250px;margin:40px auto;padding:0 24px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:10px;text-align:left;border-bottom:1px solid #dbe6e8}input,select{padding:10px;margin:8px}small{color:#526b77}.note{padding:20px;background:#e0f0ed;border-radius:12px}</style><h1>Employer reachability · corpus discovery</h1>'''
    document+='<p class="note">Coverage measures whether an employer appears for a tested synthetic profile. It does not prove professional relevance, vacancy availability or sponsorship willingness. No employer IDs or names were used as matching overrides.</p><p>'+esc(summary['total_reached'])+' of '+esc(summary['employers'])+' employers reached · '+esc(summary['newly_reached'])+' newly reached · '+esc(summary['generated_profiles'])+' generated profiles.</p><p>Stop reason: '+esc(summary['stop_reason'])+'. Full coverage: '+esc(summary['full_goal_achieved'])+'.</p><p><a href="summary.json">Summary JSON</a> · <a href="generated-profiles.json">Synthetic profiles</a> · <a href="employer-coverage.json">Every employer and its outcome</a></p><input id="q" aria-label="Find employer" placeholder="Find an employer or status"><table><thead><tr><th>Employer</th><th>Status</th><th>Previous appearances</th><th>Current appearances</th><th>Preview appearances</th></tr></thead><tbody>'
    document=document.replace('<th>Previous appearances</th>','<th>Historical appearances</th>').replace('<th>Preview appearances</th>','<th>Preview appearances</th><th>Best rank</th><th>Example profile</th>')
    for row in outcomes:
        example=row.get('example_profile') or {};profile=example.get('profile',{})
        label=' / '.join(r['raw_label'] for r in profile.get('role_intents',[]))
        specialization=profile.get('background',{}).get('specialization','')
        document+='<tr>'+''.join('<td>'+esc(row[k])+'</td>' for k in ['name','state','baseline_appearances','new_appearances','preview_appearances'])+'<td>'+esc(row.get('best_new_rank') or '—')+'</td><td>'+esc(label+(' · '+specialization if specialization else ''))+'</td></tr>'
    document+='</tbody></table><script>document.querySelector("#q").addEventListener("input",e=>{for(const row of document.querySelectorAll("tbody tr"))row.hidden=!row.textContent.toLowerCase().includes(e.target.value.toLowerCase())})</script></html>'
    (Path(output)/'report.html').write_text(document)
