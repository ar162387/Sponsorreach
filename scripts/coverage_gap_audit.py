"""Separate ranking truncation from missing evidence without changing results."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from sponsor_match.config import Settings
from sponsor_match.coverage import CoverageLedger
from sponsor_match.db import Database
from sponsor_match.intelligence import digest
from sponsor_match.models import Profile
from sponsor_match.semantic_search import SemanticMatcher,VERSION


def verify_ranking_sources(folder,metadata,source_root):
    frozen={p.name.removeprefix('frozen-'):p.read_text() for p in Path(folder).glob('frozen-*.py')}
    if not frozen or digest(frozen)!=metadata['ranking_source_hash']:raise ValueError('Frozen ranking source integrity failed')
    current={name:(Path(source_root)/name).read_text() for name in frozen}
    if digest(current)!=metadata['ranking_source_hash']:raise ValueError('Matching code changed; replay the original frozen version or rerun coverage')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--coverage-folder',required=True)
    parser.add_argument('--model-folder',required=True)
    args=parser.parse_args()
    folder=Path(args.coverage_folder)
    summary=json.loads((folder/'summary.json').read_text())
    outcomes=json.loads((folder/'employer-coverage.json').read_text())
    ledger=CoverageLedger(folder.parent/'coverage.sqlite3')
    metadata,profiles=ledger.saved_run(summary['run_id'])
    from sponsor_match import semantic_search
    verify_ranking_sources(folder,metadata,Path(semantic_search.__file__).parent)
    settings=Settings.from_env();db=Database(settings.database_url);db.open()
    try:
        current={str(r['id']):r['version'] for r in db.rows("select id,version from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv'")}
        if digest(current)!=metadata['source_hash'] or db.active_snapshot()!=metadata['snapshot']:
            raise ValueError('Coverage evidence changed; rerun coverage before gap diagnosis')
        if metadata['ranking_version']!=VERSION:raise ValueError('Ranking version changed; rerun coverage first')
        matcher=SemanticMatcher(db,settings,args.model_folder)
        if matcher.manifest['version']!=metadata['model_version']:raise ValueError('Different prospect model')
        targets={r['employer_id'] for r in outcomes if r['state']=='not_yet_reached_by_tested_profiles'}
        truncated=Counter();example={};retrieval_capped=0;start=time.monotonic()
        for i,row in enumerate(profiles,1):
            audit={}
            matcher.search(Profile.model_validate(row['profile']),audit=audit)
            retrieval_capped+=int(audit['retrieval_employer_cap'])
            for eid in targets.intersection(audit['eligible_below_shortlist_limit']):
                truncated[eid]+=1;example.setdefault(eid,row['profile_id'])
            if i%100==0:print(json.dumps({'profiles_replayed':i,'unreached_eligible_below_cap':len(truncated)}),flush=True)
        rows=[]
        for row in outcomes:
            if row['employer_id'] not in targets:continue
            eid=row['employer_id']
            rows.append({'employer_id':eid,'name':row['name'],
                         'diagnosis':'eligible_below_saved_shortlist_limit' if eid in truncated else 'no_eligible_result_in_replayed_profiles',
                         'eligible_below_limit_appearances':truncated[eid],
                         'example_profile_id':example.get(eid)})
        result={'run_id':summary['run_id'],'ranking_version':VERSION,'profiles_replayed':len(profiles),
                'unreached_professional_records':len(targets),'diagnoses':dict(Counter(r['diagnosis'] for r in rows)),
                'profiles_hitting_retrieval_employer_cap':retrieval_capped,
                'elapsed_seconds':round(time.monotonic()-start,2),
                'note':'Eligibility is algorithmic, not independently judged relevance. No ranking gate or shortlist cap was changed.',
                'employers':rows}
        (folder/'gap-diagnosis.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='employers'},indent=2))
    finally:db.close()


if __name__=='__main__':main()
