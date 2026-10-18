"""Recount a synthetic experiment using the application's confirmed-profile gate.

Original trials and hits remain immutable. A separate derived report exposes
only valid-profile frequencies and example profiles, with explicit provenance.
"""
import argparse,inspect,json
from collections import Counter
from pathlib import Path
from sponsor_match.config import Settings
from sponsor_match.coverage import CoverageLedger,profile_clarification,render_coverage
from sponsor_match.db import Database
from sponsor_match.intelligence import digest
from sponsor_match.models import Profile
from sponsor_match import taxonomy as taxonomy_module


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--coverage-folder',required=True)
    args=parser.parse_args();folder=Path(args.coverage_folder)
    summary=json.loads((folder/'summary.json').read_text());outcomes=json.loads((folder/'employer-coverage.json').read_text())
    metadata,rows=CoverageLedger(folder.parent/'coverage.sqlite3').saved_run(summary['run_id'])
    settings=Settings.from_env();db=Database(settings.database_url);db.open()
    try:
        taxonomy=db.taxonomy();taxonomy_code=Path(taxonomy_module.__file__).read_text()
        frozen=folder/'frozen-taxonomy.py'
        if frozen.exists() and frozen.read_text()!=taxonomy_code:raise ValueError('Normalizer code changed; audit the original source version')
        policy_hash=digest([inspect.getsource(profile_clarification),taxonomy_code,taxonomy.version])
        counts=Counter();preview=Counter();top10=Counter();examples={};valid=set();invalid=[]
        for row in rows:
            profile=Profile.model_validate(row['profile']);question=profile_clarification(profile,taxonomy)
            if question:
                invalid.append({'profile_id':row['profile_id'],'profile':row['profile'],'clarification':question,'raw_employer_results':len(row['results'])})
                continue
            valid.add(row['profile_id'])
            for rank,result in enumerate(row['results'],1):
                eid=result['employer_id'];counts[eid]+=1
                preview[eid]+=int(rank<=3);top10[eid]+=int(rank<=10)
                if eid not in examples or rank<examples[eid]['rank']:
                    examples[eid]={'profile_id':row['profile_id'],'rank':rank,'profile':row['profile']}
        preview_reached=sum(n>0 for n in preview.values());top10_reached=sum(n>0 for n in top10.values())
        audit={'policy':'api-confirmed-profile-1','policy_hash':policy_hash,'source_run':summary['run_id'],'ranking_version':summary['ranking_version'],'source_model':summary['model_version'],'source_hash':metadata['source_hash'],'raw_profiles':len(rows),'valid_profiles':len(valid),'needs_clarification_profiles':len(invalid),'valid_reached':len(counts),'valid_preview_reached':preview_reached,'valid_top10_reached':top10_reached,'invalid_profiles':invalid,'rankings_changed':False,'note':'A derived recount of historical synthetic trials against the confirmed-profile gate. Original raw trials/hits are preserved. No user accounts or employer data changed.'}
        (folder/'profile-readiness-audit.json').write_text(json.dumps(audit,indent=2))
        if set(counts)!={r['employer_id'] for r in outcomes if r['state']=='reached'}:raise ValueError('Invalid profiles supplied unique reach; rerun discovery under the valid-profile protocol before publishing')
        for row in outcomes:
            eid=row['employer_id']
            row.update(new_appearances=counts[eid],preview_appearances=preview[eid],top10_appearances=top10[eid],best_new_rank=examples[eid]['rank'] if eid in examples else None,example_profile=examples.get(eid))
        target=folder/'confirmed-profiles';target.mkdir(exist_ok=True)
        clean={**summary,'preview_reached':preview_reached,'top10_reached':top10_reached,'profiles_evaluated':len(valid),'profile_evaluation_policy':audit['policy'],'raw_profile_calls':len(rows),'needs_clarification_profiles':len(invalid),'source_raw_rounds':summary['rounds'],'rounds':[]}
        generated=[r for r in json.loads((folder/'generated-profiles.json').read_text()) if r['profile_id'] in valid]
        clean['generated_profiles']=len(generated)
        for name,value in [('summary.json',clean),('employer-coverage.json',outcomes),('generated-profiles.json',generated),('profile-readiness-audit.json',audit)]:
            (target/name).write_text(json.dumps(value,indent=2))
        render_coverage(target,clean,outcomes,generated)
        page=target/'report.html';text=page.read_text();text=text.replace('<h1>Employer reachability · corpus discovery</h1>','<h1>Employer reachability · confirmed profiles</h1><p>Historical trials recounted using the application\'s readiness gate: '+str(len(valid))+' valid profiles; '+str(len(invalid))+' requiring clarification excluded. Raw trials are preserved separately. No results were reranked.</p>')
        page.write_text(text)
        print(json.dumps({k:v for k,v in audit.items() if k!='invalid_profiles'}))
    finally:db.close()


if __name__=='__main__':main()
