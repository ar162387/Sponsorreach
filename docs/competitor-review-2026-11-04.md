# SponsorReach launch review — 4 November 2026

## Research scope and evidence
Reviewed Irish Talents’ public homepage, how-it-works, company directory, Google employer profile, software developer career guide, location research hub, data methodology, blog index, employer and agency offerings, contact, privacy and terms. Inspected the homepage in a browser. This is a review of relevant page types, not an exhaustive crawl of every employer, job, location and article, nor a review of private account screens. Sitemap retrieval was unsuccessful. No keyword-volume or ranking data was available; keyword conclusions below are inferred from titles, headings, URLs and internal links.

## Copy and search intent
[Homepage](https://irishtalents.com/) connects a search-led introduction to roles, employers, public evidence and audience routes. It repeatedly connects research with a practical next action. Adapt the specificity to UK employer research while retaining SponsorReach’s graduate/professional audience. Do not copy Ireland-specific permit claims or imply SponsorReach provides live job listings.

[Company directory](https://irishtalents.com/companies) and [location hub](https://irishtalents.com/visa-sponsorship/locations) target employer and geographic intent. [Career guide](https://irishtalents.com/careers/software-developer) targets occupation synonyms and links to deeper evidence. Observed keyword families include companies that sponsor visas in Ireland, visa sponsorship by city/industry, software developer Ireland, employment permit history, and candidate permit questions. These are inferred targets, not verified rankings.

SponsorReach’s implemented primary themes: UK visa sponsor companies, UK licensed sponsors, sponsor company research, international graduates, skills-based employer shortlist. Supporting copy explains company relevance, careers pages and available business contacts. Future occupation/location pages should be published only where the underlying dataset supports useful distinct content; do not generate thin doorway pages or unsupported hiring claims.

## Visual presentation
The competitor uses a green brand palette, high-contrast search hero, consistent information cards, entity headings, source periods, counts and links to the next research step. Its [employer profile](https://irishtalents.com/companies/google-ireland-ltd) separates permit evidence, company context and careers action. SponsorReach now retains its own olive/editorial styling and adds three purposeful signal cards: register → relevance → verify and approach. The price card pairs the purchase amount with included features, consumption, expiry and cancellation. Existing background → company relevance → shortlist flow stays intact. No fabricated employer results, statistics or testimonials were added.

## Legal lessons and tailored changes
[Terms](https://irishtalents.com/terms) distinguish research from recruitment and immigration advice, set data limitations and explicitly reject guaranteed outcomes. SponsorReach’s terms and new disclaimer now explain what the subscription buys, employer independence, no government affiliation, source limitations and no guarantee of employment, sponsorship or visa approval.

[Privacy](https://irishtalents.com/privacy) inventories product-specific data, processors, rights and transfers. SponsorReach’s notice instead covers its actual profile, shortlist, support, billing and professional contact handling. It identifies Supabase and UK application hosting with the documented Singapore database location. Do not copy the competitor’s PostHog, Stripe, agency-sharing or CV workflows into this product. Its disclosed pre-consent analytics behaviour is not a recommended compliance pattern.

[How it works](https://irishtalents.com/how-it-works) describes free candidate access, while its terms leave room for paid features. SponsorReach must not borrow the free positioning: its single offer is £24.99 per month for the existing 800-credit allowance. Existing first-payment 14-day voluntary refund provisions are preserved, with statutory rights separate and a cancellation request route added.

## Implementation and verification
Updated landing copy, evidence cards, pricing, FAQs, footer links, terms, privacy, contact, payments/refunds and billing wording. Added data methodology and disclaimer pages, sitemap, robots rules and home canonical metadata. Added a purchase guard that accepts only a matching GBP 2499/month, 800-credit catalogue entry; archived subscriptions remain available for reconciliation. The legacy free-unlock dialog now directs users to billing.

Type checking and production build passed. Browser checks at 1440px and 390px found no horizontal overflow and confirmed pricing/anchor targets. Privacy, terms, refunds, contact, methodology, disclaimer, sitemap and robots routes returned HTTP 200. This does not verify live payment or authenticated research delivery.

## Unresolved launch requirements
1. Connected AgentaOS status is TEST, unverified, no payout account. This may differ from another provider connection; no live approval is established here.
2. Existing provider product is $19.99/month (USDC), not £24.99. Attempt to create GBP 24.99/month returned “Bad Request”; no retry or alternative currency was substituted. Follow-up investigation confirmed the official product CLI documentation accepts only EUR or USD (https://docs.agentaos.ai/cli/products). A GBP 24.99 product cannot be configured through the current interface. Await the operator’s choice: retain GBP with a compatible provider, or explicitly approve a new EUR/USD price before registering a matching immutable plan version and retiring the old public offer. Do not convert £24.99 silently into another billing currency.
3. User supplied operator “Sponsorreach”, location “Romford, UK”, info@sponsorreach.uk and privacy@sponsorreach.uk. Full postal business address remains withheld. See [GOV.UK seller disclosures](https://www.gov.uk/online-and-distance-selling-for-businesses) and [online selling requirements](https://www.gov.uk/online-and-distance-selling-for-businesses/online-selling). Resolve a suitable publishable business address and verify legal entity/trading identity.
4. Finalise processor contracts, transfer safeguards and specific financial/support retention periods against actual operator obligations. Policy text alone does not establish these arrangements.
5. Current public application-closure banner and unauthenticated matching gate remain enabled. Decide/open onboarding only after billing and operational readiness are verified. Ensure the backend credit enforcement configuration matches the advertised paid service.
6. Verify checkout total/tax presentation, durable purchase confirmation, receipt, cancellation, first-payment refund, recurring renewal and paid-credit delivery end to end before deployment. No change in this task guarantees AgentaOS approval.
7. These changes are local and have not been deployed to sponsorreach.uk.

## AgentaOS follow-up — 4 November 2026

Rechecked MCP account and product state: still test, verification unsubmitted, only the original 19.99 USDC product. No duplicate product was created. Requested the free Revenue & Pricing Audit with explicit disclosure that new site content is staged locally, the target price is GBP and the current product is USD. Audit is being written; it is not business verification or an approval.

Retrieved the verification declarations. Submission requires the merchant’s own confirmation of each of the five statements, full legal identity and street address (plus registration number for a registered business). The provided trading name and city alone do not satisfy the fields. No declaration was accepted and no verification was submitted on the merchant’s behalf. AgentaOS lists data scraping among unsupported products; actual employer-research/data presentation must be described accurately during review. Audit request asks for a suitability assessment, but an audit response does not override the prohibited-product rules.

## Approved USD offer — 4 November 2026

Operator chose to remain with AgentaOS and use USD. Applied the existing numeric amount as US$24.99/month. Created test product `5add1d62-3893-4f8d-bab6-8fe3e82eba5b`; the provider returns the underlying currency as USDC, consistent with the prior USD product. Application price remains denominated in USD. Updated public copy, server price checks and plan registration to USD 2499/month with 800 credits. New plan registration archives prior active catalogue entries in the same environment without changing historical snapshots.

User describes the offer as employer research for PSW/immigrant professionals seeking companies in their niche; no promised job or sponsorship outcome. Removed “visa sponsors” from headline/metadata and the visa-expiry marketing line. No invented 1,500-user counter or random growth was added. Verification declaration concerning usage claims must reflect this truthful implementation.

Cyberblitz was supplied as the registered business, with a Lahore address and a personal legal name. Exact registered company name, registration number, country of registration and confirmation of registered address remain requested; no business verification has been submitted. Public operator fallback is Cyberblitz (operating SponsorReach), with Lahore, Pakistan as the location. Existing deployment environment overrides must be corrected during release. The supplied private street address has not been committed to source or published pending confirmation of the registered business details.

AWS deployment credentials are expired; AWS CLI 2.36.11 supports the required sign-in. Requested confirmation to open AWS sign-in under the signing-in-to-aws skill. No deployment or live-payment approval has been claimed.

## Deployment — 4 November 2026

AWS sign-in completed with operator approval. Staged the web source release on the existing isolated SponsorReach server, verified archive hash, installed pinned dependencies and passed the production build. Staged smoke checks returned HTTP 200 for legal/data/discovery routes. Deployed the web update with previous web and runtime copies retained for rollback; web and API health checks passed.

Updated the secure runtime configuration from the signed-in desktop account: USD product ID, Cyberblitz trading identity, Lahore/Pakistan location, and public support/privacy emails. No private street address or registration number was published. BILLING_MODE=test, BILLING_CHECKOUT_ENABLED=false, BILLING_LIVE_APPROVED=false; credit enforcement enabled to prevent the prior free-full-results behaviour. Public onboarding closure remains in place. These are published site improvements, not a live-payment launch.

The server role correctly denied an attempted SSM configuration write. The task's failed-command error output contained private runtime settings; its stdout/stderr were scrubbed on the host, and the successful update used a protected temporary input file via desktop credentials. No server-role permission expansion was made.

## Signup credits and design revision — 4 November 2026

Published the requested landing revision. Both CTAs say Start for free. Removed the three-company preview assurance, visible motion control and thread link. Hero corner labels now match at 12px on desktop/tablet and 11px on mobile. Added a skills-to-company illustration. Removed the selected pricing paragraphs and additional-tier phrase. Removed em dashes, semicolons and colons from authored visible copy while preserving source-code punctuation, URLs and HTML entities.

Added a private one-time signup credit grant with 10 credits, separate from paid periods. Confirmed email signup triggers the grant and verified API access repairs existing eligible accounts idempotently. Replays cannot reset the balance. Searches and new result batches reserve/consume credits; empty or failed work releases reservations. Exhausted accounts receive a payment-required response. Signup credits have no scheduled expiry and are not refreshed on subscription renewal. Paid subscriptions remain US$24.99/month for 800 credits. No fabricated subscription/payment records are created for free members.

Supabase public signup was disabled. Enabled signup via the authenticated project dashboard with email confirmation still on and anonymous sign-in still off. The app now accepts new email accounts and directs Start for free to the account signup/sign-in screen. Email delivery itself was not tested by sending messages to a real user.

The additive migration was applied to the actual application database and verified with rolled-back probes. The function is not executable by anon/authenticated API roles. Local database suite passed 26 tests, including concurrent grants, last-credit reservations, empty-result release, nonempty result delivery, signup trigger replay and continuation using paid allowance. Server build and desktop/tablet/mobile browser checks passed. Public legal/data pages contain none of the prohibited punctuation, and all four corner labels have matching computed sizes.

Deployed web, matching API and worker source as signup-v3 with the prior web/backend/runtime retained for rollback. Checkout remains disabled while AgentaOS verification is pending. User-supplied FBR documents supersede the earlier operator identity/location. They identify an individual trading as CYBERBLITZ, with a Rawalpindi address. No document, national identifier, tax reference or private street address was committed or published. Verification submission remains subject to the final user-count/review declaration confirmation because the earlier response requested invented metrics. No such metrics were implemented.

## Approach section consolidation

Removed the older three-step research diagram beneath the newer two-card illustration. The newer design now incorporates degree/skills context, company relevance reasoning, and websites/careers pages/published business contacts. A focused shortlist is described once within this section. Local desktop/mobile checks confirm one illustration, no old diagram and no horizontal overflow. Production build passed.

## Career goal card

Added a final goal card to the same approach flow, following background and company research. Copy reads “Your next career chapter” and “Work toward a sponsored role that fits your skills and ambitions.” It presents an intended goal without guaranteeing an employment outcome. Removed the illustration/employer-outcomes note beneath the flow. Local desktop/tablet/mobile checks passed with one goal card, no old diagram and no horizontal overflow. Production build passed.
