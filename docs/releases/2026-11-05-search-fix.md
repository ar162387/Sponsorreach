# Search submission and landing page release — 5 November 2026

Released to https://sponsorreach.uk using the existing London server.

## Changes

- New searches omit `accept_credit_cost`, which is accepted only by the strict shortlist-refresh schema. Refreshes retain the field.
- Regression checks validate the actual web request builder against both backend request schemas.
- Homepage headline, removed editorial labels, navigation wording, Instagram, public LinkedIn and business enquiry links match the requested changes.
- Removed the checkout-unavailable notice from the homepage pricing section.

## Verification

- Six search contract/integration tests pass, including a new test account, queued request, result delivery and retry credit accounting in an isolated local database. Authentication and result fixtures are synthetic; this is not a live signup test.
- All 28 existing web tests pass. Type checking and local and server production builds pass.
- Live API rejects the old request with 422 (`accept_credit_cost` is forbidden). The fixed request passes validation and reaches the expected 401 authentication gate when submitted without a signed-in account.
- Browser check confirms the live headline and social links. At 390px viewport width, the page has no horizontal overflow.
- API, worker and web services remained active after release.

## Outstanding findings

A direct production matching check for software development returned zero companies. The active official sponsor snapshot is dated 12 October 2026; it was 23 days old on the server. The ranking policy accepts sponsor snapshots at most seven days old. The request-validation fix does not refresh that dataset or relax the freshness check. Full successful live signup-to-results verification remains outstanding until register data is refreshed and a signed-in test is completed.

## Deployment and rollback

Active release: `/opt/sponsorreach/releases/20261105-search-fix`.
Previous release: `/opt/sponsorreach/releases/20261104-dashboard`.
The release changes only the four web files edited in this chat; other deployed code and data are shared with the previous release. The web service was restarted after switching the application link. The previous release remains available for rollback.

## Source control

SponsorReach application source, assets, tests and documentation are saved on `codex/sponsorreach-search-fix`. Local secrets, runtime data, generated archives and unrelated scraper edits are excluded. The established repository is https://github.com/ar162387/Sponsorreach. The scraper checkout has no remote; changes are published from a separate worktree based on the established repository’s main branch. Files present only in the established repository are preserved.
