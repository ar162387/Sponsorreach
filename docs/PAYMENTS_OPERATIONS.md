# SponsorReach payments operations

## Safety switches

Deployment intentionally uses `BILLING_MODE=off`, `BILLING_CHECKOUT_ENABLED=false`, `BILLING_ENFORCE_CREDITS=false`, `BILLING_LIVE_APPROVED=false` with a test provider key. No real-money offer is enabled. Existing membership-only access restrictions are preserved.

For isolated acceptance testing, `scripts/admin-preview.py --test-billing --port 3042 --api-port 8024 --database-url postgresql://localhost:55438/sponsorreach_billing_acceptance` sets test mode in its child processes. Test checkout is restricted to the single administrator. The isolated database contains no copied production customers or financial records.

## Register future plans

Create a separate monthly product in the matching AgentaOS environment, then register its immutable commercial contract using `backend/.venv/bin/python scripts/register-billing-plan.py --help`. Supply the JSON file expected by that command: slug, environment, name, product_id, amount_minor, currency (EUR, 2499 minor units), interval (month), credits (100) and active. Start inactive. Never change price, credits or product on an existing plan record; register a new slug/version. For the EUR cutover, create a €24.99 monthly subscription product and register a fresh slug such as `monthly-eur-v1`. Activate it only after verifying the product and checkout in the matching environment. Existing subscribers retain their stored contract. No self-service upgrades, annual plans or top-ups are offered by this release.

Credit costs are server-controlled in `sm_private.credit_costs`. The shared `Credits.spend_in` primitive supports future feature costs; never pass a browser-provided amount/action straight into it. Every action needs an independently authorised server operation and a stable idempotency reference. Credits belong to a paid-period lot and do not roll over.

## Reconciliation and support

The `sponsorreach-billing-reconcile.timer` systemd timer runs every five minutes. It recovers checkouts/events, confirms paid invoices, updates subscription state, retries interrupted saved refund submissions, expires allowances/reservations and scans provider financial state for refunds/disputes. The dedicated loopback endpoint requires a private bearer secret and is excluded from the general browser proxy.

Review failed reconciliation service runs, pending event attempts, stale reservations, pending refund decisions and mismatches between financial and credit records. A provider request is not a completed refund. Confirmed refunds/chargebacks remove unused affected credits without negative balances or removing saved research. Publicly documented provider transaction state confirms successful refunds; a decline received outside that feed must be recorded through the audited admin control with the actual provider note.

The administrator is restricted to the configured single UUID and email; use /admin with the existing password. Ordinary customers retain verified sign-in. Support conversations are in-app; no automated outbound support email is implemented.

## Deployment and rollback

Build in a separate release folder before changing the running application. Additive migrations retain financial history. Preserve the existing production database, employer catalogue, encoder and published research artifacts. Check preflight, worker smoke, HTTP pages, billing switches and timer after switching.

To pause an already paid installation, set checkout disabled, billing mode off and BILLING_ENFORCE_CREDITS=true: purchases and new credit spending stop while entitled research and billing records remain accessible. Never delete financial tables or reset balances for rollback. If restoring older code that cannot read NULL account expiry, restore the private retention snapshot prepared by the deployment script before restarting it. Do not run anonymous purge logic against signed-in accounts.

## Required external acceptance

A successful hosted test payment, renewal, failed-payment recovery, cancellation and refund must be exercised against AgentaOS test mode. Controlled SDK fixtures and database tests are not substitutes. Complete merchant approval, business identity, support contacts, classification assessment and webhook secret configuration before any live activation. Server live gating deliberately refuses checkout without these settings.


## Current acceptance evidence (1 November)

Actual hosted test payment succeeded. Server verification recorded one USD 19.99 payment and exactly 800 credits; replay added none. An owned PDF receipt downloaded, renewal cancellation was confirmed and the refund request reached provider status requested. Refund execution/approval and a real monthly renewal remain unverified. No documented test-clock/renewal-advance operation was found in the installed SDK, available connector or official full documentation; do not invent a renewal by editing provider/financial records.

The active official register is dated 12 October, outside the existing seven-day freshness rule. Both the original and new release correctly return no current matches. Refresh and republish the catalogue through its normal reviewed pipeline before paid launch; do not extend freshness thresholds to force a passing smoke check. Live checkout preparation and sales availability explicitly enforce current source freshness.
