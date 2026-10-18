# SponsorReach UK

> **Current catalogue update (17 October):** the full operator-authorized CSV baseline supersedes the earlier 39/276-company pool: 7,309 retained employers and 9,137 search embeddings, including 848 identity/contact-only records. See [full CSV baseline](docs/CSV_BASELINE.md) for counts, import policy and evaluation limits. Earlier dated measurements below are historical.

> **Latest evaluation:** 201 backend tests pass. Experimental matcher 15 with the generalized proposal generator reaches 4,830/7,309 employers across 12,223 confirmed synthetic profiles (11 gains, no losses versus the previous profile set). The new occupation-stratified 144-profile development matrix exposes major relevance failures: AI-reviewed mean returned direct Precision@3 is 42.6% across 18 sampled occupations. This is not independent human accuracy. Live search retains its existing baseline. Reports and limitations: http://127.0.0.1:4019/ and [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md). The full goal remains incomplete.


Next.js application, Python matching API and worker, and Supabase-compatible Postgres/pgvector migrations. This is an evidence-based **employer discovery** implementation. It does not promise current sponsored vacancies.

**Current pilot scope:** [PILOT.md](PILOT.md) records the user's 13 October decisions: manually supplied CSV batches only, an independent scraper, Supabase Free, minimal model spending, and email verification before live previews. Production ledger access is no longer a prerequisite. The verification-before-preview gate is implemented for live mode; explicit local demo mode still permits browser-owned previews. The compact storage profile remains pending.

## Run locally

Prerequisites: Node >=20.9, `uv`, PostgreSQL >=16 and pgvector >=0.8. Docker is not required when a local PostgreSQL installation is available.

From the scraper workspace:

```sh
sh sponsormatch/scripts/local-db.sh
python3 sponsormatch/scripts/dev.py
```

Open `http://127.0.0.1:3000`. `/match` is the social onboarding entry point. The optional `--demo` creates **fictional**, explicitly labelled employers with non-actionable `.example` contacts; it is rejected in production. Without the flag, real imported employers use the explicitly authorized CSV baseline or corroborated evidence, with sponsor/channel/professional matching gates. Demo checkout never collects payment information.

Copy `.env.example` to `.env` in this directory for configuration. The runner loads literal values without shell execution and passes the same private API secret to web/API processes. It never reads or modifies the scraper's existing `.env`.

The local database script uses an isolated cluster under `.local/` and port 55432. It does not reset an existing database. It is for local development; configure an authenticated managed database in production.

## Data operations

Run commands from `sponsormatch/backend`, with `DATABASE_URL` set when using a managed database:

```sh
uv sync --extra test --extra local --locked
uv run sponsormatch migrate
uv run sponsormatch seed-taxonomy
uv run sponsormatch import-csv ../../scraper_data.csv --namespace local:nocodb:company-enrichment-v2
uv run sponsormatch fetch-register --output ../data/register
uv run sponsormatch fetch-ons --output ../data/taxonomies
uv run sponsormatch status
```

Use the **same explicit installation/table namespace** for CSV and ledger records from the same source. Different installations require different namespaces. Source record IDs and domain names alone do not establish identity across installations.

For this project's live workflow, import each new user-supplied CSV with the same namespace as the initial CSV. Both cumulative exports and incremental batches should add/update source records; omission from a batch does not revoke an employer. Legacy-workbook and ledger adapters remain available but are not required or part of the chosen website integration. No scraper connection is planned.

CSV/workbook/ledger imports preserve historical assertions and states. The selected CSV namespace uses the operator-authorized `provided-csv-baseline-1` policy: supplied descriptors and contact routes are available for matching without requiring a second scrape. Other namespaces remain conservative. CSV role tags never become verified functions or current vacancies. The importer stores raw CSV/workbook records. Official snapshots retain their download URL, publication date, checksum, rows and active version. Failed, truncated, older, or unexpectedly shrinking register snapshots cannot silently replace the last valid snapshot.

