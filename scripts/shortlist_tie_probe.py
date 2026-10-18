"""Measure exact-score ties behind the shortlist cap, without changing ranks."""
import argparse,json,importlib.util
from pathlib import Path
from sponsor_match.config import Settings
from sponsor_match.coverage import CoverageLedger
from sponsor_match.db import Database
from sponsor_match.intelligence import digest
from sponsor_match.models import Profile
from sponsor_match import semantic_search
from sponsor_match.exposure_order import profile_tie_shortlist,semantic_source_context,VERSION as TIE_VERSION,SOURCE_VERSION


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--coverage-folder',required=True)
    parser.add_argument('--model-folder',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--simulate-profile-order',action='store_true')
    parser.add_argument('--source-context',action='store_true')
    parser.add_argument('--ranking-source',help='Optional frozen local matcher source for historical diagnostic replay')
    args=parser.parse_args();folder=Path(args.coverage_folder)
    if args.source_context and not args.simulate_profile_order:raise ValueError('Source context is an offline ordering simulation')
    summary=json.loads((folder/'summary.json').read_text());gap=json.loads((folder/'gap-diagnosis.json').read_text())
    metadata,profiles=CoverageLedger(folder.parent/'coverage.sqlite3').saved_run(summary['run_id'])
    target_profiles={r['example_profile_id'] for r in gap['employers'] if r['diagnosis']=='eligible_below_saved_shortlist_limit'}
    targets={r['employer_id'] for r in gap['employers'] if r['diagnosis']=='eligible_below_saved_shortlist_limit'}
    settings=Settings.from_env();db=Database(settings.database_url);db.open()
    engine=semantic_search
    if args.ranking_source:
        spec=importlib.util.spec_from_file_location('sponsor_match.frozen_tie_probe',args.ranking_source)
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    original=engine.interleave_intents
    try:
        current={str(r['id']):r['version'] for r in db.rows("select id,version from sm.employers where not is_demo and payload->>'matching_basis'='provided_csv'")}
        if digest(current)!=metadata['source_hash'] or db.active_snapshot()!=metadata['snapshot']:raise ValueError('Evidence changed; rerun the source coverage experiment')
        matcher=engine.SemanticMatcher(db,settings,args.model_folder)
        if matcher.manifest['version']!=metadata['model_version']:raise ValueError('Source model mismatch')
        captured=[]
        def capture(results,intents,limit):
            captured[:]=results
            return original(results,intents,limit)
        engine.interleave_intents=capture
        rows=[];skipped=0;hidden=set();full_hidden=set();alternate_exposure=set();baseline_exposure=set()
        for row in profiles:
            if row['profile_id'] not in target_profiles:continue
            profile=Profile.model_validate(row['profile'])
            if len(profile.role_intents)!=1:skipped+=1;continue
            audit={'include_eligible_results':True}
            results,_,versions=matcher.search(profile,audit=audit)
            if 'eligible_results' in audit:captured[:]=audit['eligible_results']
            if len(captured)!=audit['eligible_before_shortlist_limit']:raise ValueError('This matcher did not expose its full eligible result set')
            saved={r.employer_id for r in results}
            cutoff=results[-1].score if len(results)==100 else None
            tied=[r.employer_id for r in captured if cutoff is not None and r.score==cutoff]
            omitted=[eid for eid in tied if eid not in saved];hidden.update(omitted)
            cutoff_context=(results[-1].features.get('source_context_tie_similarity') or 0.) if cutoff is not None else None
            full_tied=[r.employer_id for r in captured if cutoff is not None and r.score==cutoff and (r.features.get('source_context_tie_similarity') or 0.)==cutoff_context]
            fully_omitted=[eid for eid in full_tied if eid not in saved];full_hidden.update(fully_omitted)
            entry={'profile_id':row['profile_id'],'profile':profile.model_dump(mode='json'),'eligible':len(captured),'returned':len(results),'cutoff_score':cutoff,'exact_cutoff_tie_size':len(tied),'unreturned_exact_ties':omitted,'versions':versions}
            entry.update(cutoff_source_context_similarity=cutoff_context,full_ordering_tie_size=len(full_tied),unreturned_full_ordering_ties=fully_omitted)
            if args.simulate_profile_order:
                source_scores={}
                if args.source_context:
                    all_employers={e.id:e for e in db.employers([r.employer_id for r in captured])}
                    texts=[semantic_source_context(r.explanation['sources'][0]['excerpt'],all_employers[r.employer_id].name) for r in captured]
                    vectors=matcher.context_store.encode(texts)
                    query=matcher.provider.embeddings([profile.search_text()])[0]
                    source_scores={r.employer_id:float(vector@query) for r,vector,text in zip(captured,vectors,texts) if text}
                alternate=profile_tie_shortlist(captured,profile,100,source_scores)
                assert sorted(r.score for r in alternate)==sorted(r.score for r in results)
                alternate_exposure.update(r.employer_id for r in alternate);baseline_exposure.update(saved)
                employers={e.id:e for e in db.employers(list({r.employer_id for r in results[:3]+alternate[:3]}))}
                def display(values):
                    return [{'employer_id':r.employer_id,'name':employers[r.employer_id].name,'score':r.score,'source_context_similarity':source_scores.get(r.employer_id),'explanation':r.explanation} for r in values[:3]]
                entry.update(baseline_preview=display(results),alternate_preview=display(alternate),alternate_shortlist=[r.employer_id for r in alternate],newly_selected_in_this_profile=sorted({r.employer_id for r in alternate}-saved))
            rows.append(entry)
        result={'source_coverage_run':summary['run_id'],'source_ranking':summary['ranking_version'],'evaluated_ranking':engine.VERSION,'source_model':metadata['model_version'],'source_hash':metadata['source_hash'],'profiles_tested':len(rows),'multi_intent_profiles_skipped':skipped,'unique_eligible_employers_hidden_in_exact_cutoff_ties':len(hidden),'unique_previously_unreached_in_exact_cutoff_ties':len(hidden&targets),'tie_breaking_changed':False,'note':'Selected diagnostic profiles from the earlier cap-gap audit, not exhaustive coverage or relevance validation. No scores, gates, rank order or saved results changed.'}
        result.update(tie_dimension='primary_score',unique_hidden_after_source_context_comparison=len(full_hidden),unique_previously_unreached_in_full_ordering_ties=len(full_hidden&targets))
        if args.simulate_profile_order:
            result.update(simulation_policy=SOURCE_VERSION if args.source_context else TIE_VERSION,simulation_only=True,baseline_selected_exposure=len(baseline_exposure),alternate_selected_exposure=len(alternate_exposure),previously_unreached_selected_by_alternate=len(alternate_exposure&targets),previously_unreached_selected_by_baseline=len(baseline_exposure&targets),newly_exposed_vs_selected_baseline=len(alternate_exposure-baseline_exposure),selected_baseline_exposure_lost=len(baseline_exposure-alternate_exposure),relevance_accuracy_measured=False)
        out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
        (out/'profiles.json').write_text(json.dumps(rows,indent=2));(out/'summary.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
    finally:
        engine.interleave_intents=original
        db.close()


if __name__=='__main__':main()
