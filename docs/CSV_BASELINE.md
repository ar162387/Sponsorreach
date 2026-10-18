# Full CSV catalogue — 16 October 2026

The operator-authorized CSV baseline replaces the earlier 276-company corroborated-only pool. All **7,309 retained employers** have **9,137 MiniLM embedding documents**. The 201 records archived by the no-outreach cleanup remain archived; the original CSV is unchanged. There is no scraper integration.

6,461 employers have recorded professional descriptors; 848 have identity/contact details only. Identity-only documents retain catalogue coverage but cannot pass the professional relevance gate without relevant evidence. Being indexed does not guarantee recommendation: current Skilled Worker A-rated linkage, a useful route and explicit professional alignment still apply.

CSV descriptors are typed `provided_csv`, with exact excerpts and source-record references. They are accepted as the supplied baseline, with initial evidence multiplier 0.40. They are not represented as freshly verified website observations. Recorded role tags remain historical; CSV job counts never establish current vacancies. No willingness-to-sponsor or immigration-eligibility claim is inferred. Generic sector evidence cannot establish internal HR/legal/finance/marketing functions.

## Repeatable manual imports

Use the same installation/table namespace for later CSV batches. That namespace now persists `provided-csv-baseline-1`; subsequent manual imports automatically apply the same policy. Stable source identities and replay protection remain. Missing records in a later batch do not revoke existing employers. Run the index builder after changes; unchanged semantic content reuses vectors. No paid model calls are required.

From `backend`:

```sh
uv run --no-sync sponsormatch import-csv /absolute/path/new.csv --namespace local:nocodb:company-enrichment-v2
uv run --no-sync sponsormatch index
```

For isolated staging, `activate-csv-baseline` explicitly applies the policy to an already imported artifact. The supplied catalogue was prepared locally, backed up remotely, and transferred in resumable company transactions. `scripts/publish_csv_baseline.py` checkpoints committed employers; `scripts/publish_staged_index.py` stages resumable compressed vector batches and atomically switches the active version after hash/count validation. Private account/profile/session/feedback tables are not copied or removed. Previous index versions remain available. Public-row backup: `data/releases/2026-10-16-csv-baseline/live-public-before.json.gz`.

Current staged index: `10ab30bf-5844-40f0-bf87-08e44e4b7632`. Embeddings use pinned local all-MiniLM-L6-v2, 384 dimensions. Ranking version: `evidence-6-csv-baseline`. Saved shortlists remain frozen; run a new/refined search to use the expanded catalogue.

## Evaluation and limits

`data/evaluation/2026-10-16/full-csv-final` contains 253 synthetic prospect cases: 251 completed and two requested clarification; 250 returned direct recommendations and one abstained. All seven consistency checks passed across 13,660 recommendation instances, plus four metamorphic checks. These check source/reference/gate consistency, not independent relevance accuracy. Precision, recall, NDCG and explanation-support quality gates require human judgments; unjudged pairs are not negatives.

Engine latency on the local catalogue: p50 158.743 ms, p95 283.418 ms, p99 487.596 ms. The isolated full-catalogue k6 probe used four VUs for 20 seconds: 108 completed workflows, 683 HTTP requests, 540/540 checks passed, no HTTP failures, p95 shortlist completion 686.4 ms. It excludes Next.js, Auth and remote Supabase latency; it is not a full production capacity result. No emails or Supabase candidate profiles were created by that probe.

97 backend tests pass. The optimized Next.js build and TypeScript validation pass. Human occupational review and live remote latency targets remain outstanding. Official register snapshot remains 12 October with a seven-day freshness limit; refreshing it remains an operator task. Public hosting and final operator/privacy identity remain pending.