Claim, channel and vacancy observations retain immutable versions. Accepted claims point to their supporting observation version. Failed and late updates preserve accepted historical evidence while recording their own states. Explanations keep the supporting version IDs alongside quoted sources.

### Review and publish employer evidence

```sh
uv run sponsormatch prepare-source EMPLOYER_UUID https://employer.example/about --output ../data/source-review.json
# Optional: add --llm to extract draft, quoted claims using OPENAI_API_KEY.
# Inspect the source and add/review its claims before publication.
uv run sponsormatch review-source EMPLOYER_UUID ../data/source-review.json --identity-reviewed
uv run sponsormatch index
```

Review document shape:

```json
{
  "url": "https://employer.example/about",
  "source_text": "The actual source page text...",
  "claims": [{"kind":"activity","text":"accounting services","excerpt":"We provide accounting services."}],
  "review_status": "reviewed"
}
```

`text` and `excerpt` must occur verbatim in the captured source. The source host must match the employer's recorded website. The operator must confirm employer attribution. Generic industry evidence cannot establish internal HR, finance, legal, or marketing functions. Contact values are promoted only when corroborated by that source. Preserve original documents for audit; the review command is an operator tool, not a public API.

All initial role observations remain historical/unverified; live-vacancy verification is a separate capability. Missing evidence causes abstention or lower confidence, not invented claims.

`verify-vacancy EMPLOYER_UUID URL --attribution-reviewed` can verify a specific first-party JSON-LD JobPosting whose hiring organization matches the accepted employer and whose closing date and UK country are supplied. Unknown or overseas locations remain unverified; expired/filled adverts never get an open badge. Review employer attribution before running this operator command. The scheduler rechecks verified adverts; failed reads preserve observations and the badge expires after 72 hours.

### Taxonomies

The shipped 24 occupation families are labelled **local bootstrap concepts**, not ESCO or SOC. `fetch-ons` imports the official UK SOC four-digit and extended six-digit groups plus unambiguous job-title aliases from the current coding index. Artifacts keep version dates and checksums. Ambiguous unqualified titles are excluded; industry-qualified titles retain their qualifiers. Codes support professional normalization, not automatic visa classification.

```sh
uv run sponsormatch import-taxonomy /path/to/occupations_en.csv --namespace esco --version 1.2.1
```

The adapter accepts `preferredLabel`/`label`, `conceptUri`/`id`/`code`, and newline-delimited `altLabels`/`aliases`. ESCO bulk download currently requires an email-based download step; obtain the official 1.2.1 English CSV package at https://esco.ec.europa.eu/en/use-esco/download. Do not submit someone else's email automatically. Unknown specialized interests retain their text instead of receiving an incorrect category. UK SSC access requires a Skills Explorer account and remains optional. US/UK/ISCO identifiers must not be equated automatically.

### Model services

The default `EMBEDDING_PROVIDER=local` uses pinned Sentence Transformers `all-MiniLM-L6-v2` on CPU, generating 384-dimensional vectors without an API key or per-call fee. The first setup downloads model weights; subsequent computation stays on the application machine. Long documents are split into token-bounded chunks and averaged into one normalized vector. This needs local compute and, for an online deployment, a host capable of running the model. It does not provide free hosting.

Install with `uv sync --extra local --extra test --locked`. Download the pinned model once:

```sh
uv run --no-sync hf download sentence-transformers/all-MiniLM-L6-v2 --revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 config.json modules.json sentence_bert_config.json config_sentence_transformers.json tokenizer.json tokenizer_config.json special_tokens_map.json vocab.txt model.safetensors 1_Pooling/config.json
uv run --no-sync sponsormatch embedding-check
```

Runtime loading is cache-only: it cannot download model files or execute remote model code during a search. Model identity includes the pinned revision and chunking version. Separate typed vector columns prevent mixing local 384-dimensional vectors with legacy 768-dimensional OpenAI vectors. Existing indexes are retained for rollback.

