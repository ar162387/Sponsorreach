# SponsorReach implementation verification

> **Current catalogue update (16 October):** the full operator-authorized CSV baseline supersedes the earlier 39/276-company pool: 7,309 retained employers and 9,137 search embeddings, including 848 identity/contact-only records. See [full CSV baseline](docs/CSV_BASELINE.md) for counts, import policy and evaluation limits. Earlier dated measurements below are historical.


Verified locally on 12 October 2026. This is a runnable application and matching-service baseline, not evidence that the commercial release gates have passed.

The user's [13 October pilot decisions](PILOT.md) replace the earlier requirement for production ledger access and a paid hosting/database budget. Website ingestion is CSV-only. The pending email-verification gate and compact Free-tier profile have not been included in the test counts below.

## Delivered

- Next.js landing page and direct `/match` entry; three-step intake, focused role clarification, optional related careers, real matching stages, complete previews, server-controlled demo unlock, result history, feedback and policy pages.
- Python API and independent bounded worker with database-owned sessions, hashed browser ownership, verified-account association, idempotent requests, frozen ranked shortlists and server-side withholding.
- Supabase-compatible private Postgres schemas, RLS, pgvector and full-text retrieval, evidence gates, transparent ranking, sourced explanations and separate sponsorship/vacancy/eligibility dimensions.
- Official-register, historical CSV/workbook and read-only ledger adapters; independent employer identities, namespace-aware mappings, reviewed linkage and immutable observations. Failed/late refreshes preserve accepted evidence.
- Offline extraction and embedding adapters, operator evidence review, UK-specific structured vacancy verification, index staging/publication/resumption/rollback, evaluation tooling and optional offline reranker benchmark.
- Scraper persistence corrections that preserve uncertainty states and stop synthesizing active vacancies from model-produced titles.
- Local runner, reproducible dependency locks, migrations, container definitions and deployment instructions.

## Checks

| Check | Result |
|---|---|
| Backend suite with actual PostgreSQL 16/pgvector | 57 passed |
| Existing scraper suite, including five new persistence regressions | 167 passed |
| Next.js optimized production build and TypeScript checks | Passed |
| Browser onboarding → three previews → demo unlock | Passed; the same five saved employers were revealed |
| Preview withholding, account isolation, RLS and idempotent replay | Passed in integration tests |
| Immutable evidence, failed/late refresh, reviewed identity linkage | Passed in integration tests |
| Actual vector SQL, staged build failure, vector reuse and index rollback | Passed using mocked provider vectors against actual Postgres |
| Axe WCAG 2 A/AA on inspected pages and checkout dialog | No detected violations |
| Results at 390px and desktop widths | No horizontal overflow; screenshots inspected |
| Git whitespace check | Passed |

Mocked embeddings test database behavior; they do not establish semantic retrieval quality or external provider compatibility. Automated accessibility checks do not replace a complete accessibility audit. The backend suite has one upstream AnyIO deprecation warning.

## Local imported data

- 8,509 historical employer records: 7,510 CSV records and 999 early-workbook records. These are source organizations, not a reconciled legal-company count.
- 143,198 current official route rows, including 123,175 Skilled Worker rows. These are route rows, not distinct legal companies or vacancies.
- 1,796 official UK SOC groups, plus the 24 explicitly local bootstrap families. Official coding-index aliases preserve ambiguity exclusions and source versions.
- 15 fictional employers support the labelled demo experience. Their `.example` channels are non-actionable.
- Zero accepted real-employer claims and zero live generated embeddings. Historical assertions were not silently promoted into validated recommendations.

Source artifacts and the isolated local database are retained under ignored application data directories. No unrelated remote Supabase project was modified. Pre-existing workspace changes were preserved.

## Launch prerequisites and unmeasured targets

A dedicated SponsorReach database (initially Supabase Free), optional cloud-model credentials, Supabase email-auth/SMTP configuration, complete external taxonomy downloads and reviewed real-employer evidence are still needed. The production ledger is no longer required. Finalize controller/privacy details, the email-verification gate, compact storage profile and deployed retention/refresh schedules before inviting public users.

