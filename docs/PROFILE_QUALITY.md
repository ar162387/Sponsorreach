# Profile quality and general matching — 17 October 2026

Completed 272 profile variants across 16 professions, with 69 actual browser form submissions checked against expected payloads. The browser tests used real local profile normalization and intercepted final submission to avoid sending emails or creating production candidate records. Engine tests used the full real local catalogue.

111 backend tests pass. All 7,309 live employers / 9,137 embeddings remain onboarded; this work changes ranking and evidence interpretation, not catalogue inclusion. Ranking: `evidence-11-general-role-context`.

## Matching changes

- Preserve uncommon specialization terms using occupation-corpus token frequencies rather than new per-profession lists.
- Recognize longer occupation titles before accepting a shared head noun. Imported occupation-code groups are not treated as universal synonym lists.
- Split supplied role/activity lists for relevance attribution. Unrelated titles cannot provide skill or career-stage credit. Keep original source excerpts and separate matched spans.
- Give supported interests representation in multi-role previews.
- Deduplicate skill/certification credit; unmatched optional skills do not dilute existing supported credit.
- Distinguish delivery of professional services from mentions in training, education or merchandising contexts.

No new occupation-specific SEEDS or ACTIVITY_SYNONYMS were added. Existing bootstrap mappings still exist. Imported ONS concepts and aliases cover a wider range, while unknown titles retain their raw terms. These changes are conservative heuristics, not a universal occupation-understanding model; narrow synonym recall, broader/related concept relationships and profession coverage still require more evaluation.

## Measurements and limits

166 explicit AI-reviewed family/employer judgments, with 247 top-result appearances reviewed across 32 minimal/complete anchor profiles. These are development judgments made by the implementing assistant, not independent human labels or held-out acceptance results. All release gates remain false. Contact usefulness means a recorded contact route exists; deliverability and current vacancies were not tested.

Comparable original 10-family set (20 anchors):
- Before: returned-result Precision@3 0.907, Precision@10 0.878, NDCG@10 0.938; fixed-slot Precision@3 0.817, Precision@10 0.790.
- After: returned-result Precision@3 1.000, Precision@10 1.000, NDCG@10 0.979; fixed-slot Precision@3 0.850, Precision@10 0.815.

Returned-result precision uses the actual returned count and excludes empty searches. Fixed-slot precision divides by K and includes empty positions and abstentions. Shortlists below K and per-profession coverage are published alongside these metrics. Pooled recall is only over reviewed employers, not the entire catalogue. The stricter model reduced reviewed pooled recall on the comparable set from 1.000 to 0.956, so coverage remains a tradeoff to improve.

All 16 tested synonym variants and related opt-ins preserved direct top-three results. All 15 multi-role cases with support for both interests represented both interests in the preview. Quantum research correctly has no supported first-interest results. Identity and visa context stay outside the professional profile.

Optional fields affected rankings: removing specialization changed top-three results in 3/16 families; skills 4/16; experience 4/16; certifications 6/16; industries 7/16. London/Manchester/relocation changes did not affect these results because actual workplace evidence is unavailable. The current website cannot promise location-specific workplaces from registered addresses.

Local engine p50 133 ms / p95 297 ms / p99 409 ms in this development run. These are local measurements and do not establish live Supabase or complete website latency.

## Reproduction

From backend:

```sh
uv run --no-sync python ../scripts/profile_matrix.py ../data/evaluation/new-run
uv run --no-sync python ../scripts/summarize_profile_matrix.py
```

The summarizer currently points to this dated evaluation folder. Browser harness: `scripts/browser_form_matrix.py`; its selected variants and explicit route interceptions are recorded in code. Review artifacts, before/after runs, comparisons and browser payload captures are under `data/evaluation/2026-10-17/`. Interactive report: http://127.0.0.1:4012/quality.html.

Human review remains needed before reporting independent precision, explanation-support or launch readiness. Future targeted improvements should focus on general concept relationships and occupation evidence rather than adding keyword exceptions for individual test cases.

## Free-plan connection budget

A live Supabase probe returned software 100 / plumbing 4 results with the new hybrid index. Cold durations were 54.51 and 10.16 seconds while the Session pooler reported its 15-client ceiling. Reduced default per-process pools from eight to four and default worker concurrency from four to two. API plus worker now reserve at most eight connections; `SPONSORMATCH_DB_POOL_SIZE` and `MATCH_WORKER_CONCURRENCY` make the limits explicit. Remote latency remains an outstanding target; local measurements must not be used as a substitute.

Five additional browser submissions cover alternative visa routes/dates and a signed-in refinement with no repeated identity fields.

## Public catalogue cache and measured remote checks

A trace identified approximately 1.9 MB of taxonomy and 1.9 MB of employer JSON transferred per uncached software search. Added a compressed SQLite cache under the ignored application `.local` directory, isolated by database identity. Only employer and taxonomy records are cached. Every employer read checks current ID/version headers in Postgres; deleted/missing headers and changed versions cannot reuse old values. Taxonomy snapshots use a SHA-256 signature of current concept payloads; the existing 30-second memory cache remains. Cache failures fall back to database reads. Cache storage is bounded to 10,000 records per type/database and survives process restarts.

Seeded the cache from the prepared 7,309-company catalogue; cached records cannot be used unless current live versions match. Added a small employer updated-at index and batched independent search metadata reads. No company records were removed. Tests cover database isolation, version changes, missing headers and disk failure fallback. The migration is replayable through the existing migration runner.

Three subsequent remote engine checks, with the model loaded and public cache seeded, took 7.25 s (software, 100 results), 2.57 s (plumbing, 4 results), and 3.42 s (nursing, 96 results). A repeated nursing query took 1.56 s. Profiles differ slightly from earlier tracing probes; these are smoke measurements, not a controlled p95 benchmark. Remote latency remains a release gap.

The separate browser branch test also passed career exploration confirmation, the three-role limit and Back-button context retention. Final backend suite: 111 passed. Production frontend build and TypeScript validation pass.
