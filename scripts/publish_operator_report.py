"""Publish only synthetic/public experiment artifacts to a local operator report."""
import argparse,html,json,re,shutil,hashlib
from pathlib import Path


def validate_interest_review(source):
    source=Path(source)
    review=json.loads((source/'ai-development-review.json').read_text())
    checksum=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
    for name,field in [('runs.json','runs_hash'),('sampling.json','sampling_hash')]:
        if review.get(field)!=checksum(json.loads((source/name).read_text())):
            raise ValueError('Interest review does not describe its frozen inputs')


def validate_encoder_probe(source,coverage,metadata):
    source=Path(source);manifest=json.loads((source/'manifest.json').read_text());result=json.loads((source/'summary.json').read_text())
    checksum=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
    if result.get('manifest_hash')!=checksum(manifest):raise ValueError('Encoder comparison manifest changed')
    versions=manifest['versions']
    if versions.get('ranking')!=coverage['ranking_version'] or versions.get('prospect_model')!=coverage['model_version'] or versions.get('snapshot')!=metadata['snapshot']:raise ValueError('Encoder comparison uses different evidence versions')
    for name in ['minilm','bge']:
        if result.get('pair_output_hashes',{}).get(name)!=checksum(json.loads((source/(name+'-pairs.json')).read_text())):raise ValueError('Encoder comparison pair features changed')