The 240-profile evaluation generator supplies synthetic cases, not reviewer labels. Human precision, explanation-support and occupational-coverage gates remain unmeasured. The full-catalogue 150,000–500,000-document load, latency and monthly-cost targets have not been established. Docker image builds and production deployment were not executed. Provider invoice/cost reconciliation and production monitoring need deployment data.

Real payments, CV processing, automated outreach, immigration eligibility checking, live reranking and learned ranking remain outside this initial release, as specified in the plan.

## 14 October update — SponsorReach

The website's public name is SponsorReach. Added a free CPU-only Sentence Transformers MiniLM provider with a pinned model revision, chunk-aware pooling and true 384-dimensional storage/retrieval. The 768-dimensional OpenAI path remains optional and isolated. Added live email-verification gates, owner-bound confirmation lookup, visible delivery errors, resend UI and safe callback routing to the saved shortlist. Explicit local demo mode remains separate and cannot seed a remote database.

The updated backend suite passes 59 tests, including real Postgres retrieval across both vector dimensions, model-mismatch fallback and verification-before-preview access control. The optimized Next.js build and TypeScript checks pass. Real SMTP delivery has not been tested.

Supabase Auth responds to the supplied credentials. The original direct endpoint was IPv6-only; the user supplied a Session pooler URI, and Postgres connectivity now succeeds. The connected MCP project is different, so it was not modified. Resend domain listing returns 403, consistent with a restricted key but insufficient to validate sender setup. Dedicated application migrations have been applied through the supplied pooler connection. No test email was sent. Public operator/contact details and hosting remain pending.

The pinned MiniLM model has been downloaded and tested with networking disabled. It produces 384-dimensional normalized vectors. A simple engineering pair scored approximately 0.500 cosine similarity versus 0.017 for the engineering/accounting pair; this is a smoke check, not a measured relevance-accuracy result. A real local 15-document demo index was built and published without any embedding API key. The browser verification-screen check showed zero employer cards before verification.

After the Session pooler update, the dedicated Supabase database was initialized and the chosen CSV catalogue was transferred atomically: 7,510 real employer records, 7,510 original CSV source rows, 143,198 dated register rows and 1,820 taxonomy concepts. No fictional employers, legacy-workbook employers or candidate profiles were transferred. The remote database measured 186.8 MB after import. Every application table has RLS enabled; the migration tracker also denies public/API-role access. The remote catalogue currently has zero accepted professional claims and zero searchable professional facets, so importing it does not yet establish live recommendation quality.

## Outreach cleanup — 14 October

The backend suite passes 70 tests, including no-route screening, immutable backup verification, replay protection, restoration of canonical IDs on improved batches and refusal to archive employers that have newer contact data. Local and remote cleanup each archived 201 records. Supabase now retains 7,309 real employers, 201 minimal archived dispositions and compact source references. Original CSV remains unchanged. The audit found 6,544 potential digital routes, 726 postal-only records, 39 ambiguous digital records and 22 possible name/town duplicate groups; none establishes channel validity or a confirmed duplicate. Real matching publication still requires accepted evidence. Website returns HTTP 200 locally in explicit demo mode. SMTP delivery remains untested.

## Published real starter pool — 14 October

Published 39 reviewed CSV employers, 45 first-party activity claims and 42 MiniLM facet embeddings to Supabase. Real search smoke checks return software 4, accounting 2, legal 4, mechanical 1, marketing 3 and nursing 2; unsupported HR and niche research cases abstain. The actual gateway/worker saves four real software matches, withholds names/counts before confirmation, blocks results/unlock, and rejects a different browser owner. Synthetic access-check records were removed and no email was sent. 74 backend tests pass. Runtime is live Supabase with email verification enabled; the earlier demo-only runtime and zero-real-document state above are historical. SMTP delivery, actual email callback, broader coverage, human evaluation and full load/latency targets remain pending. See docs/REAL_MATCHING_PILOT.md.

## Stable local form — 14 October

Reproduced a rapid development Fast Refresh loop in browser logs and server rebuild output. The local launcher now builds and serves the standalone frontend by default; intentional live reload requires --watch. Optimized build and TypeScript checks pass. Browser verification typed background/role fields, advanced through all three steps, returned through Back, and confirmed retained values. Test values were cleared without submitting or sending an email. Live catalogue remains 7,309 real records, verification required; localhost ownership cookies persist with HttpOnly/SameSite=Lax and HTTPS production retains Secure. Screenshot: data/verification/stable-onboarding.png.

