# Catalogue preparation and evaluation — 16 October 2026

> **Current catalogue update (16 October):** the full operator-authorized CSV baseline supersedes the earlier 39/276-company pool: 7,309 retained employers and 9,137 search embeddings, including 848 identity/contact-only records. See [full CSV baseline](CSV_BASELINE.md) for counts, import policy and evaluation limits. Earlier dated measurements below are historical.


The live application uses all 7,309 retained CSV employer records as its catalogue. The earlier cleanup archived 201 records without any outreach route; those records remain excluded and backed up. This release does **not** make all 7,309 employers eligible for recommendations.

The published search index now covers **276 employers and 283 facet documents**, up from 39 employers and 42 documents. There are 322 accepted source-backed activity claims. The 237 newly prepared employers were checked by a deterministic source-corroboration policy; this is not human-reviewed accuracy. No vacancy, sponsorship-willingness or immigration-eligibility claims were inferred.

Index: `b8d474f4-d3fa-4013-9084-53e1a95d8532`. The previous published index is retained for semantic-index rollback. Model: pinned local MiniLM, 384 dimensions. No paid model or embedding calls were used. Measured live database size after publication: 200,726,195 bytes (approximately 191.4 MiB).

## What happened to the remaining records?

Every retained employer has a preparation outcome in `data/pool/2026-10-16-full-v2/catalogue-outcomes.json`.

| Outcome | Employers |
| --- | ---: |
| Prepared for matching | 276 |
| No activity mapping in the current professional taxonomy | 4,915 |
| No professional descriptor | 852 |
| No recorded first-party website for corroboration | 305 |
| Shared domain needing identity review | 210 |
| Distinctive full name not confirmed on source | 171 |
| Source unavailable | 135 |
| Page identity not confirmed | 114 |
| No exact professional activity span | 203 |
| No unambiguous current sponsor linkage | 59 |
| Changed website hostname | 21 |
| Professional context needing review | 20 |
| Generic identity needing review | 15 |
| Ambiguous name/town identity | 11 |
| Private-network URL or oversized source rejected | 2 |

These describe preparation limitations, not conclusions that the CSV companies are incorrect or professionally unsuitable. The current activity taxonomy covers 24 professional families; imported SOC title aliases do not automatically provide activity-to-profession relationships. Increasing catalogue coverage requires additional reviewed mappings, evidence for observed functions and targeted source preparation. Generic sector similarity must not establish internal HR, legal, finance or marketing roles.

957 unique website candidates were processed. A second wording pass reused 812 same-day source reads and fetched 145 additional candidates. New equivalent phrases include home care, residential care, supported living and community pharmacy. Sources are bounded to public HTTP(S), IP-pinned, download-limited and checked against recorded hosts. Failed sources and shared domains remain excluded. Raw CSV observations and contacts are preserved; unrelated scraper operations are untouched.

## Repeatable prospect evaluation

The suite contains **253 synthetic prospects**: ten variants across each of 24 families, plus 13 adversarial/multiple-intent/synonym cases. It runs against real employers only and writes no candidate profiles. Human relevance labels are kept separate from source-consistency checks.

Final run:

- 251 completed searches; two broad titles correctly requested clarification.
- 179 profiles returned direct recommendations; 69 returned no recommendations; three additional profiles returned only opted-in related recommendations.
- 147 profiles had at least three direct results.
- 3,186 returned recommendation instances passed each of seven automated consistency checks: real employer, accepted identity, current sponsor linkage, useful channel, existing evidence references, accepted evidence and related-career opt-in.
- Four metamorphic checks passed, including preservation of software matches under a senior prefix, preservation of direct results when related careers are enabled, niche abstention and broad-role clarification.
- No automated consistency violations. **This is not a measured precision or explanation-support rate.**

Seven direct professional families still have no supported results: HR, financial analysis, research, psychology, project management, technical sales and compliance. Internally publish these gaps alongside aggregate coverage.

