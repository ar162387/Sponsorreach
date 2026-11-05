# Credit and checkout audit — 5 November 2026

## Live status

The normal hosted subscription checkout is enabled on SponsorReach for every signed-in verified account, including reviewers. It remains in AgentaOS test mode. Clicking Subscribe navigates directly to the hosted card form. The public billing-plans endpoint confirms checkout enabled, US$24.99 monthly and 800 credits. Real-money approval is not enabled. The existing payment reconciliation timer, API, worker and web services are active.

The explicit server setting `BILLING_TEST_CHECKOUT_PUBLIC=true` permits non-admin test checkout; its default remains false. `BILLING_CHECKOUT_ENABLED=true` enables the purchase flow. Neither setting substitutes for live-payment approval.

## Actual sandbox payment

Used the application's checkout creation, account correlation and confirmation code with the real AgentaOS test SDK, hosted card form and an isolated local application database. Paid the existing US$24.99 subscription using test card 4242. Provider confirmation granted exactly 800 credits. Processing that same confirmation again returned `granted=false`; the database still contained one payment and one credit grant, with an available balance of 800. Scheduled cancellation of this synthetic test subscription to avoid further test renewals. No real card or customer payment was used, and this synthetic buyer was not signed in as a real production customer.

## Automated checks

63 backend tests and 37 web/component tests pass (100 total). Local and server production builds and TypeScript checks pass. Credit/API tests use isolated PostgreSQL, synthetic account identities and synthetic result snapshots; these prove transaction and access behavior, not the quality of real employer recommendations. UI tests render the actual React components in a virtual DOM.

| Scenario | Verified behavior |
| --- | --- |
| Verified signup | Grants 10 credits once, including concurrent/replayed signup processing |
| New nonempty first batch | Reserves then charges one credit when delivered |
| Zero results | Releases reservation; no debit |
| Failed/abandoned/expired work | Releases reservation; no unintended charge against a later period |
| Majority repeated across prospects | Free when more than half the delivered batch was already unlocked on that account |
| Threshold | 10 of 20 repeated costs one credit; 11 of 20 repeated is free; small-batch boundaries also checked |
| Fully repeated results | Free; still grants access to the batch |
| Previously locked companies | Count as new, rather than as already delivered |
| Reopen/retry | Does not double-charge or duplicate entitlements |
| Two simultaneous identical deliveries | Account lock ensures only the first delivery is charged |
| Additional repeat batch at zero balance | Opens free; UI does not block it |
| New paid batch at zero balance | Refused without debit; billing link remains available |
| New search at zero balance | Form preserves draft, disables submission and explains how to get credits |
| Balance depleted during submission | Handles 402 gracefully and preserves the draft |
| Credits added | Allowance refreshes without losing the profile |
| Multiple professional prospects | Three profiles share one balance while preserving their separate profile context and saved shortlists |
| Different accounts | Balances and access remain separate, including accounts using the same browser token |
| Submission key reused by another account | Returns a conflict instead of reusing another account's search or producing a database error |
| Signup and subscription activity | Both are visible in the usage view and scoped to the account |
| Paid invoice / monthly allowance | Grants the stored allowance only after verified payment and correlation |
| Duplicate notifications / same cycle | Does not grant another allowance |
| Unpaid / trial / wrong business / wrong account / wrong price / forged webhook | Does not grant credits |
| Refund / dispute / expiry / renewal | Scoped reversals, reservation release, renewal allowance and no rollover covered by isolated tests |
| Disabled and public sandbox checkout | Both states covered; public opt-in permits a signed-in non-admin reviewer |

## Fixes shipped

- Account-wide repeat protection for the initial search batch and additional batches, with a server-provided next-batch price.
- Empty and mostly repeated deliveries preserve credits; free results remain accessible.
- Credit balance refresh after search, result delivery, unlock and payment actions.
- Clear depleted-credit handling, saved drafts and a free-batch action even at zero balance.
- Signup-credit usage visibility.
- Strict account ownership for saved searches and safe handling of cross-account submission keys.
- Public test-card checkout enabled, including direct navigation from Subscribe.

## Remaining verification limits

AgentaOS business verification still has requested changes, so real-money card processing has not been approved or claimed as tested. The production sponsor register was previously found to be dated 12 October 2026, beyond the application's seven-day freshness policy. Positive real-company search results require that source to be refreshed. This release does not relax the freshness rule or fabricate company results. The card and credit tests should not be interpreted as a completed real-customer signup-to-live-employer-result test.

## Deployment

Release: `/opt/sponsorreach/releases/20261105-credit-protection`.
Previous release: `/opt/sponsorreach/releases/20261105-signin-fast`.
Runtime backup is retained privately on the server. No database schema migration or existing balance adjustment was made.