Optional `EMBEDDING_PROVIDER=openai` enables the existing `text-embedding-3-small` adapter using `OPENAI_API_KEY`; optional offline extraction also requires that key. No paid model call is made by the local embedding path. User names, email and visa context are stored separately and are not embedded. No per-employer LLM inference runs during matching.

Embedding indexes freeze facet snapshots, reuse unchanged vectors, and publish atomically only when every snapshot document has a vector. Failed builds leave the previous index active. Inspect versions with `index-versions`, resume with `index --resume VERSION_UUID`, or restore a published version with `rollback-index VERSION_UUID`. Previous vectors and document templates remain available. Set the application embedding model to match the restored index; a model mismatch uses the evidence-gated lexical/concept fallback. Retired or changed evidence is excluded even when an older index is restored.

When embeddings are unavailable, search explicitly records `lexical_concept_fallback`. This is a genuine reduced-capability retrieval path, not fabricated semantic results. Both paths enforce the same identity, sponsor, channel and professional evidence gates. Quality improvements require human evaluation; no accuracy percentages are claimed.

## Access and auth

Opaque browser ownership tokens are HttpOnly. The server stores only their hashes. The Next.js gateway keeps the private API secret out of browser code. Results are persisted before preview; locked company identifiers/contact fields are never returned to the browser. Demo unlock reveals the same saved ranking.

For email authentication, set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` in both web and backend environments. Live mode defaults to `REQUIRE_VERIFIED_EMAIL=true`: previews, result pages, unlock and feedback require an owner-associated verified account. Pending status withholds result counts and company details. Delivery errors are shown and resending reuses the saved shortlist. The callback returns to that shortlist after account association. Configure the Supabase redirect allowlist for `APP_ORIGIN/auth/callback**`, email magic links, and production SMTP. The redirect must support the validated `next` query parameter. PKCE callback exchange is followed by server-side user verification. Account association requires both the browser ownership token and matching verified email; email alone cannot claim another session.

Private `sm` and `sm_private` schemas should remain outside the Supabase Data API. RLS is enabled on all their tables; default grants are denied. The API database connection is private and must have the privileges needed by this service. No service-role secret is sent to clients.

## Tests and evaluation

```sh
cd sponsormatch/backend
uv run pytest -q
# Include integration tests using a dedicated disposable DB:
TEST_DATABASE_URL=postgresql://localhost:55432/sponsormatch_test uv run pytest -q
uv run sponsormatch evaluation-profiles --output ../data/evaluation-profiles.json
uv run sponsormatch evaluate ../data/rankings.json ../data/reviewed-labels.json --k 10
```

Run the existing scraper regression suite with its own installed environment:

```sh
v2/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

See [VERIFICATION.md](VERIFICATION.md) for measured checks and outstanding release prerequisites.

The 240 generated profiles are synthetic test inputs, **not human-reviewed relevance labels**. Reviewers provide `profile_id`, `employer_id`, `label` (`direct`, `related`, `insufficient_evidence`, `irrelevant`, `wrong_entity`, `unjudged`). Metrics report judged coverage and pooled recall; unjudged pairs are not negatives. Release gates remain false until independent occupational coverage, explanation and identity audits exist. Cross-encoder reranking and learned ranking are not enabled.

The optional `benchmark-reranker INPUTS LABELS` command runs the planned offline experiment after `uv sync --extra rerank`. Inputs contain `profile_id`, `professional_query` (no identity/visa fields) and eligible `candidates` with `employer_id`/`evidence_text`. It compares at most 60 candidates per profile and reports model latency and labelled metrics without enabling live reranking.

`link-employers CANONICAL_UUID DUPLICATE_UUID --evidence-id OBSERVATION_ID --identity-reviewed` supports reviewed legacy/V2 reconciliation. Different company numbers are rejected. Source keys move to the canonical employer; the duplicate and audit history remain quarantined. Shared domains never cause automatic linkage.