Representative direct counts: software 22, accounting 43, legal 16, nursing 7, marketing 12, civil engineering 17, mechanical engineering 2, electrical engineering 2, pharmacy 3, HR 0. Saved direct shortlists remain capped at 100; counts vary with the profile and current accepted evidence.

Evaluation exposed and fixed a real normalization bug: an imported SOC alias for “Senior software engineer” masked the supported base software concept. Stage prefixes now resolve through the base profession. Ranking version `evidence-4` invalidates older cached rankings.

Run from `backend`:

```sh
DATABASE_URL=postgresql://localhost:55432/sponsormatch uv run --no-sync sponsormatch benchmark-prospects --output ../data/evaluation/new-run --concurrency 2
```

Outputs: `report.html`, `report.json`, `runs.json`, `rankings.json`, `prospects.json` and `review-template.json`. The HTML report filters profiles and lets reviewers label relevance and explanation support, retaining edits locally and exporting JSON. Labels default to `unjudged`; testing the controls did not leave any judgments saved.

```sh
uv run --no-sync sponsormatch evaluate ../data/evaluation/new-run/rankings.json /path/to/review-labels.json --k 3
uv run --no-sync sponsormatch evaluate ../data/evaluation/new-run/rankings.json /path/to/review-labels.json --k 10
```

Precision and NDCG require reviewed top results. Unjudged pairs are never negatives. Precision uses the number of returned results; inspect shortlist underfill separately. Pooled recall is limited to judged results and available ranking depth, not exhaustive recall over the catalogue. Human labels, occupation-stratified development/held-out evaluation, retrieval ablations, ANN-vs-exact recall and independent explanation audits remain outstanding. No release-quality gate is claimed passed.

## Load measurements and their limits

The isolated local k6 harness exercises actual match creation, queue processing, local embeddings and local Postgres. It checks result withholding, email verification and owner isolation. It sends no emails, creates no Supabase candidate records and cleans up only its own uniquely marked local synthetic records.

```sh
uv run --no-sync python ../scripts/run_load_probe.py --vus 4 --seconds 20 --output ../data/evaluation/load-run
```

Measured probe: four virtual users over 20 seconds, 154 completed workflows, 806 HTTP requests, 770/770 checks passed, zero HTTP failures, 429 ms p95 match completion. This is a small closed-loop probe, not a 50-client capacity test or a 10-new-matches/second acceptance result. Model startup is warmed before this probe; new synthetic summaries exercise uncached match queries.

The 253-profile engine run measured 142.643 ms p95 on local data, including two initial model-load outliers; it excludes HTTP, queue, Auth and remote database latency. A separate cold two-search Supabase probe took 11.30 and 11.42 seconds for software/senior software, each returning 22 results; HR returned zero in 2.85 seconds. That includes model startup and concurrent remote queries. **The live cold-match three-second target is not met or established.** Local performance numbers must not be presented as live application latency.

## Publication and recovery

Public employer changes were staged locally, checked, then copied to Supabase atomically. Candidate profiles, accounts, feedback and saved results were not copied or deleted. A verified gzip backup of the modified live public rows is stored at `data/pool/2026-10-16-full-v2/prepublish-live-public.json.gz`. Source manifests retain exact excerpts and hashes. Existing saved shortlists stay frozen; a new search uses the expanded index.

Use a new dated preparation folder for each later CSV batch. `prepare-pool --per-family 100000` processes all currently mapped source candidates; `--cache-dir` only reuses same-URL reads at most 24 hours old. `publish-prepared` is a staging operation; inspect its full-catalogue outcomes and manifest before transferring public rows. The publisher refuses employers that already have accepted live evidence, preventing silent overwrites. Incremental revalidation of previously accepted employers must use the observation-preserving update path.

The current official snapshot is dated 12 October and has a seven-day recommendation freshness limit. Refresh is still an operator task; no recurring automation was created. Public hosting, the final operator/privacy identity, human quality gates and full-scale load targets remain pending.