## Compact contact cards — 16 October

All recorded non-rejected contact routes are now available on authorized cards, independently of the stricter eligibility gate. Duplicate routes collapse. Contact-state history remains in the backend; the redesigned UI omits import/check labels, dates, full web URLs, initial avatars and the sources/register details block. Email/phone render as compact rows; websites, careers and LinkedIn use small buttons; repeated job-board links are grouped in accessible native menus. Official-site favicons are stored locally where fetched successfully; fallback icons do not expose user requests to third-party favicon services. Match explanations have a short grounded summary while retaining full supporting data internally. Added spam/junk reminders before resending and to account sign-in confirmation.

79 backend tests pass, including presentation deduplication, rejected/unsafe routes, unchanged relevance gates, preview access and concise summaries. Rendered the actual Card component with three public employer fixtures: 9Nexus 5, A Tech 8 and A&A Communication 5 unique links. Verified the Indeed menu opens to two distinct links, no duplicate hrefs occur within each rendered card, and removed metadata/avatars are absent. This visual fixture does not bypass the live application authorization.

The final optimized frontend build and TypeScript check pass. Desktop and 390px mobile screenshots are saved under data/verification/compact-cards-*.png. The mobile fixture has no horizontal overflow. Layout decisions use NN/g Cards: UI-Component Definition (https://www.nngroup.com/articles/cards-component/) and Material card guidance: concise summaries, consistent scan order and compact actions. Screenshot fixtures render the actual production Card component with public employer data.

## Full-catalogue preparation and prospect testing — 16 October

Published 237 additional real employers, bringing the live index to 276 employers / 283 documents / 322 accepted first-party activity claims. All 7,309 retained records have an outcome; the remaining 7,033 are not currently recommendation-ready. Deterministic source corroboration is explicitly distinct from human-reviewed accuracy. Paid embedding/model calls: zero. Live database size measured 200,726,195 bytes. Public-row backup and hash manifests are retained; no private accounts/profiles/results were copied or removed.

The 253-profile final run completed 251 cases and requested clarification for two. 179 had direct results, 69 abstained, three had only opted-in related results and 147 had at least three direct results. Across 3,186 recommendation instances, all seven evidence/ownership-of-source eligibility consistency checks passed. Four metamorphic checks passed. Found and fixed the senior-prefix / imported-SOC alias collision, with a regression test and cache invalidation through ranking evidence-4. Human precision, NDCG, pooled recall and explanation-support release gates remain unmeasured.

The isolated k6 four-VU / 20-second probe completed 154 workflows, 806 HTTP requests, 770 passing checks, zero failed HTTP requests and 429 ms p95 completion. No emails or live Supabase test candidates were created. Synthetic local records were cleaned by exact run marker. These measurements exclude Next.js, Auth and remote DB latency. A cold concurrent Supabase probe returned 22 software / 22 senior-software / zero HR matches in 11.30 / 11.42 / 2.85 seconds respectively; the three-second live target is not established.

The evaluation HTML filters career profiles and exports reviewer labels; browser testing verified visible filtering, label count updates and restoration to zero judgments. No console errors. Latest application build and TypeScript validation pass. Detailed operational commands, gaps and measurement scope: docs/CATALOGUE_EVALUATION.md.

Final backend suite: 89 passed. Added explicit taxonomy-version document regeneration coverage. The production frontend build/TypeScript check and localhost page/report health checks pass. Website and the operator evaluation report remain running locally.

## Profile quality update — 17 October

272 profile variants across 16 professions; 69 browser form payloads checked; 111 backend tests passed. General role-context ranking fixes and explicitly AI-reviewed development metrics are documented in [PROFILE_QUALITY.md](docs/PROFILE_QUALITY.md). Human release-quality gates remain unverified.

## Prospect discovery and coverage loop — 17 October

Added corpus-derived career ideas, explicit specialization selection, versioned employer exposure accounting, resumable synthetic prospect iteration and post-index background model refresh. The first experiment reran 516 profiles and generated 200 more, reaching 1,370 employers, including 227 new records. Every retained employer has an outcome. Full reachability and general semantic ranking replacement remain active work; see [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).

## General semantic experiment — 17 October

133 backend tests pass. The free local semantic experiment uses official occupation data and source spans without profession/company exception lists. It tested 272 form variants and records all-employer exposure and best-reaching profiles. Version 7 reached 4,620/7,309 retained employers; it is not promoted. AI review of 145 anchor pairs found 141 direct, three insufficient-evidence and one related result. Independent human validation, related-career parity, remaining corpus gaps and deployed performance remain incomplete. Full evidence and exact limitations: [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).


## Evidence alternatives and private cohorts — 17 October

142 backend tests pass. The semantic experiment now checks multiple source alternatives; reach remains incomplete at 4,618/7,309 employers. Versioned derived-interest cohorts are stored privately, refreshed after prospect-model publication, and aggregated without owner/session identifiers. The two existing ready sessions were associated while exact ranking/access/ownership checks stayed unchanged; a background refresh completed successfully. A local NLI probe failed the diagnostic comparison and remains disabled. Current allowlisted operator dashboard: http://127.0.0.1:4019/. See [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).

## Broader occupation audit — 17 October

150 backend tests pass, including omitted-domain alias ambiguity, source lineage, occupation-conditioned relation checks and source-attribution gates. The version-11 semantic experiment evaluated 7,767 distinct saved profiles, reached 4,757 employers, and completed without matching errors. Of 1,213 unreached professionally described records, 193 were eligible below the saved-shortlist cap and 1,020 had no eligible result. No profile hit the 1,500-employer retrieval cap. These are exposure diagnostics, not relevance accuracy.

272 full-form variants remain reproducible. A separate deterministic sample of 27 occupations spans all nine major SOC groups. AI review of all 62 returned top-three pairs found 38 direct, six related, ten insufficient-evidence and eight irrelevant pairs; four profiles abstained. Mean returned direct Precision@3 is 59.4% across the 23 nonempty profiles. This development sample informed tuning and is not held out or independently human reviewed. Top-ten precision and recall are not established for that sample. The quality gate failed, and the experimental matcher was not promoted.

The allowlisted operator dashboard at http://127.0.0.1:4019/ shows both original and broader samples, their evidence and exact coverage gaps. HTTP checks confirm the latest version and failed-quality notice are visible. Mobile browser inspection found a 390px viewport and 390px page width; report links reach the broader review. The live onboarding page returns HTTP 200. No real accounts, emails, payments, employer records or saved rankings were changed by these experiments.

The additional pinned local Qwen instruction-model probe completed on all 62 broader development pairs. All outputs passed JSON/exact-quote validation, but six of 33 direct decisions disagreed with the AI review and eleven of 38 AI direct pairs were missed. Direct-judgment precision 81.8%, recall 71.1%; 207.94 seconds inference excluding loading/download. Rejected as a matching gate; no runtime integration or production dependencies added. Full methodology and repeatable command: [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).


## Version-12 source-coherent evaluation — 17 October

166 backend tests pass, including completed coverage metadata and resumable exposure accounting. The 92 sponsor-link corrections were independently verified on Supabase with unchanged identity/business/contact/vector/private-result data and no merges/deletions. The new prospect model's production cohort refresh is done, attempt one, with no error. Live ranking remains the existing baseline.

On model `cdbd25ac18bbcbf97ddf07d6`, the completed experimental run reached 4,798/7,309 employers over 8,101 distinct profiles; 1,602 reached the preview positions. Every retained employer has a recorded outcome, but 2,511 remain unreached. The 272 full-form variants and broader 27-occupation sample use the same model, ranker and register snapshot. Broader AI development Precision@3 is 66.7%; independent human validation and recall remain unmeasured. No release claim is made.

The additional 25,805-title local diagnostic rejected 13 direct pairs while removing one irrelevant pair, so it remains outside matching. The operator dashboard now publishes exact-version manifests, guarded against mixed model/register artifacts, with only allowlisted public employer evidence and synthetic profiles. Full backups/private user rows are excluded. More details and limitations: [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).


## Full replay catches niche regression — 17 October

170 backend tests pass. The family-aware official-title diagnostic retains all 181 AI direct pairs in its 205-pair development sample and removes one irrelevant pair. The 272 original form shortlists remain identical, while the 27 broader profiles retain 66.7% mean returned direct Precision@3. Version 13's completed 8,183-profile replay reaches 4,791 employers, seven fewer than version 12. Inspection shows those seven are exact/niche historical-role matches incorrectly rejected by a taxonomy disagreement; version 13 is rejected.

Version 14 preserves strong direct wording before the new title veto. All seven targeted regressions now pass. Its 299 form reruns are complete and its full coverage replay is in progress, so a final version-14 reach count is not yet claimed. Review reuse requires unchanged profile/source signatures; changed/new pairs remain unjudged. The exact-score tie audit finds 136 employers hidden at selected cutoffs, including 37 previously unreached employers, without changing tie order or scores. The operator report records completed source-specific runs and their non-promotion reasons. The website remains on the existing live baseline.


## Source-aware ties and valid-profile frequencies — 17 October

187 backend tests pass. Completed experimental version 15 reaches 4,819 employers, including 34 gains and 13 losses versus version 14. Gap replay covers 8,193 raw calls and identifies 183 eligible employers below the saved-shortlist cap plus 1,054 without an eligible result. A readiness audit excludes one broad Analyst profile from valid frequencies: 8,192 confirmed profiles still reach exactly the same 4,819 employers, 1,681 in previews and 2,968 in top tens. All seven niche regression cases pass. The generator now checks confirmation/clarification before future baseline and generated searches; its new proposal version has not yet completed a discovery run.

The 272 full-form variants and 27 broader profiles were rerun. AI development direct Precision@3 remains 100% on the original nonempty anchors and 66.7% on the broader sample. Original-family Precision@10 is 95.02%, with new product/function gaps. Independent human validation and recall remain unmeasured. Experimental ranking remains unpromoted.

The free local source-only classifier processed 59 selected development sources, with 57 schema/exact-quote-valid outputs and semantic mistakes still present. It stays outside matching. Operator publications now hash all copied inputs, verify their copies and preserve earlier content-specific bundles. The current dashboard points to confirmed-profile frequencies while retaining the raw trials and readiness audit. Complete methodology: [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).


## Human review provenance — 17 October

193 backend tests pass. Review exports are bound to exact profiles, displayed evidence/contacts, model/ranking/register versions and positions. The scorer rejects stale, edited, conflicting or AI-labeled imports; missing judgments/support marks remain unknown, with recall and release readiness unclaimed.

An isolated synthetic browser fixture verified unchanged reload persistence, changed-source reset, typed metadata export and 390px layout without overflow. The exported unjudged fixture and the real unjudged matrix packet both score as zero reviewed pairs, not perfect accuracy. Fixture storage and the temporary served link were removed. No real human judgments or account actions were generated. Current operator reports retain source-specific and content-specific publication hashes and point to valid confirmed-profile frequencies.


## Generalized proposals and sampled occupations

201 backend tests pass. New checks cover source-backed interest provenance, unknown niches, technical punctuation, relative occupation-hypothesis pruning, stable occupation-stratified sampling, bounded task descriptions and the absence of invented qualifications. The complete proposal run evaluates 12,223 confirmed profiles, reaching 4,830 employers (11 gains, no losses); a broad Analyst proposal is withheld before matching. All 11 gain pairs replayed exactly. Their separate AI inspection marks eight direct, one related and two insufficient, so reach is not claimed as verified relevance.

A new deterministic 144-profile matrix spans 18 occupations across all nine major SOC families. All profiles pass the API confirmation policy. Its 51 top-three pairs are AI-reviewed development diagnostics: 22 direct, nine related, ten insufficient and ten irrelevant; mean returned direct Precision@3 is 42.6%. Precision@10, retrieval recall and independent human accuracy are unmeasured for this matrix. The findings expose broad semantic failures and prevent matcher promotion. Website `/match` returns HTTP 200 and API health returns `ok`. Completed gap replay verifies all 12,223 profiles: 173 eligible employers fall below the saved-shortlist cap, 1,053 have no eligible result and zero profiles hit the retrieval cap.
