# Future product and launch specification

Documentation handoff only. This package adds no runtime API, database migration, payment product or deployed page.

## Commercial rules

| Action | Required behaviour |
| --- | --- |
| Pack | One payment of 19.99 buys 800 credits; no renewal/top-up |
| Currency | Test GBP denomination first if supported; otherwise USD throughout. Internal amount is 1999 minor units; AgentaOS decimal amount is 19.99. Resolve tax presentation consistently |
| Free preview | One initial nonempty search per verified account, up to three companies; failure/empty attempts preserve allowance |
| Paid first batch | Explicitly unlock positions 1–20 for 1 credit, including the free preview. Purchase does not auto-spend |
| Revised/new search | Explicit submission costs 1 credit when its first nonempty batch is durably available. Editing alone costs nothing |
| More results | Each newly unlocked batch of up to 20 costs 1 credit, including a partial nonempty final batch. No paid prefetch |
| Revisit | Refresh, back, reopening unlocked batches and retries are free. Explicitly running a new search is distinct from reopening |
| Failure/empty | No final debit for validation errors, failed work or empty results/batches; release reservations |
| Zero balance | Blocks new paid work; unlocked results remain accessible |
| Expiry | No scheduled credit/inactivity expiry. Authentication sessions may expire without deleting entitlements |
| Saved results | Persist while the account exists, subject to deletion, correction and withdrawal |
| Refund | Full voluntary refund within 14 days, including after usage; remove only unspent credits from that pack, no debt; preserve unlocked results |
| Closure | Resolve refund rights before account deletion; refund proportional unused paid-credit value on permanent service closure |

Track purchase lots and consume oldest credits first for auditable refunds. Refunds must not remove another pack's credits. Financial records follow approved lawful retention periods.

## Product changes needed later

- Private account-owned purchase, credit-ledger, reservation and batch-unlock records; immutable deltas/references and idempotency keys. Server-authoritative balances; deny direct browser writes.
- Verified-account ownership for spending and free-preview assignment. Browser ownership tokens alone cannot spend account balances. Prevent allowance reset across devices/sign-ins.
- Stable saved ranking and batch identities. At most one debit per account/result-set/batch. Evidence withdrawals must not shift locked companies into unlocked slots without authorisation checks.
- Atomic credit reservations before expensive work; final debit with durable nonempty delivery/unlock, release on failure/empty results and recovery for abandoned reservations. Never hold database transactions across external calls.
- Authenticated balance/history reads and explicit search/unlock actions. Return cost, balance and existing entitlements; validate bounded cursors and prevent direct-pagination bypass. Withhold locked company details.
- Server checkout for an account-bound 800-credit product. Persist expected product/currency/environment/account. Verify raw signed webhooks and payment state, grant credits once, and never trust a redirect as proof.
- Replace the production unpaid-unlock bypass during the later paid release, including backend access. Keep fictional fixtures isolated and non-chargeable.
- Separate temporary session expiry from account research persistence. Update ownership queries and purge/deletion jobs together; preserve existing account-owned research without inventing paid balances. Anonymous abandoned sessions may retain bounded expiry.
- Working correction/removal, refund and deletion flows. Employee sections appear only with appropriately sourced supported records; company routes remain when those records are absent.

Exact route names and migration implementation belong to the later product work; these behavioural requirements apply regardless of naming. No current API changes in this document release.

## Copy and policy rollout

Apply COPY.md across landing, intake, results, account, metadata and artwork. Exclude the disallowed public terms “demo”, “scraping” and “visa” from visible wording, metadata and alt text. Preserve truthful fixture labels until removed from public flows. Historical internal field names need not change for a copy rule.

Remove deadline pressure and the founder anecdote. Use a real rights-appropriate screenshot or omit it. Resolve operator details and all tokens. Do not advertise paid access while sales remain paused or checkout simulated. Publish copy, entitlements, policies and payments as a coordinated later release.

## Acceptance scenarios

| Scenario | Expected result |
| --- | --- |
| Two-company free preview | Both free; allowance consumed after success only |
| Empty/failed preview | Allowance preserved; no balance change |
| Paid batch after preview | Explicit 1-credit debit for up to 20 total, including previews |
| 45 companies | First 20, next 20 and final 5 each cost 1; charges shown beforehand |
| Revised form | New nonempty search costs 1; prior results remain accessible |
| Refresh/back/reopen/retry/two tabs | No duplicate batch debit |
| One credit, concurrent new requests | At most one succeeds; no negative balance |
| Crash/provider/network failure | Recoverable reservation; no duplicate or stranded final charge |
| Empty/out-of-range/withdrawn batch | No debit or locked-detail leak |
| Another user's search | Denied without charging either account |
| Forged redirect/wrong product/currency/test-live mismatch | No purchased credits granted |
| Webhook replay/return race | One grant only |
| Refund after use across multiple packs | Full qualifying refund; only that pack's unspent balance removed; no debt |
| Zero credits | Previously unlocked results still readable |
| 30 days pass | Account results/credits survive; anonymous expiry still bounded |
| Contact/evidence removed | Suppressed in new and saved views; unlocked refresh free |
| Deletion/closure | Explain loss, resolve refund rights and enforce documented retention |
| Mobile pricing | Currency, charges, support and refunds readable before purchase |

## Release gates

1. Obtain a specific work-finding classification assessment of the actual paid offer; no disclaimer is legal clearance.
2. Supply actual operator/address/jurisdiction/registration and monitored contact routes; align gateway application, Terms and checkout.
3. Confirm source/reuse rights, named-contact lawful basis/notices/objections, provider/transfers, retention and cookies. Do not deny legacy collection until removed.
4. Resolve service/content classification, consent, tax display, provider seller role and enforceable consumer terms. Implement the 14-day refund promise.
5. Verify dedicated test payments, concurrency, delivery reconciliation, persistence and deletion jobs against the scenarios above.
6. Scan public copy for forbidden words and unresolved tokens; review links, real evidence, mobile layout and consistent currency/price.
7. Record build, product ID/currency, policy versions, dated checks and rollback owner. Monitor duplicate/missing debits, payment-credit reconciliation, reservations, refunds, complaints and withdrawal propagation.

Keep sales disabled if a gate is unresolved. Rollback must preserve balances, financial history and granted access. A future gateway application must disclose the actual research/credits/contact model; approval is not assumed.
