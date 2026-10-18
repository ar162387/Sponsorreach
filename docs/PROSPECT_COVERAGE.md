# Corpus-driven prospect discovery and coverage — 17 October 2026

The objective remains active. All 7,309 retained CSV employers are indexed with 9,137 free local MiniLM embeddings. Index coverage is not supported professional recommendation coverage. The 201 no-outreach records remain archived.

## What is live

- Website: http://127.0.0.1:3000/match, compiled standalone build with the existing email verification and owned shortlist access.
- Employer matching: `evidence-11-general-role-context`. Its existing phrase/seed gates have **not** been represented as a completed general semantic replacement.
- Career ideas: corpus model `9b488fb7cad26af82c3b3735` (`prospect-discovery-5`), published only for career-idea assistance. Users explicitly select interests/specializations; no degree, skill or certification is asserted automatically.
- Imports remain manually supplied CSV batches. No scraper connection, paid model invocation, payment collection or private candidate export was added.

## Completed coverage experiments

| Version | Saved-shortlist reach | Top-three reach | Top-ten reach | Status |
| --- | ---: | ---: | ---: | --- |
| Current matcher, initial 516-profile replay + 200 generated profiles | 1,370 | 166 | 406 | Earlier completed baseline |
| Semantic experiment 5, all-facet extension | 4,952 | 1,307 | 2,726 | Development experiment; known false positives |
| Semantic experiment 7, all-facet extension | 4,620 | 1,384 | 2,710 | Earlier development experiment |
| Semantic experiment 8, multiple evidence alternatives | 4,618 | 1,365 | 2,699 | Latest development experiment; not promoted |

Experiment 7 reran the prior profile pool and generated 1,865 more hypotheses. The run stopped after exhausting the profiles produced by this proposal algorithm, not after proving that no conceivable candidate could reach another record. Its current-version outcomes account for every retained employer:

| Outcome | Employers |
| --- | ---: |
| Reached in a saved shortlist | 4,620 |
| Professional observations exist, but no returned result for tested profiles | 1,350 |
| Current sponsor linkage required | 547 |
| Professional descriptors required, after preceding gates | 782 |
| Useful channel required | 10 |

There are 848 identity/contact-only records overall; these outcome categories apply gates in order. Some of those 848 are counted under sponsor linkage instead. No gate was removed to force full coverage.

Version 7 shares 4,595 reached employers with version 5, adds 25 and no longer returns 357. This is a change in algorithmic exposure, not 357 independently proven false positives. Narrower evidence-relation checks reduced total reach while increasing the number of distinct employers seen in the top three.

Operator reports:

- Current experimental reachability: http://127.0.0.1:4018/report.html
- Full-form results, source excerpts, recorded contacts and exportable review labels: http://127.0.0.1:4017/report.html
- Earlier version-5 reachability: http://127.0.0.1:4016/report.html

Reports are static local operator artifacts. They are not public catalogue or locked-result endpoints.

## Generalized semantic experiment

`semantic_search.py` is an offline experiment. It does not use `SEEDS` or `ACTIVITY_SYNONYMS`. It compares accepted role/activity spans with the candidate's explicit role and background, using 1,181 official ONS occupation descriptions and official aliases as data.

The source model contains 24,339 unique phrases, 38,823 observations, 3,516 provisional occupation groups and 27,141 evidence associations covering 6,194 employers. Associations are derived hypotheses, not independently verified employer functions. Raw spans are retained per observation so shared normalized phrases cannot borrow another employer's citation.

The experiment distinguishes occupation wording, task alignment and source relation. Generic semantic relation templates contrast performing work with teaching its subject, selling related products and membership associations. It checks the full accepted activity description as well as the retrieved phrase. Full-description embeddings are cached by content and pinned encoder, without paid API calls. Generic one-word role fragments are detected through ambiguity across official occupation vocabulary, rather than a hand-picked list of professions.

A reliable competing occupational category can reject unrelated activities. Close categories with strong direct wording remain possible; a nearest-category decision alone had incorrectly removed software, nursing and plumbing services during development. SOC major-group metadata prevents a generic sector from automatically establishing a management function.

Identity, current sponsor authorization, useful channel, source ownership/version and verbatim citation gates remain. Historical advertisements stay historical; no active-vacancy badge is inferred. Related-career retrieval is not implemented in this experimental matcher and must be completed before promotion.

## Form testing and quality findings

The latest complete matrix tested **272 profiles across 16 families**, including minimal/full forms, removing individual optional fields, career stages, location changes, synonyms, transferable skills, multiple intents and related-career opt-in. Every input and top-ten result is retained.

Compared with each family's full form, removing skills changed the top three in 3/16 cases, removing specialization in 2/16, removing experience in 2/16 and changing to the supplied synonym in 5/16. Adding a second role changed the top three in all 16. These are sensitivity observations, not proofs of desirable behavior. Synonym consistency still needs improvement without collapsing specialized occupations into broad buckets.