## Production and operational checklist

`compose.yaml` provides private API/worker containers and a web container suitable for a TLS reverse proxy. It uses a managed database configured through `.env`, and does not expose the API publicly. Docker image builds were not executed in this environment because Docker is unavailable.

- Apply generated migration files only to a dedicated SponsorReach project/database; the connected unrelated project was not modified.
- Set `SPONSORMATCH_ENV=production`, a shared API secret of at least 32 characters, `APP_ORIGIN`, and managed credentials. Keep the Python API private to the web gateway.
- Configure the actual controller name/privacy email and review the privacy policy, processing basis, provider agreements and transfer arrangements before public use.
- Run the worker as a separate supervised process. The worker defaults to four bounded execution threads (`--concurrency` supports 1–8); `--once` processes one job. Postgres jobs use expiring leases, bounded attempts, backoff and a dead-letter state.
- Schedule `fetch-register` daily, `schedule-refresh` daily, and `purge-expired` daily using the deployment's scheduler. Do not automatically close vacancies on timeouts or crawl blocks.
- Match sessions expire after 30 days. The retention command removes expired profiles, sessions, feedback and query caches; daily deletion must actually be scheduled.
- Monitor queue lag/dead work, API latency, snapshot age, evidence coverage, broken channels and provider costs. Saved results recheck live authorization/channel/claim state before rendering.
- Back up the managed database and snapshot files. Keep model/template/taxonomy/ranking versions with saved results. Use a new embedding model ID to avoid mixing vector spaces; rebuild before switching traffic.
- Benchmark at the intended catalogue size and request rate before declaring the latency/scale targets met. Human precision targets and full-catalogue capacity are **not** established by the developer test suite.

## Current verification boundary

Local Postgres migrations and the real CSV/register import paths are exercised. Optional cloud-model credentials, SponsorReach Supabase auth/SMTP configuration, full external taxonomy downloads, reviewed real employer evidence, human quality labels, the pending Free-tier storage changes and production deployment remain installation/launch dependencies. The scraper ledger is not required for the selected CSV-only workflow. The UI labels sample data and all sponsorship/job uncertainty accordingly.

## Credentials supplied on 14 October

The application now accepts `SUPABASE_CONNECTION_STRING` as an alias for `DATABASE_URL` and safely substitutes a separately supplied password in recognized URI placeholders. CLI/API read only the application `.env`, without executing shell text or reading the scraper `.env`.

Supabase Auth responds to the supplied URL/key. The original direct database host has an AAAA record but no A record. The user supplied the same-project Session pooler URI, which is configured and successfully connected. Dedicated application migrations have now been applied through that connection. The connected MCP project differs from the supplied project, so it has not been used for remote changes.

Resend domain listing returns HTTP 403 with the supplied key. This may be a send-only scope; it does not establish whether sending will work. No test email was sent. A verified sender/domain and Supabase custom SMTP configuration remain unverified. No privacy inbox was invented.

The initial Supabase import contained 7,510 employers from the supplied CSV. Outreach screening has since archived 201 without any recorded contact route or postal address, leaving 7,309 catalogue employers; compact archive references preserve source traceability. The one-time `scripts/publish_initial_catalogue.py` bootstrap refuses a nonempty target and excludes local candidate/demo data. Future uploads use the idempotent CSV importer with the same source namespace. Real professional evidence still needs validation before recommendation publication.

## Outreach screening — 14 October

Archived 201 no-route employers from local and Supabase catalogues after writing verified full backups. Retained 6,544 with potential digital routes, 726 postal-only records and 39 ambiguous-channel records for review. These are structural counts, not verified outreach or matching coverage. Future CSV imports screen no-route rows and preserve canonical IDs for later restoration. See [cleanup policy](docs/DATA_CLEANUP.md) and [email setup](docs/EMAIL_SETUP.md). The backend suite now passes 70 tests.

## First real matching pool — 14 October