def main():
    p=argparse.ArgumentParser();p.add_argument('--matrix',required=True);p.add_argument('--coverage',required=True);p.add_argument('--cohorts',required=True);p.add_argument('--nli',required=True);p.add_argument('--output',required=True);p.add_argument('--tests',type=int,required=True);p.add_argument('--fresh');p.add_argument('--relation-probe');p.add_argument('--linkage-repair');p.add_argument('--title-probe');p.add_argument('--tie-probe');p.add_argument('--source-probe');p.add_argument('--interest-matrix');p.add_argument('--encoder-probe');args=p.parse_args()
    matrix,coverage=Path(args.matrix),Path(args.coverage)
    summary=json.loads((coverage/'summary.json').read_text());quality=json.loads((matrix/'ai-development-review.json').read_text());cohorts=json.loads((Path(args.cohorts)/'summary.json').read_text());nli=json.loads((Path(args.nli)/'summary.json').read_text());gap=json.loads((coverage/'gap-diagnosis.json').read_text())
    metadata=json.loads((coverage/'run-metadata.json').read_text())
    readiness=None
    if (coverage/'profile-readiness-audit.json').exists():
        readiness=json.loads((coverage/'profile-readiness-audit.json').read_text())
        if readiness['source_run']!=summary['run_id'] or readiness['ranking_version']!=summary['ranking_version'] or readiness['source_model']!=summary['model_version'] or readiness['source_hash']!=metadata['source_hash']:raise ValueError('Profile-readiness audit belongs to a different run')
        if readiness['valid_reached']!=summary['total_reached'] or readiness['valid_preview_reached']>summary['preview_reached'] or readiness['valid_top10_reached']>summary['top10_reached'] or readiness['valid_profiles']+readiness['needs_clarification_profiles']!=readiness['raw_profiles']:raise ValueError('Readiness counts are inconsistent; rerun the confirmed-profile audit')
    if metadata['ranking_version']!=summary['ranking_version'] or metadata['model_version']!=summary['model_version']:raise ValueError('Coverage metadata differs from its summary')
    if gap['run_id']!=summary['run_id'] or gap['ranking_version']!=summary['ranking_version']:raise ValueError('Gap diagnosis belongs to a different experiment')
    def validate_matrix(source):
        rows=json.loads((source/'runs.json').read_text())
        if not rows or any(r['versions'].get('ranking')!=summary['ranking_version'] or r['versions'].get('prospect_model')!=summary['model_version'] or r['versions'].get('snapshot')!=metadata['snapshot'] for r in rows):
            raise ValueError('Quality and coverage artifacts must use the same ranking, source model and register snapshot')
        review=json.loads((source/'ai-development-review.json').read_text())
        if review['ranking_version']!=summary['ranking_version'] or review['source_model']!=summary['model_version']:raise ValueError('Review labels describe a different ranking or source model')
    validate_matrix(matrix)
    if args.fresh:validate_matrix(Path(args.fresh))
    if args.interest_matrix:
        validate_matrix(Path(args.interest_matrix));validate_interest_review(args.interest_matrix)
    if args.encoder_probe:validate_encoder_probe(args.encoder_probe,summary,metadata)
    if set(cohorts['models'])!={summary['model_version']}:raise ValueError('Cohort sensitivity uses a different source model')
    inventory={}
    def include(source,target,names):
        for name in names:
            path=Path(source)/name
            if path.exists():inventory[(target+'/'+name).lstrip('/')]=path
    include(matrix,'review',['report.html','runs.json','summary.json','review-packet.json','ai-anchor-reviews.json','ai-development-review.json','version-comparison.json','new-anchor-admissions.json','admission-audit.json','new-pair-ai-audit.json','niche-regression-check.json'])
    include(coverage,'coverage',['report.html','summary.json','employer-coverage.json','generated-profiles.json','gap-diagnosis.json','run-metadata.json','exposure-changes.json','release-decision.json','profile-clarifications.json','new-reach-review.json','new-reach-ai-review.json'])
    include(args.cohorts,'cohorts',['summary.json','associations.json']);include(args.nli,'nli',['summary.json'])
    if readiness:include(coverage/'confirmed-profiles','confirmed',['report.html','summary.json','employer-coverage.json','generated-profiles.json','profile-readiness-audit.json'])
    if args.fresh:include(args.fresh,'fresh',['report.html','runs.json','summary.json','review-packet.json','ai-anchor-reviews.json','ai-development-review.json','version-comparison.json','forms.json','selection.json'])
    if args.interest_matrix:include(args.interest_matrix,'interests',['report.html','runs.json','summary.json','review-packet.json','ai-anchor-reviews.json','ai-development-review.json','forms.json','sampling.json','clarifications.json'])
    if args.encoder_probe:include(args.encoder_probe,'encoders',['report.html','summary.json','manifest.json','minilm-pairs.json','bge-pairs.json'])
    if args.relation_probe:include(args.relation_probe,'relation-probe',['summary.json','manifest.json','predictions.json'])
    if args.title_probe:include(args.title_probe,'title-probe',['summary.json','pairs.json'])
    if args.tie_probe:include(args.tie_probe,'tie-probe',['summary.json','profiles.json'])
    if args.source_probe:include(args.source_probe,'source-probe',['summary.json','manifest.json','annotations.json','pairs.json','review-findings.json'])
    if args.linkage_repair:inventory['linkage-repair-verification.json']=Path(args.linkage_repair)/'verification.json'
    publication_files={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in inventory.items()}
    publication_hash=hashlib.sha256(json.dumps([publication_files,args.tests,hashlib.sha256(Path(__file__).read_bytes()).hexdigest()],sort_keys=True).encode()).hexdigest()
    version=re.sub('[^a-zA-Z0-9_-]','-',summary['ranking_version']+'--'+summary['model_version']+'--'+summary['run_id'][:8]+'--'+publication_hash[:12]);root=Path(args.output);folder=root/version;folder.mkdir(parents=True,exist_ok=True)
    # Deliberate allowlists exclude real-user cohort reports and any .env/DB data.
    for source,target,names in [
        (matrix,folder/'review',['report.html','runs.json','summary.json','review-packet.json','ai-anchor-reviews.json','ai-development-review.json']),
        (coverage,folder/'coverage',['report.html','summary.json','employer-coverage.json','generated-profiles.json','gap-diagnosis.json','run-metadata.json']),
        (Path(args.cohorts),folder/'cohorts',['summary.json','associations.json']),
        (Path(args.nli),folder/'nli',['summary.json']),
    ]:
        target.mkdir(exist_ok=True)
        for name in names:shutil.copy2(source/name,target/name)
    for name in ['version-comparison.json','new-anchor-admissions.json','admission-audit.json','new-pair-ai-audit.json','niche-regression-check.json']:
        if (matrix/name).exists():shutil.copy2(matrix/name,folder/'review'/name)
    if (coverage/'profile-clarifications.json').exists():shutil.copy2(coverage/'profile-clarifications.json',folder/'coverage'/'profile-clarifications.json')
    if (coverage/'exposure-changes.json').exists():shutil.copy2(coverage/'exposure-changes.json',folder/'coverage'/'exposure-changes.json')
    if readiness:
        target=folder/'confirmed';target.mkdir(exist_ok=True)
        for name in ['report.html','summary.json','employer-coverage.json','generated-profiles.json','profile-readiness-audit.json']:shutil.copy2(coverage/'confirmed-profiles'/name,target/name)
    if (coverage/'release-decision.json').exists():shutil.copy2(coverage/'release-decision.json',folder/'coverage'/'release-decision.json')
    new_reach=None
    if (coverage/'new-reach-ai-review.json').exists():
        new_reach=json.loads((coverage/'new-reach-ai-review.json').read_text())
        if new_reach['source_sha256']!=hashlib.sha256((coverage/'new-reach-review.json').read_bytes()).hexdigest():raise ValueError('New-reach review does not describe these exact pairs')
        for name in ['new-reach-review.json','new-reach-ai-review.json']:shutil.copy2(coverage/name,folder/'coverage'/name)
    fresh=None
    if args.fresh:
        source=Path(args.fresh);fresh=json.loads((source/'ai-development-review.json').read_text())
        if fresh['ranking_version']!=summary['ranking_version']:raise ValueError('Fresh audit and coverage ranking versions differ')
        target=folder/'fresh';target.mkdir(exist_ok=True)
        for name in ['report.html','runs.json','summary.json','review-packet.json','ai-anchor-reviews.json','ai-development-review.json','version-comparison.json','forms.json','selection.json']:
            if (source/name).exists():shutil.copy2(source/name,target/name)
    interests=None
    if args.interest_matrix:
        source=Path(args.interest_matrix);interests=json.loads((source/'ai-development-review.json').read_text())
        target=folder/'interests';target.mkdir(exist_ok=True)
        for name in ['report.html','runs.json','summary.json','review-packet.json','ai-anchor-reviews.json','ai-development-review.json','forms.json','sampling.json','clarifications.json']:
            if (source/name).exists():shutil.copy2(source/name,target/name)
    if args.encoder_probe:
        target=folder/'encoders';target.mkdir(exist_ok=True)
        for name in ['report.html','summary.json','manifest.json','minilm-pairs.json','bge-pairs.json']:shutil.copy2(Path(args.encoder_probe)/name,target/name)
    relation_probe=None
    if args.relation_probe:
        source=Path(args.relation_probe);relation_probe=json.loads((source/'summary.json').read_text())
        target=folder/'relation-probe';target.mkdir(exist_ok=True)
        for name in ['summary.json','manifest.json','predictions.json']:shutil.copy2(source/name,target/name)
    linkage_repair=None
    if args.linkage_repair:
        source=Path(args.linkage_repair)/'verification.json';linkage_repair=json.loads(source.read_text())
        if not linkage_repair['applied'] or not linkage_repair['eligible_after']:raise ValueError('Linkage repair is not verified')
        if linkage_repair['snapshot']!=metadata['snapshot']:raise ValueError('Linkage repair and evaluation use different register snapshots')
        # The full backup is deliberately excluded; only public aggregate
        # verification flags are copied to the operator bundle.
        shutil.copy2(source,folder/'linkage-repair-verification.json')
    title_probe=None
    if args.title_probe:
        source=Path(args.title_probe);title_probe=json.loads((source/'summary.json').read_text())
        if title_probe['source_model']!=summary['model_version']:raise ValueError('Title probe uses another source model')
        target=folder/'title-probe';target.mkdir(exist_ok=True)
        for name in ['summary.json','pairs.json']:shutil.copy2(source/name,target/name)
    tie_probe=None
    if args.tie_probe:
        source=Path(args.tie_probe);tie_probe=json.loads((source/'summary.json').read_text())
        if tie_probe['source_model']!=summary['model_version'] or tie_probe['evaluated_ranking']!=summary['ranking_version']:raise ValueError('Shortlist tie probe uses another model or ranking')
        target=folder/'tie-probe';target.mkdir(exist_ok=True)
        for name in ['summary.json','profiles.json']:shutil.copy2(source/name,target/name)
    source_probe=None
    source_review=None
    if args.source_probe:
        source=Path(args.source_probe);source_probe=json.loads((source/'summary.json').read_text())
        if source_probe['source_model']!=summary['model_version'] or source_probe['ranking_version']!=summary['ranking_version']:raise ValueError('Source-only probe uses another model or ranking')
        target=folder/'source-probe';target.mkdir(exist_ok=True)
        for name in ['summary.json','manifest.json','annotations.json','pairs.json']:shutil.copy2(source/name,target/name)
        if (source/'review-findings.json').exists():
            source_review=json.loads((source/'review-findings.json').read_text())
            annotations=json.loads((source/'annotations.json').read_text())
            if source_review['annotations_sha256']!=hashlib.sha256(json.dumps(annotations,sort_keys=True,default=str).encode()).hexdigest():raise ValueError('Source review does not describe these annotations')
            shutil.copy2(source/'review-findings.json',target/'review-findings.json')
    manifest={'ranking_version':summary['ranking_version'],'source_model':summary['model_version'],'source_hash':metadata['source_hash'],'register_snapshot':metadata['snapshot'],'ranking_source_hash':metadata['ranking_source_hash'],'proposal_version':metadata['proposal_version'],'evaluated_date':metadata['evaluated_date'],'coverage_run':summary['run_id'],'matrix':matrix.name,'fresh_matrix':Path(args.fresh).name if args.fresh else None,'private_user_artifacts_included':False}
    manifest.update(publication_hash=publication_hash,publication_files=publication_files,interest_matrix=Path(args.interest_matrix).name if args.interest_matrix else None,encoder_probe=Path(args.encoder_probe).name if args.encoder_probe else None)
    if readiness:manifest.update(profile_evaluation_policy=readiness['policy'],profile_evaluation_policy_hash=readiness['policy_hash'])
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
    esc=lambda x:html.escape(str(x))
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SponsorReach matching laboratory</title><style>body{font:16px/1.5 system-ui;color:#103e54;background:#f6f9f8;max-width:1050px;margin:40px auto;padding:0 22px}h1{font-size:38px;letter-spacing:-1px}nav{display:flex;gap:16px;flex-wrap:wrap}a{color:#087e76}section{background:white;border:1px solid #dbe7e7;border-radius:16px;padding:24px;margin:20px 0}.stats{display:flex;gap:24px;flex-wrap:wrap}.stats strong{display:block;font-size:30px}.stats span{color:#526d78}li{margin:10px 0}small{color:#526d78}</style><h1>SponsorReach matching laboratory</h1><p>Versioned tests of the real employer catalogue. The semantic engine is experimental; the website retains its current baseline ranking.</p><nav><a href="http://127.0.0.1:3000/match">Open website</a>'''
    base=esc(version)
    coverage_link='confirmed/report.html' if readiness else 'coverage/report.html'
    page+='<a href="'+base+'/review/report.html">Review forms and results</a><a href="'+base+'/'+coverage_link+'">Every employer and its reachability</a></nav><section class="stats">'
    for value,label in [(summary['total_reached'],'employers reached'),(readiness['valid_profiles'] if readiness else gap['profiles_replayed'],'confirmed test profiles' if readiness else 'profiles evaluated'),(readiness['valid_preview_reached'] if readiness else summary['preview_reached'],'employers in top three'),(args.tests,'passing backend tests')]:page+='<div><strong>'+esc(value)+'</strong><span>'+esc(label)+'</span></div>'
    page+='</section><p>Completed coverage: '+esc(summary['ranking_version'])+' · source model '+esc(summary['model_version'])+'.</p>'
    if readiness:page+='<p>'+esc(readiness['raw_profiles'])+' raw diagnostic calls; '+esc(readiness['needs_clarification_profiles'])+' requiring clarification excluded from confirmed-profile frequencies. Company reach is unchanged by this correction. <a href="'+base+'/confirmed/profile-readiness-audit.json">Readiness audit</a> · <a href="'+base+'/coverage/report.html">Original raw trials</a>.</p>'
    if (coverage/'profile-clarifications.json').exists():
        rejected=json.loads((coverage/'profile-clarifications.json').read_text())
        page+='<p>'+esc(len(rejected))+' proposed profiles required clarification and were withheld before matching. <a href="'+base+'/coverage/profile-clarifications.json">Withheld inputs</a>.</p>'
    release_path=coverage/'release-decision.json'
    if release_path.exists():
        decision=json.loads(release_path.read_text())
        if decision['ranking_version']!=summary['ranking_version'] or decision['source_model']!=summary['model_version'] or decision['coverage_run']!=summary['run_id']:raise ValueError('Release decision belongs to another run')
        page+='<section><h2>Promotion decision: '+('promoted' if decision['promoted'] else 'not promoted')+'</h2><ul>'+''.join('<li>'+esc(reason)+'</li>' for reason in decision['reasons'])+'</ul><a href="'+base+'/coverage/release-decision.json">Recorded decision</a></section>'
    previous=[]
    for path in sorted(root.glob('*/manifest.json')):
        if path.parent==folder:continue
        prior=json.loads(path.read_text())
        previous.append('<li>'+esc(prior['ranking_version'])+' · <a href="'+esc(path.parent.name)+'/review/report.html">forms</a> · <a href="'+esc(path.parent.name)+'/coverage/report.html">coverage</a></li>')
    if previous:page+='<details><summary>Previous completed report bundles</summary><ul>'+''.join(previous)+'</ul></details>'
    page+='<section><h2>Coverage remains incomplete</h2><ul>'
    for state,count in summary['outcome_counts'].items():page+='<li>'+esc(state.replace('_',' '))+': <strong>'+esc(count)+'</strong></li>'
    page+='</ul><p>Among unreached professional records: '+esc(gap['diagnoses'].get('eligible_below_saved_shortlist_limit',0))+' qualified below the saved-shortlist limit; '+esc(gap['diagnoses'].get('no_eligible_result_in_replayed_profiles',0))+' had no eligible result in these tests.</p></section>'
    if linkage_repair:
        page+='<section><h2>Verified register-linkage correction</h2><p>'+esc(linkage_repair['targets'])+' employer links reconciled. Employer IDs, business facts, contacts, embeddings and saved results were preserved. No employers were merged or deleted.</p><a href="'+base+'/linkage-repair-verification.json">Verification</a> · <a href="'+base+'/manifest.json">Exact report versions</a></section>'
    page+='<section><h2>Quality review</h2><p>'+esc(quality['judged_pairs'])+' anchor pairs inspected by AI: '+esc(quality['labels'])+'. Independent human reviews: 0. These development judgments do not establish release accuracy.</p><a href="'+base+'/review/ai-development-review.json">Review metrics and limitations</a></section>'
    if quality.get('admission_audit'):
        audit=quality['admission_audit']
        page+='<section><h2>New admissions audit</h2><p>'+esc(audit['judged_pairs'])+' lower-shortlist additions reviewed by AI: '+esc(audit['labels'])+'. '+esc(audit['reason'])+'</p><a href="'+base+'/review/admission-audit.json">Evidence and individual judgments</a> · <a href="'+base+'/review/version-comparison.json">Version and optional-field comparison</a></section>'
    if fresh:
        precision=fresh['precision_at3']['precision_at_k']
        page+='<section><h2>Broader occupation check: quality gate failed</h2><p>27 additional occupation profiles across all nine major groups. AI reviewed '+esc(fresh['judged_pairs'])+' returned top-three pairs: '+esc(fresh['labels'])+'. Mean returned direct Precision@3: '+esc(round(100*precision,1))+'%. This development sample informed tuning and is not held-out or independent human validation.</p><p>These gaps prevent promotion even when the original test families perform well.</p><a href="'+base+'/fresh/report.html">Inspect broader profiles and source evidence</a> · <a href="'+base+'/fresh/ai-development-review.json">Broader review metrics</a></section>'
    if new_reach:
        page+='<section><h2>Inspecting newly reached employers</h2><p>All '+esc(len(new_reach['labels']))+' new employer/profile pairs replayed successfully. AI development inspection marked '+esc(new_reach['direct'])+' direct, '+esc(new_reach['related'])+' related and '+esc(new_reach['insufficient'])+' insufficient. These targeted pairs are not an accuracy estimate. Generic architecture does not establish landscape design, and business ownership does not establish an employment function.</p><a href="'+base+'/coverage/new-reach-review.json">Exact new pairs and sources</a> · <a href="'+base+'/coverage/new-reach-ai-review.json">AI review and limitations</a></section>'
    if interests:
        sampling=json.loads((Path(args.interest_matrix)/'sampling.json').read_text())
        precision=interests['precision_at3']['precision_at_k']
        page+='<section><h2>Occupation-stratified interest tests</h2><p>'+esc(sampling['profiles'])+' form variants across '+esc(len(sampling['selected_references']))+' sampled official occupations and '+esc(sampling['major_families'])+' major families. AI inspected '+esc(interests['judged_pairs'])+' top-three pairs; mean returned direct Precision@3: '+esc(round(100*precision,1))+'%. These are development judgments, not human validation or a release estimate. The sample exposes equipment-versus-occupation and sector-versus-function failures.</p><a href="'+base+'/interests/report.html">Inspect new profiles and evidence</a> · <a href="'+base+'/interests/ai-development-review.json">Metrics and limitations</a></section>'
    if args.encoder_probe:
        page+='<section><h2>Free local encoder comparison</h2><p>Pinned MiniLM and BGE-small were compared on 255 AI-labelled development pairs. Cutoffs selected from 204 older pairs were checked on 51 newer pairs, with whole-source and matched-span views. Neither model resolves professional evidence attribution sufficiently to justify replacement or a new gate.</p><a href="'+base+'/encoders/report.html">Inspect model comparison and rejected supported pairs</a></section>'
    if relation_probe:
        percentage=lambda value:'not measured' if value is None else f'{100*value:.1f}%'
        page+='<section><h2>Local evidence interpretation probe</h2><p>'+esc(relation_probe['pairs'])+' AI-reviewed pairs assessed locally. Direct-judgment precision: '+esc(percentage(relation_probe['direct_judgment_precision']))+'; direct-judgment recall: '+esc(percentage(relation_probe['direct_judgment_recall']))+'. This measures agreement with development labels, not independent human accuracy or retrieval recall. The model remains outside live matching.</p><a href="'+base+'/relation-probe/summary.json">Results and limitations</a> · <a href="'+base+'/relation-probe/predictions.json">Predictions and source quotes</a></section>'
        page+='<p><small>This historical query-conditioned probe uses a different pair set; its figures are not the current retrieval metrics.</small></p>'
    if title_probe:
        family_aware=title_probe.get('family_aware',False)
        title='Occupation-family title diagnostic' if family_aware else 'Rejected official-title competition rule'
        scope='The family-aware variant is evaluated only in the offline semantic experiment.' if family_aware else 'The simple title-only rule is rejected and is not integrated.'
        page+='<section><h2>'+title+'</h2><p>'+esc(title_probe['official_unique_titles'])+' official occupation titles and aliases compared with '+esc(title_probe['pairs'])+' AI-reviewed pairs. The proposed rule rejected '+esc(title_probe['rejected'].get('direct',0))+' direct pairs while removing '+esc(title_probe['rejected'].get('irrelevant',0))+' irrelevant pair. This is development-set agreement, not independent human accuracy. '+scope+'</p><a href="'+base+'/title-probe/summary.json">Diagnostic summary</a> · <a href="'+base+'/title-probe/pairs.json">Individual comparisons</a></section>'
    if tie_probe:
        detail=''
        if 'unique_hidden_after_source_context_comparison' in tie_probe:detail='After comparing source context too, '+esc(tie_probe['unique_hidden_after_source_context_comparison'])+' employers remained hidden in exact ordering ties in this sample. '
        page+='<section><h2>Primary-score shortlist ties</h2><p>'+esc(tie_probe['unique_eligible_employers_hidden_in_exact_cutoff_ties'])+' eligible employers were hidden in equal-primary-score cutoff groups across '+esc(tie_probe['profiles_tested'])+' selected diagnostic profiles; '+esc(tie_probe['unique_previously_unreached_in_exact_cutoff_ties'])+' were unreached in the source coverage experiment. '+detail+'This is not an exhaustive count. The diagnostic did not change rankings or saved results.</p><a href="'+base+'/tie-probe/summary.json">Tie diagnosis</a></section>'
    if source_probe:
        findings='<ul>'+''.join('<li>'+esc(item)+'</li>' for item in source_review['findings'])+'</ul>' if source_review else ''
        page+='<section><h2>Source-only local extraction diagnostic</h2><p>'+esc(source_probe['sources'])+' development sources processed without candidate roles, taxonomy definitions or review labels in the model prompt. '+esc(source_probe['valid_sources'])+' outputs passed schema/exact-quote validation; that does not establish semantic correctness. The classifier remains outside live matching.</p>'+findings+'<a href="'+base+'/source-probe/summary.json">Results and limitations</a> · <a href="'+base+'/source-probe/annotations.json">Source annotations</a></section>'
    page+='<section><h2>Prospect cohorts</h2><p>'+esc(cohorts['profiles_with_association'])+' of '+esc(cohorts['profiles'])+' form variants received an interest association. Ambiguous interests remain unresolved. Inferred interest groups do not assert skills or credentials.</p><a href="'+base+'/cohorts/summary.json">Synthetic cohort sensitivity</a></section>'
    page+='<section><h2>Rejected model experiment</h2><p>A historical local language-inference probe accepted only '+esc(nli['direct']['entailed'])+' of '+esc(nli['direct']['pairs'])+' AI-reviewed direct pairs, while still accepting weak cases. This different pair set is not the current retrieval evaluation. It remains outside live matching.</p><a href="'+base+'/nli/summary.json">Probe results</a></section><small>Public employer evidence and synthetic test inputs only. Private candidate identities and session identifiers are excluded from this report bundle.</small></html>'
    for name,expected in publication_files.items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=expected:raise ValueError('Publication input changed while copying; previous dashboard remains active')
    temp=root/'index.tmp';temp.write_text(page);temp.replace(root/'index.html')
    print(json.dumps({'report':str((root/'index.html').resolve()),'ranking_version':summary['ranking_version'],'bundle':version,'private_user_artifacts_included':False}))


if __name__=='__main__':main()