A manual AI development review inspected all **145 returned top-ten anchor pairs** from 15 nonempty profiles: 141 direct, three insufficient-evidence and one related-career result incorrectly presented as direct. One profile, quantum-lattice research, abstained. Macro AI development Precision@3 was 1.00 and Precision@10 approximately 0.970; these figures are **not held-out or independent human accuracy**. No release-quality claim follows from them.

Known remaining development failures include an occupational association treated as legal work, employment coaching treated as HR work, and materials retailers/stockholders treated as materials-science employers. A previous explicit material-science match also disappeared under the context check and needs investigation. These cases are recorded as review data; no employer-name exceptions were added to ranking.

The earlier 166-pair AI pool covers only part of the new output. Metric reports now include fully judged profile counts and overall judged-item coverage; unjudged items are never silently called irrelevant. All top-K pairs require review before reporting full-slice metrics.

## Versioning and reproducibility

`coverage.py` records synthetic profiles and exposures in `data/coverage/coverage.sqlite3`. Every hit retains employer, profile, rank, direct/related group and run version. Every employer receives an outcome. Reports include the actual best-reaching profile, its best rank and exposure frequency.

Imported tests are deduplicated by actual professional profile content. They are rerun under the selected current matcher. Historical exposure is reported separately. Resume requires the same proposal algorithm, matcher-source hash, ranking/model/index versions, employer versions, sponsor snapshot and evaluation date. New runs retain the matcher source and run metadata. Matcher source snapshots are diagnostic reproducibility aids, not a complete deployment lockfile.

`--strategy semantic` selects the experimental matcher only for offline coverage. `--strategy current` retains the live matcher. This command never changes the live API strategy.

```sh
# From sponsormatch/backend; use the isolated real-catalogue mirror for experiments.
DATABASE_URL=postgresql://localhost:55432/sponsormatch uv run --no-sync sponsormatch coverage-audit \
  --model-folder ../data/prospects/9b488fb7cad26af82c3b3735 \
  --output ../data/coverage/new-experiment --strategy semantic \
  --baseline ../data/evaluation/2026-10-17/form-final \
  --max-profiles 200 --rounds 8
```

`--max-profiles 0` removes the explicit profile budget; `--rounds` still bounds a run. Exhaustion means no new profile from this generator, not full corpus reachability. All mapped employer facets and their own activity specializations are considered. Employer names/IDs are never injected into candidate input or used as rank overrides.

`coverage_gap_audit.py` replays the same saved profiles and distinguishes eligible employers excluded by the 100-result cap from records without an eligible match under tested profiles. Version 5 found 191 cap-excluded employers and 827 other unreached professional records. Version 7 replayed 4,564 distinct saved profiles: 134 of its 1,350 unreached professional records were eligible below the 100-result cap; the other 1,216 had no eligible result under those tested profiles. Version 8 replayed 4,565 profiles: 136 cap-excluded records and the same 1,216 without an eligible result; 1,352 professional records remain unreached. No query hit the 1,500-employer retrieval cap. These remain algorithmic diagnoses, not independent relevance judgments. Do not transfer old-version diagnoses to new rankings.

## Incremental updates and remaining work

After a manual CSV import and index publication, a deduplicated background work item rebuilds the prospect model and publishes it only if current employer versions agree. Model files publish atomically and previous versions remain available. This does not connect the scraper.

The remaining work includes:

- Improve evidence-relation classification and resolve documented false positives/negatives, with occupation-stratified held-out review.
- Complete opted-in related careers in the semantic experiment and evaluate synonym consistency, multiple intents and task/skill relationships.
- Review the unreached cohorts and ranking-cap exclusions; do not weaken evidence gates to manufacture reachability.
- Obtain genuine professional evidence and reliable sponsor linkage for sparse/unlinked records.
- Improve cohort ambiguity handling and independently review its meaning. Versioned derived-interest associations are now stored privately, alongside user-selected form interests; they do not assert qualifications.
- Add supported skill/task assistance when suitable source relationships exist, without inferring candidate qualifications.
- Verify deployed latency/load and end-to-end user feedback before replacing the live matcher.

Backend verification: **142 tests passed**, including source/version/identity/route/channel gates, full-source relation rejection, generic-title ambiguity, evidence-span ownership, exposure replay/resume and best-profile provenance. Production Next.js build and TypeScript checks passed. The real career-idea gateway returned the active model; the form has no horizontal overflow at 390px and no skills were auto-selected. The operator review page rendered its controls, persisted a test judgment across reload, and was reset to zero actual human judgments.


## Iteration 8 and adaptive candidate cohorts

The latest operator entry point is http://127.0.0.1:4019/. Its allowlisted static bundle contains only public employer evidence and synthetic test inputs. Real-user cohort reports, identity/session data and credentials are excluded.