The local app is now running against Supabase with verified-email access and zero fictional employers. Published 39 reviewed employers, 45 attributable activity claims and 42 real local-model embeddings. The remaining 7,309-record catalogue is not all indexed yet. Real search and live pre-verification access checks pass; 74 backend tests pass. Email delivery, the real confirmation callback and human quality/load gates remain unverified. See [pilot evidence and limitations](docs/REAL_MATCHING_PILOT.md).

## Stable local preview

`python3 sponsormatch/scripts/dev.py` (from the scraper folder) builds and serves the compiled standalone website, API and worker. It uses the configured real database and keeps email verification enabled. The default avoids development hot-refresh loops that can interrupt form entry. Use `--watch` only while intentionally editing the frontend; add `--demo` only for isolated local fictional fixtures. HTTP loopback preview cookies remain HttpOnly and SameSite=Lax, while production HTTPS cookies remain Secure.

## Full-catalogue preparation — 16 October

All 7,309 retained CSV records have a preparation outcome. Live search now indexes 276 real employers / 283 free local MiniLM facets, up from 39 / 42. The remaining 7,033 records are retained but not recommendation-ready; most need activity mappings or additional source attribution. No paid models were used. The website is running at http://127.0.0.1:3000/match. See [catalogue and evaluation results](docs/CATALOGUE_EVALUATION.md) for the complete breakdown, repeatable 253-prospect suite, review UI and bounded k6 workflow. Precision/recall are not established without labels; small local load results do not establish live Supabase performance.

## Profile quality update — 17 October

272 profile variants across 16 professions; 69 browser form payloads checked; 111 backend tests passed. General role-context ranking fixes and explicitly AI-reviewed development metrics are documented in [PROFILE_QUALITY.md](docs/PROFILE_QUALITY.md). Human release-quality gates remain unverified.

## Prospect discovery and coverage loop — 17 October

Added corpus-derived career ideas, explicit specialization selection, versioned employer exposure accounting, resumable synthetic prospect iteration and post-index background model refresh. The first experiment reran 516 profiles and generated 200 more, reaching 1,370 employers, including 227 new records. Every retained employer has an outcome. Full reachability and general semantic ranking replacement remain active work; see [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).

## General semantic experiment — 17 October

All-facet experimental coverage reached 4,620 employers after evidence-relation checks; 272 full-form variants and 145 AI-reviewed anchor pairs are retained. The live matcher remains unchanged pending quality validation. New local review and coverage reports, exact gaps, known failures, and 133 passing tests are documented in [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).


## Evidence alternatives and private cohorts — 17 October

142 backend tests pass. The semantic experiment now checks multiple source alternatives; reach remains incomplete at 4,618/7,309 employers. Versioned derived-interest cohorts are stored privately, refreshed after prospect-model publication, and aggregated without owner/session identifiers. The two existing ready sessions were associated while exact ranking/access/ownership checks stayed unchanged; a background refresh completed successfully. A local NLI probe failed the diagnostic comparison and remains disabled. Current allowlisted operator dashboard: http://127.0.0.1:4019/. See [PROSPECT_COVERAGE.md](docs/PROSPECT_COVERAGE.md).

## Skills and search-quality lab — 18 October

The local candidate uses the full pinned ESCO occupation/skill resource and recorded company spans, with explicit task context, typed knowledge relationships and source-version checks. It remains behind a feature flag; the hosted pilot ranker has not been replaced. See [SKILL_MATCHING.md](docs/SKILL_MATCHING.md).

The private relevance lab compares identical frozen profiles, collects blinded pooled reviews, calculates per-query and occupational-slice metrics, and traces retrieval/fusion/gate/ranking failures. The current local comparison contains 299 profiles across three versions. AI development judgments are distinct from human validation. See [RELEVANCE_EVALUATION.md](docs/RELEVANCE_EVALUATION.md) for research, metric definitions, commands and limitations. Reports and employer data remain outside Git.
