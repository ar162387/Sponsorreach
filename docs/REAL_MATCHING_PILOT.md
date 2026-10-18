# First real matching pool — 14 October 2026

The local website at http://127.0.0.1:3000 now uses the supplied Supabase project and requires verified email before results. It is no longer running with `--demo`. The catalogue contains 7,309 CSV employers and no fictional or legacy-workbook employers. The first published search index covers 39 employers; the remaining catalogue has not yet been published for matching.

## Preparation and source handling

Prepared a bounded sample across occupational families using existing CSV business-activity tags, recorded websites, and exact current register name/town linkage. Unique recorded domains and unambiguous identities were required. Read recorded homepages to retain exact activity excerpts; this is an initial bounded evidence pass, not a connection to the scraper or a blanket rescrape.

101 source drafts produced 40 with activity spans, 40 without exact activity spans, 13 without sufficient page identity confirmation, two redirected to a changed hostname, and six were unavailable. These are conservative source-preparation outcomes, not findings that the underlying companies or CSV tags are incorrect. Reviewed the prepared excerpts and excluded AIESEC's teaching-exchange wording from direct teaching-employer evidence.

Published 39 reviewed employers, 45 first-party activity claims and 42 facet documents. No current vacancy or sponsorship-willingness claims were inferred. Contact values present on these pages and recorded website routes were corroborated; other imported contacts retain their earlier unverified state. Source text, review manifest and hashes are retained under `data/pool/2026-10-14`.

The free pinned local MiniLM model generated all 42 embeddings. Index `6716db0a-9aef-4d25-9f9b-3a931a40f7a9` is published in Supabase. Publication is atomic and prior index versions are retained for rollback. No embedding API key or paid model call was used.

## Search checks

| Profile | Real direct matches |
| --- | ---: |
| Software engineer | 4 |
| Accountant | 2 |
| Solicitor | 4 |
| Mechanical engineer | 1 |
| Marketing specialist | 3 |
| Nurse | 2 |
| HR specialist | 0 |
| Quantum lattice researcher | 0 |

These are smoke checks, not reviewer precision measurements. HR abstains because unrelated business activities do not establish an internal HR function. Sparse coverage remains, especially outside these families. Results should return fewer than three cards when evidence is insufficient.

The first remote smoke run had variable latency and did not meet the three-second target. Single reads now avoid unnecessary transaction round trips; taxonomy seeding uses batched operations. Atomic multi-statement updates retain explicit transactions and rollback tests. A formal latency/load benchmark remains outstanding.

## Live access check

Via the actual Next.js gateway and live worker: created a disposable synthetic profile, saved four real software results, confirmed the session reached ready, verified no employer names or result counts were returned before confirmation, results and unlock returned 403, and another browser ownership token returned 404. Removed the disposable profile/session afterwards. Sent zero emails during this check.

Backend suite: 74 passed, including source-span filtering, identity hints, exclusion of vacancy/negative/footer wording and explicit transaction rollback.

## Email test pending

The user reports saving both Supabase URL settings and Gmail custom SMTP. Successful real delivery is not yet verified. Open `/match`, use a software role for this first test, complete onboarding with an inbox you control, and open the confirmation link in the same browser. Copy it into the in-app browser if the email application opens another browser. Three previews and a simulated unlock should then become available for the four-result software shortlist. No payment details or charge are involved.

Before a public launch: expand occupational coverage, complete human relevance evaluation, finish operator/privacy details and hosting, measure capacity and latency, and establish register refresh/retention schedules. Current sponsor authorization expires from recommendation eligibility if the configured snapshot freshness limit is exceeded.