The version-8 experiment retains up to eight evidence alternatives per employer/intent and checks each independently. It takes the best supported result rather than adding scores for extra documents. A rejected activity no longer hides an attributable role from another facet. A regression test proves this fallback. Net reach was 4,618 (two fewer than version 7 after ranking competition), so this correctness fix is not presented as a coverage improvement. Its outcomes are 4,618 reached, 1,352 professionally described but unreached, 547 requiring current sponsor linkage, 782 requiring professional descriptors and 10 requiring a useful channel.

`ProspectLibrary.associate` now assigns versioned professional-interest cohorts. It preserves each confirmed intent, prefers unambiguous official aliases, and uses semantic proximity to official occupation families. Provisional recorded job titles require an exact user-entered label; the system does not infer credential-bearing titles from broad interests. Low-confidence or close competing families stay unresolved. Neither candidate skills nor certifications are modified.

The 272-variant cohort matrix associated 219 profiles and retained 69 unresolved intents (some multi-intent profiles have both an association and an unresolved interest). Its exports contain professional test IDs and group associations, not identities or visa context.

New completed sessions store `prospect_cohorts` in their existing private `versions` JSON. The saved employer ranking and index versions retain their own meaning. Optional cohort failure does not block result delivery. Cohorts are not used for authorization, ranking overrides or qualification claims.

Publishing an updated prospect model queues a deduplicated `refresh_prospect_cohorts` work item. The worker processes bounded batches and renews its lease. Refresh keeps earlier model associations in `prospect_cohort_history`, rechecks active-model changes, and updates session metadata under a row lock. It preserves ranked employers and account/preview access. Missing occupation-reference artifacts prevent pointer publication.

The initial real-data refresh updated the two existing ready sessions. Before/after checks confirmed identical ranked-result rows, ownership/access/status/expiry fields and ranking versions. A queued background refresh completed in one attempt with no error. Evidence is in `data/coverage/cohort-refresh-verification.json` and `cohort-worker-verification.json`; those files are not included in the operator's public-evidence bundle.

Operator commands from `backend`:

```sh
uv run --no-sync sponsormatch refresh-cohorts --limit 100
uv run --no-sync sponsormatch cohort-report --output ../data/coverage/private-cohort-summary.json
uv run --no-sync python ../scripts/cohort_probe.py --profiles /path/to/synthetic/forms.json --output ../data/coverage/cohort-matrix
```

The aggregate report deduplicates owners and profiles per model/group without exporting owner, profile or session identifiers. Older model cohorts remain distinct instead of being silently combined.

## Rejected local language-inference probe

