# Payment infrastructure status — 1 November 2026

Application implementation is complete for controlled provider testing. Real-money sales remain disabled. A real hosted test payment, verified credit grant, receipt, cancellation and refund-request submission have completed. Real monthly renewal and final refund approval remain unverified; this is not a claim of live-payment readiness.

## Implemented

- Account-bound hosted checkout with persisted intents, provider idempotency, server-selected immutable plan versions and test/live separation.
- Verified raw signed webhooks, durable event inbox, provider payment/invoice/business/product checks, replay-safe grants and five-minute reconciliation.
- Monthly USD 19.99 / 800-credit plan; configurable future monthly plans share the same internal service credit unit. No transfer, redemption or cash balance.
- Transactional reservations, nonempty-delivery settlement, explicit 20-company batch unlocks, immutable ledger, expiry/refund handling, account locks and stable saved ranking positions.
- Free first account preview, legacy unlocked access, persistent signed-in research, revision-aware workers and unpaid-unlock bypass protection.
- Revised paid searches create a separate saved shortlist, require cost acknowledgement and retain old entitlements. Stars, bookmarks, account workspace and personalised loading states from the live release are preserved.
- Customer billing/UTC usage chart and table, history, owned PDF receipts, period-end cancellation, first-payment refund requests and support conversations.
- Single-account password administrator; audited support/refund controls and provider sync. Refunds are provider requests: requested does not mean money returned. Pending interrupted submissions retry during reconciliation; confirmed returns revoke only unused credits. Provider declines can be recorded by the administrator with an audit note when the provider supplies its decision externally.
- Configuration-driven pricing, Terms and refund policy; public free-access copy stays accurate while billing is off. AgentaOS ownership badge added to both footers.

## Verification

- Full backend suite: 243 passed against a fresh disposable PostgreSQL database after the compatibility merge.
- Four paid API access tests pass, including the added separate-refresh/one-charge/bookmark-access regression.
- 19 provider adapter tests pass and cover paid/unpaid invoice verification, wrong ownership/business/price/environment, archived plans, trial refusal, refunds, interrupted refund recovery and real SDK raw-signature tampering.
- Next.js production build and TypeScript pass. Next.js updated to 16.4.3; production dependency audit reported zero vulnerabilities.
- Actual AgentaOS test checkout completed after the owner approved submission. The API verified a paid USD 19.99 invoice and its confirmed transaction. Exactly one 800-credit grant was recorded in the isolated acceptance database; replay granted nothing.
- Real provider response handling was corrected for lowercase subscription fiat currency, absent checkout invoice fields and transaction references to internal checkout UUIDs. Invoice and transaction ownership are verified together. A regression prevents substituting an unrelated transaction.
- Owned provider PDF receipt downloaded successfully (9,420 bytes, valid PDF header). Period-end cancellation was confirmed. The provider refund request is `requested`; money return is not confirmed and credits correctly remain at 800. A completed refund and actual monthly renewal remain external acceptance work.
- Test webhook signing secret saved privately locally and in the existing encrypted AWS configuration. No secret is recorded in source or documentation.
- The original production release also failed its matching smoke with zero results. Investigation confirmed the active official register is 12 October 2026, outside the existing seven-day eligibility window on 1 November. Eligibility is unchanged. The deployment smoke now explicitly verifies zero results and disabled sales when the register is stale; live checkout preparation refuses stale-source launches.


## Live activation dependencies

Merchant verification/payout readiness and legal operator/address/jurisdiction/support details remain unverified. The owner supplied Muhamad Maaz, Romford UK, info@sponsorreach.uk and privacy@sponsorreach.uk. The full business contact address is still missing. Complete actual renewal/final-refund scenarios and refresh the official register and the existing paid-service classification assessment before enabling live sales. No business identity was invented.

See PAYMENT_SETUP_STEPS.md for exact private settings locations and PAYMENTS_OPERATIONS.md for plan registration, reconciliation and rollback.

## Deployed release

Release `/opt/sponsorreach/releases/20261101-payments-v4` is running on the verified existing London instance. Web/API/worker and the five-minute reconciliation timer are active. One manually triggered reconciliation run completed successfully. HTTPS checks confirm public pages and contacts, the badge, checkout disabled, private account data denied to signed-out requests and the internal bridge excluded from the browser proxy. Invalid webhook signature returned 400; a correctly signed informational test delivery returned 202 and was durably processed. This was an integration check generated by the deployment, not a claim that the provider's own retry log was inspected. Failed synthetic deployment fixtures were cleaned up.

The local isolated acceptance preview remains on http://127.0.0.1:3042/admin, using the chosen password login. Its database holds the real provider test transaction and refund request; production research/customer records were not copied into it. Authenticated customer screens across every requested mobile width still need owner-assisted browser acceptance; signed-out admin access and production API ownership checks have been verified.
