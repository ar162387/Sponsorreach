# Current pilot decisions — 14 October 2026

> **Current catalogue update (16 October):** the full operator-authorized CSV baseline supersedes the earlier 39/276-company pool: 7,309 retained employers and 9,137 search embeddings, including 848 identity/contact-only records. See [full CSV baseline](docs/CSV_BASELINE.md) for counts, import policy and evaluation limits. Earlier dated measurements below are historical.


These user decisions supersede the original production-sync and $100–300/month assumptions. They describe the next live pilot; changes marked pending are not yet implemented.

## Data intake

The website receives manually supplied CSV batches only. The scraper runs independently. No scraper server access, production ledger, scraper API credentials, polling, webhook or continuous sync is required.

Use `scraper_data.csv` as the initial live catalogue. Do not import the early workbook or fictional demo fixtures into the live project. Later uploads may be incremental batches or cumulative exports. Preserve the same source installation/table namespace, reconcile source IDs and UUIDs, add new records, and update existing records without creating duplicates. Missing rows in a batch do not mean deletion. Failed and older observations must preserve accepted evidence.

The official sponsor register remains a separate source for route/rating authorization. It is not a connection to the scraper. CSV tags and reported job counts remain historical assertions; professional claims/contact attribution need validation using the available evidence URLs and employer pages. Credentials alone do not turn imported assertions into verified recommendations.

## Budget

Use Supabase Free initially. Use the pinned local 384-dimensional MiniLM embedding model by default, without an API key or per-call fees. Local compute is still required; optional OpenAI embedding support remains available. Avoid blanket LLM reclassification of every company. Use deterministic normalization and only targeted offline extraction when necessary. Existing Kimi/other provider access is optional; establish its API endpoint, model access, pricing and embedding support before introducing an adapter.

The local database measured approximately 202 MB on 13 October, before real generated vectors. Supabase Free currently allows 500 MB of database data and 1 GB of object storage. The local measurement includes development/history data and does not predict the deployed project's final size. Free-tier public uptime and capacity are not guaranteed.

Before scaling imports, implement a compact deployment profile: keep immutable original CSV/register artifacts and older audit/index archives outside the live database, retain traceable current evidence in Postgres, bound rollback/history retention, and measure table/index sizes before publication. Do not silently discard provenance to meet a quota. Object-storage quotas and archive sizes also need measurement. This compact profile is pending; the current schema retains full historical rows and index versions.

The application/API/worker need hosting in addition to Supabase. Prefer an already available always-on machine if resources permit; this can host an isolated website service without integrating with the scraper. Otherwise select hosting with explicit free-plan operational limits. No paid hosting subscription is authorized by these decisions.

## Account and result access

Required live flow: onboarding -> save pending profile/shortlist -> send passwordless confirmation email -> verify account ownership -> show up to three complete employer previews. Preserve the pending browser session proof; matching email alone must never grant access to arbitrary sessions.

The live code now enforces verified, owner-associated accounts before revealing previews, counts, results or unlock access. A check-email/resend screen and validated callback routing are implemented and tested. Explicit local demo mode retains anonymous previews. Real SMTP delivery and the production redirect allowlist still need configuration and verification.

Retain a working explicitly simulated unlock for the full saved shortlist. Do not add payment processing or collect payment details now.

## Inputs needed next

- Supabase Free credentials are supplied and the dedicated database is connected; no further database credentials are currently needed.
- No embedding API key is required for the default local model. Optional cloud extraction/embeddings require their own credentials only if enabled.
- Custom SMTP provider configuration and verified sender/domain for public confirmation emails. Supabase's default sender is restricted to project-team addresses.
- Intended website URL/domain and an available application hosting account or machine.
- Operator name and privacy contact before public use.

No production ledger, scraper credentials, Stripe credentials or new paid database plan is required.

## Next work

1. Verify real email delivery and callback configuration; the server gate and delivery/retry UI are implemented.
2. Continue the compact storage profile. No-route archives and import screening are implemented; broader history/index retention still needs measurement.
3. The supplied CSV is imported and 201 no-route employers are archived, leaving 7,309. Validate identity, authorization, useful channels and professionally attributable evidence for a starter pool.
4. Generate real embeddings for qualified documents, publish the index, and test real searches with clear abstention where evidence is insufficient.
5. Configure email, hosting, retention/refresh schedules and backups; run a small controlled pilot and measure costs and relevance.

Human relevance evaluation and full-catalogue load testing remain uncompleted. No promise of sponsored vacancies or hiring probability is introduced.

## Sources checked

- [Supabase plans](https://supabase.com/pricing)
- [Supabase SMTP requirements](https://supabase.com/docs/guides/auth/auth-smtp)
- [OpenAI embedding pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small)

Detailed user setup instructions: [email](docs/EMAIL_SETUP.md). Cleanup counts and safeguards: [data](docs/DATA_CLEANUP.md).

## Current runtime update

The local site now uses Supabase and its first published 39-employer real search pool (42 facet embeddings). Verification before preview remains enabled. The user reports saving local callback URL settings and Gmail SMTP. Real delivery/callback still require a user sign-in test. Broader catalogue publication, occupation coverage and human quality gates remain incomplete. Details: [real pilot](docs/REAL_MATCHING_PILOT.md).

## 16 October catalogue expansion and evaluation

Published 276 employers and 283 facet vectors in the live Supabase index, preserving previous versions and private account data. All 7,309 retained employers were assessed; 7,033 remain outside recommendations. The 253-prospect suite and reviewable HTML output are available under data/evaluation/2026-10-16/final. Local k6 completed 154 workflows / four VUs / 20 seconds with 770 checks passing and p95 completion 429 ms; remote cold software probes remained about 11.4 seconds including model startup. Human relevance metrics and full load targets remain unmeasured. See docs/CATALOGUE_EVALUATION.md.