A pinned local [DeBERTa NLI model](https://huggingface.co/cross-encoder/nli-deberta-v3-small), revision `fa2804872c3b4bd748f38c0185cc85775361e735`, was loaded from safetensors without remote model code. The model card identifies its Apache-2.0 license and SNLI/MultiNLI training. It ran locally; no hosted inference service or paid model call was used.

On the 145 AI-reviewed development pairs, it called only 108/141 direct pairs entailed, while still calling two of the four weak/related pairs entailed. This formulation is unsuitable as a professional-evidence gate. It was not integrated into live or experimental ranking. Inference took 3.43 seconds after download/model loading; this is an isolated feasibility measurement, not website latency. Its model scores are not professional relevance probabilities.

The full goal remains incomplete: general semantic ranking still needs quality and related-career work before promotion, all-employer reachability is unproven, sparse inputs remain, and independent human validation is absent.

## Broader occupation coverage and evidence checks (17 October 2026)

The proposal generator is now `multi-occupation-evidence-3`. For each accepted activity span it considers up to three distinct four-digit occupation parents above the embedding floor. This added 26,331 evidence-linked query hypotheses and expanded the in-memory proposal set to 3,572 groups. They are synthetic search hypotheses, not accepted employer occupations, vacancies or user qualifications. The published prospect library is unchanged.

With the unchanged version-8 matcher, the larger proposal set reached 4,632 employers, 14 beyond its rerun baseline. It tested 2,500 additional profiles and stopped at its round limit. The version-9 relation-permission experiment reached 4,860 employers after exhausting its remaining novel proposals. Inspection of all 20 new admissions for the 16 complete form anchors found 19 professionally supported pairs and one unsupported warehouse-partitioning supplier. Neither experiment was promoted.

Version 10's broader role-family restriction removed valid legal-assistant matches. Its full coverage replay was stopped and its partial ledger is not a completed coverage result. Version 11 preserves strong direct title alignment, requires clearer occupation resolution for weaker title similarities, learns ambiguous unqualified titles from official aliases with domain qualifiers, and requires stronger duty evidence before relaxing a product/education/membership relation. No employer-name or job-niche exceptions were added.

The completed version-11 coverage experiment reached 4,757 of 7,309 employers, including 1,553 that appeared in the top three and 2,872 in the top ten. It reran 7,541 baseline profile entries and generated 229 more before exhausting novel supported proposals. Outcomes: 4,757 reached; 1,213 professionally described but unreached in these tests; 547 requiring current sponsor linkage; 782 requiring professional descriptors; 10 requiring a useful channel. No matching errors occurred. Reach is algorithmic exposure, not measured relevance. None of the stored employers was deleted or made a guaranteed recommendation by this experiment.

`compare_semantic_runs.py` compares the same frozen profile inputs between versions, rejects changed or duplicate profile IDs, reports complete-shortlist employer exposure, and groups sensitivity by optional-field variant. Version 9 to 11 changed the top three for 17/272 profiles and the top ten for 18/272. Candidate skills and experience can affect ordering; location, career stage and industry often cannot change results without corresponding employer evidence. The experimental engine still lacks substantive related-career retrieval, so the related-careers toggle is not presented as implemented parity.

A second sample selected three distinct occupation parents per major SOC group using a fixed hash seed, yielding 27 additional professions. It was frozen before the results, but cases subsequently informed tuning, so it is now a development sample, not held-out validation. Manual AI review of all 62 returned top-three pairs in version 11 found 38 direct, six related, ten insufficient-evidence and eight irrelevant pairs. Four profiles abstained. Mean returned direct Precision@3 across 23 nonempty profiles was 59.4%; this is an AI development diagnostic, not independent human accuracy. Precision@10 and recall were not established for that sample. The original 16-family anchor results therefore cannot support a claim of general matching quality.

Remaining failures include confusing product/customer sectors with actual work, generic officer or sales titles, operational versus adjacent careers, and mismatched food-processing/food-service evidence. These findings prevent promotion of the experimental engine. Live search continues using `evidence-11-general-role-context`; its keyword-based limitations remain explicitly outstanding.

Reproducible artifacts are in `data/coverage/multi-occupation-v8`, `multi-occupation-v9`, `multi-occupation-v11`, `semantic-matrix-v11` and `fresh-occupation-v11`. Backend regression checks: 150 passed. The full all-employer goal and independent relevance validation remain incomplete.

## Free local instruction-model probe

A separate offline probe used [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), through the [MLX community 4-bit conversion](https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit/tree/50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b), pinned to revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`. The original model card identifies Apache-2.0 licensing. Runtime `mlx-lm==0.32.2` was installed in an isolated uv environment, not the application dependencies. Weights are cached locally; no hosted inference, API key or paid call was used. Hugging Face requests downloaded model artifacts only. Employer excerpts and synthetic professional inputs stayed local.

The prompt was fixed before inference and included the intended occupation, its official description, accepted source excerpt and matched spans. Review labels and separate employer-name fields were omitted; names occurring within source excerpts remained. It distinguished actual professional work from customer industries, products, subject teaching and adjacent careers, with no job-specific exceptions or examples. Direct outputs needed a nonempty exact source quote; all 62 outputs passed syntax/quote validation.

Against the 62 AI-reviewed broader development pairs, it classified 33 pairs as direct, of which 27 agreed with the AI direct judgments: direct-judgment precision 81.8%. It retained 27/38 AI direct pairs: direct-judgment recall 71.1%. Six weak pairs were accepted and eleven direct pairs missed. Inference took 207.94 seconds, approximately 3.35 seconds per pair, excluding download and model loading. These are diagnostic agreement figures, not independent human accuracy, retrieval recall or website latency. This dataset differs from the earlier NLI probe, so the figures are not an apples-to-apples model comparison.

This formulation was rejected as a matching gate and remains outside live and experimental ranking. Correctly quoting a source did not guarantee a correct professional relationship: generic titles and customer-sector references still caused errors. No employer claims or shortlist results were changed. The source embeddings remain MiniLM, with no model/index migration or paid service added.

Reproduce from the application directory (Apple Silicon):

```sh
HF_HUB_DISABLE_XET=1 uv run --no-project --with mlx-lm==0.32.2 python scripts/local_relation_probe.py \
  --runs data/coverage/fresh-occupation-v11/runs.json \
  --labels data/coverage/fresh-occupation-v11/ai-anchor-reviews.json \
  --model-folder data/prospects/9b488fb7cad26af82c3b3735 \
  --output data/coverage/local-relation-probe-v1 \
  --revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b
```

The tokenizer's `.jinja` template is downloaded alongside its JSON files and safetensors; remote model code is disabled. Output files preserve prompt/model/runtime versions, source inputs, predictions, exact-quote validation, per-pair timings and limitations. Completed input hashes can be reused on replay.


## Specificity checks and verified linkage repair (17 October 2026)

Version 12 learns title specificity from the full official occupation vocabulary and the pinned encoder's subword tokenizer. Counterfactual titles remove qualifiers for an evidence comparison; user inputs are preserved. Confident synonyms resolving to the same detailed occupation are excluded from the contrast. Single-word activity evidence is checked against the complete source excerpt to reduce customer-sector matches. No employer-specific or occupation-specific keyword exceptions were added. Regression suite: **166 passed**.

A separate identity audit found 92 recoverable sponsor links. Unverified historical workbook observations had been treated as additional established identities; missing official counties had also caused avoidable rejection. `register-linkage-2` distinguishes unknown counties from contradictions and counts supported identities rather than every historical observation. Genuine supported duplicates and known county disagreements still require review. Both local and actual Supabase repairs verified all 92 links. Employer IDs, business facts, contacts, search vectors and private saved results were preserved; no rows were merged/deleted. Repair backups remain outside the operator report. Production cohort refresh completed on its first attempt.

The resulting published prospect model is `cdbd25ac18bbcbf97ddf07d6`, source hash `6c7fa3598c27d29cc6ddd5ae89323027f587440da877e427736256e66aa4138e`. This career-interest library publication does not promote the semantic ranker. Current live ranking remains `evidence-11-general-role-context`. The evaluated register snapshot remains the 12 October artifact; this experiment did not import a newer register.

Frozen version-12 coverage run `3a05dea5bca743b8a02111530ece36e0` replayed **8,101 distinct profiles** without matching errors. Outcomes across all 7,309 retained CSV employers:

| Outcome | Employers |
|---|---:|
| Reached in a saved shortlist | 4,798 |
| Professionally described, but not reached by tested profiles | 1,258 |
| Professional descriptors needed | 788 |
| Current sponsor linkage needed | 455 |
| Useful channel needed | 10 |

1,602 employers appeared in a top three; 2,941 in a top ten. Of the 1,258 professionally described unreached employers, 204 qualified below the 100-result saved-shortlist limit and 1,054 had no eligible result. No profile hit the 1,500-employer retrieval cap. Compared with the same engine before linkage repair, 65 employers became reachable and 11 lost exposure through competition, a net increase of 54. These figures measure algorithmic exposure, not professional relevance or sponsorship willingness.

The 272 full-form variants were rerun on this source model. The original 16-family AI development review contains 145 judged top-ten pairs: 140 direct, four insufficient-evidence and one related. Fifteen profiles returned results and one abstained. Mean returned direct Precision@3 is 100%; mean returned direct Precision@10 is 96.35%. Those tuned anchors do not establish general accuracy.

The broader 27-occupation development sample returned 60 judged top-three pairs: 41 direct, five related, six insufficient-evidence and eight irrelevant. Twenty-two profiles returned results and five abstained. Mean returned direct Precision@3 improved from 59.4% in version 11 to **66.7%** in version 12. This remains below the release target. There are no independent human reviews, and recall is explicitly unmeasured rather than inferred from judgments of only the returned head. The experiment is not promoted. Optional-field sensitivity and exact before/after profiles remain in both matrix folders.

Current reproducible artifacts: `multi-occupation-v12-relinked`, `semantic-matrix-v12-relinked`, `fresh-occupation-v12-relinked`, and `cohort-matrix-relinked`. The operator publisher rejects mixed ranking/model/register-snapshot artifacts, retains version-specific bundles and exposes aggregate repair verification only. Synthetic cohort sensitivity associated 219/272 forms; 69 individual role intents remained unresolved. No real user qualifications were inferred.

## Rejected official-title competition diagnostic

`occupation_title_probe.py` compares historical role spans against **25,805 distinct official occupation labels and aliases**, retaining ambiguous aliases across every applicable family. It uses cached local MiniLM embeddings and no profession keyword lists. Across the current 205 AI-reviewed pairs (181 direct, ten insufficient, six related, eight irrelevant), 82 had occupational-role evidence to which the proposed rule applied. Requiring a sufficiently stronger competing title removed the integration-engineer/immigration-service false match, but also rejected 13 direct pairs, including legal-assistant and mechanical-engineering evidence. This simple rule is rejected and is not integrated into matching.

Outputs are in `data/coverage/occupation-title-probe-v1`. They preserve source-model/input hashes, source excerpts, competing titles, similarities and per-family results. This is agreement with development labels, not held-out accuracy or post-filter Precision@K. Both website and matching API remained healthy during these offline tests. No paid calls, emails, payment operations or test accounts were created.


## Occupation-family competition, niche regression and ties

Version 13 adds a family-aware alternative to the rejected title-only rule. It compares historical role spans with all 25,805 official title aliases, but only permits a strong, semantically distant competing family to reject a title. Related occupational families remain supported. Cached local arrays avoid repeating the title calculations for every query. The cache is content/model-versioned and atomically published with unique temporary files. It does not consume Supabase storage or call hosted models.

On the existing 205 AI-reviewed development pairs, the diagnostic retained all 181 direct pairs while removing the integration-engineer/immigration-service error. All 272 original form variants preserved their full shortlists. The broader 27-profile sample retained 41 direct, five related and six insufficient-evidence pairs, with irrelevant pairs reduced from eight to seven. Mean returned direct Precision@3 remains 66.7%, because the affected profile still has no direct match. No release-level improvement is claimed.

The full version-13 run `310155a2e1574e9f855e5e9eee45fcf6` evaluated 8,183 profiles and reached 4,791 employers: 1,601 in previews and 2,927 in top tens. Remaining outcomes: 1,265 professionally described/unreached, 788 needing descriptors, 455 needing current sponsor linkage and ten needing a useful channel. Gap replay found 204 below the saved-shortlist cap and 1,061 without an eligible result; no query hit the retrieval employer cap. The seven-employer regression versus version 12 consisted of exact historical-role matches such as Production Scheduler and Modelling & Simulation Engineer. Those niche queries were assigned imperfect official categories, so this gate incorrectly overruled their direct wording. Version 13 is rejected and was not promoted.

Version 14 restores the existing strong-direct-wording boundary (role similarity at least 0.88) before applying the new title-competition veto. Broad-title, identity, sponsor, source and channel gates remain in force. All seven targeted niche cases now return their employer again. The 272 original and 27 broader form reruns are complete; the broader AI diagnostic remains 66.7%, and the full coverage replay is in progress. Do not substitute version-12/13 reach counts for a completed version-14 measurement. The live website still uses `evidence-11-general-role-context`.

`reuse_unchanged_reviews.py` carries existing AI development judgments forward only when both the entire profile and accepted evidence signature are unchanged. New/changed pairs remain unjudged. It refuses inputs not explicitly labeled as AI reviews, keeps recall unmeasured and never turns these labels into independent human validation. A regression test checks changed source text, new employers and changed profiles. Current backend suite: **170 passed**.

A separate exact-score tie probe replayed 15 selected earlier cap-gap profiles through version 13. It found 136 unique employers omitted in exact cutoff ties, of which **37 were unreached in the earlier full run**. These are different measures; 136 must not be presented as additional globally unreachable records. Tie-breaking and ranking were unchanged. This points to an exposure issue from UUID ordering among identical scores, without justifying weaker professional gates. Outputs: `shortlist-tie-probe-v13`.

The dashboard preserves previous completed bundles, their source/ranking/register manifests and explicit non-promotion decisions. The full goal remains active: general relevance, related-career parity, remaining coverage, sparse evidence and human validation remain unresolved. No paid model calls, test emails or real-account mutations were made by these experiments.


## Source-aware exposure and confirmed-profile audit (17 October 2026)

Version 14's completed run `1d88704c60c6489890e4a5ac6d4896e7` restores all seven niche-role regressions and reaches 4,798 employers across 8,182 actual profile searches. The earlier 8,183 baseline-entry count included one broad profile omitted by normalization. Its gap replay confirms 204 eligible employers below the saved-shortlist cap and 1,054 with no eligible result.

`exposure_order.py` first tested deterministic, professional-profile-based ordering of exact score ties. The seed uses explicit roles, background, skills, project/experience text and certifications; formatting, skill order/duplicates, identity, visa, location and career stage cannot manufacture a different seed. It does not alter scores, eligibility, intent balance or the shortlist limit. That hash-only simulation selected 27 previously unreached employers in 15 selected profiles, but it also exposed weak population/function matches. This selected counterfactual is not a catalogue-wide gain or relevance measurement.

Version 15 uses a more informative tie-break first: similarity between the candidate's professional representation and the actual supporting source excerpt. Exact known company names, URLs, emails and phone values are removed from this derived embedding input; the original quoted evidence remains unchanged. Only genuine equal-score groups require these extra source vectors, with distinct text cached under the pinned local encoder. Contact-only changes therefore do not regenerate identical semantic context. Residual ties use the deterministic professional seed. Primary scores and professional/identity/sponsor/channel gates remain unchanged. This source-based refinement is tested offline and is not enabled in live search.

Completed version-15 run `7651e345809c483aad21cf3948e6aafc` uses prospect model `cdbd25ac18bbcbf97ddf07d6` and the unchanged 12 October register snapshot. It reaches **4,819 employers**, gaining 34 and losing 13 versus version 14, a net gain of 21. 1,681 employers reach a preview position and 2,968 a top ten. Outcomes:

| Outcome | Employers |
|---|---:|
| Reached by a valid confirmed profile | 4,819 |
| Professionally described, not reached | 1,237 |
| Professional descriptors needed | 788 |
| Current sponsor linkage needed | 455 |
| Useful channel needed | 10 |

The gap audit replayed 8,193 raw diagnostic calls: 183 unreached employers qualified below the 100-result cap and 1,054 had no eligible result. No query hit the 1,500-employer retrieval cap. A separate readiness audit found one generated `Analyst` profile that the real API would require clarifying. Its 19 results added no employers, preview employers or top-ten employers to the reached set. The confirmed-profile view therefore has **8,192 valid profiles** and exactly the same 4,819/1,681/2,968 employer counts; it removes that invalid trial from per-employer frequencies and example profiles. Original raw hits remain preserved. This distinction must not be hidden or counted as 8,193 valid forms.

`audit_profile_readiness.py` produces a separate `confirmed-profiles` report with a normalizer/policy hash. Discovery proposal version 4 now applies the same clarification/exploration/confirmation requirements before both baseline and generated searches, logs clarification cases separately, and records actual baseline/generated profile counts. It preserves unfamiliar confirmed niches instead of forcing them into a known occupation. The completed version-15 experiment above still records proposal version 3; version 4's corrected generator is implemented and tested, but has not yet had a complete new discovery run.

All 272 original form variants and 27 broader occupations were rerun. Newly returned anchor pairs were inspected against their exact quoted sources: 20 new original-family pairs and three broader pairs. The original 145-pair AI development review now has 138 direct, six insufficient-evidence and one related pair. Returned direct Precision@3 remains 100%; Precision@10 is **95.02%**, down from 96.35%. Two security-product descriptions do not establish an analyst function. The broader sample remains 41 direct, five related, six insufficient and seven irrelevant pairs across 59 returned top-three pairs, with **66.7%** mean returned direct Precision@3 and five abstentions. Current-head judgments cannot establish recall. No independent human validation or release promotion is claimed.

A current tie diagnostic samples 15 cap-gap profiles. It finds 139 employers hidden among equal-primary-score cutoff groups, including ten unreached employers. After comparing source-context similarity too, none of that sampled hidden set remains in an exact full-ordering tie. This is not an exhaustive count. These newer gaps cannot all be described as UUID tie-breaking: the source-context comparison now distinguishes them.

An additional whole-source feature diagnostic considered all span lengths, with explicit-wording protection and the existing conservative cross-family thresholds. It rejected two AI-judged irrelevant pairs and no direct pairs in the current 204-pair sample. It has not been integrated or used to claim post-filter top-K accuracy; newly surfaced results would need a fresh review. Artifacts: `whole-source-probe-v15/extension-summary.json` and `extension-pairs.json`.

**187 backend tests pass.** The gap verifier now rejects changed matching helpers or tampered frozen source. Semantic coverage snapshots capture the actual ranking, evidence, taxonomy, model-provider and tie-order helper files. Operator bundles include content hashes of every published input and the publisher code, so updated judgments/audits create a new publication directory rather than silently overwriting an earlier bundle. Copied hashes are verified before the active dashboard index changes. Backups, secrets and real candidate data remain outside the allowlist.

## Source-only local extraction diagnostic

`source_relation_probe.py` uses the already cached Qwen3-4B-Instruct-2507 MLX conversion, pinned revision `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`, in isolated `mlx-lm==0.32.2`. It supplies only source text, evidence kind and exact target spans. Candidate occupations, taxonomy definitions, review labels and separate employer-name fields are omitted. Names can still occur inside original source excerpts. Model and dependency networking are disabled for the run; no hosted inference or paid call is used.

The explicitly biased development sample contains every weak-reviewed source plus one deterministic direct source per reviewed occupational family: 59 sources/pairs. The model processed these in 231.74 seconds of original inference, excluding loading. Cached replay reuses the outputs without loading the model. **57/59** outputs passed strict schema/target/exact-quote checks; two remain invalid rather than being repaired into factual claims. In valid output plus invalid states, the relation counts are 26 performed activities, 21 professional roles, two customer sectors, eight products/tools and two invalid outputs.

Against the existing AI professional-relevance judgments, source-only positive classification retained 32 direct pairs, but also five related, seven insufficient and three irrelevant pairs. Two direct pairs lacked a positive relation: one invalid quote and one incorrect product classification of postal services. These are development diagnostics of a deliberately selected failure sample, not representative accuracy or post-filter Precision@K. A correct source category would still not establish the candidate-specific professional relationship.

The probe distinguishes some product and customer-sector references, but still incorrectly calls mining in a consultancy list, AI assistant tools and food-processing supplier context performed work. A source quote can be exact while its asserted relation is wrong. This classifier is **not enabled as a matching gate** and does not publish employer claims, user qualifications, vacancies or sponsorship statements. Review findings are stored separately with an annotation-content hash, so cached replay cannot erase the inspection or attach it to changed predictions.

Reproduce from the application directory:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 UV_OFFLINE=1 \
uv run --no-project --with mlx-lm==0.32.2 python scripts/source_relation_probe.py \
  --matrix data/coverage/semantic-matrix-v15 \
  --matrix data/coverage/fresh-occupation-v15 \
  --revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b \
  --output data/coverage/source-only-relation-probe-v1
```

The full goal remains active. The matcher still needs better professional-function discrimination and related-career parity; 2,490 retained employers remain unreached under the current evidence/sponsor/channel gates. The generator still needs richer meaningful optional-context variants and broader official-occupation coverage. Live ranking retains its existing bootstrap limitations until a general replacement meets the agreed quality gates. No real users, emails, payments or employer data were changed by these offline experiments.


## Version-bound human review workflow

The report's review packet and exported judgments now retain profile/evidence hashes, ranking/model/register versions and positions. Browser storage is scoped to the exact packet, and restoration copies only valid label/boolean fields, never provenance. An unchanged report retains its labels after reload; changed source evidence starts unjudged. Historical browser storage is not deleted or silently treated as a fresh review.

`evaluate_human_reviews.py` validates those exports against the exact matrix. It rejects changed sources/profiles/models, inconsistent metadata, edited offline context, AI-labeled records and conflicting duplicate reviews requiring adjudication. Unreviewed pairs are not negatives; unmarked explanation/channel fields stay unknown. Current-head reviews cannot establish retrieval recall, which remains unmeasured. The output identifies these as self-reported human development reviews, not authenticated reviewer identities or held-out release validation. It does not automatically enable a ranker.

From `backend`, after exporting real judgments from the current report:

```sh
uv run --no-sync python ../scripts/evaluate_human_reviews.py \
  --matrix ../data/coverage/semantic-matrix-v15 \
  --reviews ~/Downloads/sponsorreach-human-review.json \
  --output ../data/coverage/human-review-v15.json
```

The download path is an example; use the actual exported file. A current unjudged packet was successfully scored as **zero judgments / not evaluated**, never as perfect precision. Browser verification used an explicitly synthetic fixture in an isolated session: label/support/channel choices survived an unchanged reload, changed evidence reset the new packet to unjudged, the export included its hashes/versions, and a 390px viewport had no horizontal overflow. The temporary served fixture and its browser storage were removed; no real human reviews were generated. Screenshot and machine-readable UI proof: `output/playwright/sponsorreach-review-provenance/` in the scraper workspace.

Final backend suite for this update: **193 passed**. These engineering checks do not replace actual human relevance judgments. The full goal remains active.


## Generalized profile generator and occupation-stratified tests

Proposal version `multi-occupation-evidence-5` adds all 1,181 official reference occupations to the discovery baseline, including 98 without an existing employer-derived reference group. Existing profiles deduplicate by their full normalized representation. The activity hypothesis expansion retains up to three distinct occupational parents within 0.10 of the best similarity and above the existing 0.43 floor. This excludes the observed bookkeeping-to-print-finishing hypothesis without a profession-specific exception.

`discovery_profiles.py` adds semantically related, employer-source-backed project interests and specialization combinations. Unmapped observed roles retain their own labels and vectors. Technical punctuation distinguishes C from C++. Source claim IDs accompany each generated combination; employer names/IDs never enter candidate query text. Interest statements do not invent experience, skills or credentials. The generator checks the same profile-confirmation requirement as the API before matching.

Completed run `5f5a0effdbfc489392c160952c44f7a8`, using unchanged matcher 15/model/register/evidence, evaluated **12,223 confirmed profiles**: 8,607 baseline profiles and 3,616 additional generated profiles. One broad proposed Analyst input was withheld before matching. It reached **4,830/7,309 employers**, gained 11 and lost none versus run 15, with 1,898 preview employers and 3,135 top-ten employers. No matching errors occurred. The finite proposal pool was exhausted. Remaining outcomes are 1,226 unreached professionally described records, 788 requiring professional descriptors, 455 requiring current sponsor linkage and ten requiring useful channels. Completed gap replay covers all 12,223 confirmed profiles: 173 unreached employers qualified below the saved-shortlist cap; 1,053 produced no eligible result. No profile hit the retrieval cap.

Every new employer/profile pair replayed successfully. AI inspection marks eight direct, one related (generic architecture versus landscape architecture) and two insufficient (business ownership interests do not establish employment functions). The raw reach count remains algorithmic; the new pairs are a targeted development sample, not a precision estimate or verified human relevance.

The additional `official-interest-matrix-1` sampler chooses two official occupations per major SOC family using a stable hash, without selecting familiar or successful roles. Its **144 profiles / 18 occupations / nine major families** cover hypothetical source-derived task interests, official aliases, career stages, relocation and related-career switches. All 144 pass the application profile-confirmation check. Skills and credentials remain empty because official descriptions do not establish a candidate's qualifications; the separate existing 272-form matrix covers those optional fields.

AI review of all 51 returned top-three anchor pairs finds **22 direct, nine related, ten insufficient and ten irrelevant**. Mean per-profile returned direct Precision@3 is **42.6%**; three shortlists have fewer than three employers. These are new development judgments, not independent human validation, held-out performance or total-catalogue accuracy. Precision@10 and retrieval recall remain unmeasured for this matrix. Labels are not transferred to optional-field variants. The unchanged ranker remains unpromoted.

The failures include radiation-safety occupations confused with patient-monitor products, street-market trading confused with financial market making, industrial air blowers confused with glass-blowing craft, and customer-sector descriptions confused with performed work. Official aliases change top-three rankings in nine of 18 cases and result counts in nine. Removing task-interest context changes top three in four cases and top ten in eight. Stage, relocation without a location preference, and related-career toggles produce no changes; this does not establish those features work. Related-career retrieval parity remains absent.

The operator publisher can include this matrix with `--interest-matrix data/coverage/official-interest-matrix-v1`, checks its matcher/model/register versions and includes its synthetic inputs, unjudged human-review packet and explicitly AI-labeled development judgments in the content-hashed publication. No human review is fabricated, and no candidate accounts or employer records were modified. **201 backend tests pass.**
