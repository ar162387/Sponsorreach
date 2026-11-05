> Current implementation progress: [MONTHLY_BILLING_STATUS.md](MONTHLY_BILLING_STATUS.md). The monthly offer and test product supersede the historical one-time proposal below. Integration remains incomplete.

# AgentaOS preparation for SponsorReach

> The later [paid-launch specification](paid-launch/LAUNCH.md) supersedes this document's original single-shortlist product proposal and undecided price. The selected future offer is 19.99 for 800 account credits. Payment implementation remains deferred; no product has been created.

Prepared on 30 October 2026. Setup only; payment implementation is deferred at the user's request.

## Prepared

- Codex MCP registration: `agentaos`, hosted URL `https://mcp.agentaos.ai/mcp`. Browser OAuth completed successfully during setup. Start a fresh chat to load its account tools.
- Official skill installed locally at `~/.codex/skills/agentaos/SKILL.md`, fetched from https://agentaos.ai/SKILL.md. Start a fresh Codex chat to load newly installed skills and MCP tools.
- Official server SDK: `@agentaos/pay@2.6.0`, pinned in `web/package.json` and its lockfile.
- Local CLI: `agentaos@3.4.3`, pinned as a development dependency. From `sponsormatch/web`, use `npm run agenta -- --help`.
- Inactive server-only variable examples in `.env.example`. No secrets have been added.

The website's demo unlock, checkout UI, access rules, real environment, deployment and database are unchanged. No product, checkout, charge, webhook endpoint or business-verification submission has been created by this setup.

## Agreed integration choices

Public website: https://sponsorreach.uk

Prefer GBP pricing if the provider supports it at activation; otherwise use USD. The current product/checkouts API reference accepts EUR or USD, so USD is the documented fallback. The country/currency page separately describes local-currency card payments; that does not establish support for a GBP-denominated product. Do not pass GBP to the API without confirming support.

The one-time shortlist price is still undecided. The existing example £19 is not an approved USD amount or a currency conversion. Do not create a priced product until the amount is selected.

Start in Test mode. Do not switch the account or website to Live as part of preparation.

## Check or reconnect the account

Codex MCP OAuth completed successfully during this setup. If reconnection is needed:

On the machine running Codex:

```sh
codex mcp get agentaos
codex mcp login agentaos
```

Sign in on the AgentaOS browser page, choose **Test**, and approve. In a fresh Codex chat, the first AgentaOS tool call should be `agenta_status_get` with `{}`. It reports the account's actual status and next step.

The CLI has its own optional browser login, separate from Codex MCP OAuth. Only needed if working through the terminal:

```sh
cd sponsormatch/web
npm run agenta -- login
npm run agenta -- status --json
npm run agenta -- products list --json
```

These commands do not create products or enable payments. Never copy OAuth credentials into the app. The app later needs its own server API key from Developers → API keys.

## Implementation when requested

Use the skill's **Pattern B**: each saved shortlist is protected by ownership and verified email. A shared product buyer link does not carry the required app correlation metadata.

1. Recheck account status and supported product currencies. Select the one-time amount, then create one test product for full access to a saved shortlist. Save its UUID as `AGENTAOS_SHORTLIST_LINK_ID`; the `/pay/...` buyer URL is a different value.
2. Add a test API key to server-only environment storage as `AGENTAOS_API_KEY`. Keep it out of `NEXT_PUBLIC_*` and browser bundles. Live activation is a separate step after required provider verification.
3. Add a private checkout-record table through a new migration. Store checkout ID, shortlist ID, verified account ID, product ID and processing status. Deny direct browser/API-role access. Preserve the saved ranking.
4. Add a server checkout endpoint that checks ownership, verified email, ready status and additional locked results. Use `AgentaOS.checkouts.create({ linkId, buyerEmail, metadata: { customerId, matchId }, successUrl, cancelUrl })`. IDs and price must come from trusted server state. Save before redirecting and reuse pending checkouts where possible.
5. Derive return URLs from the fixed HTTPS origin `https://sponsorreach.uk`, for example `/results/<shortlist-id>`. AgentaOS appends `sessionId` to the success URL. Local HTTP return URLs are unsupported; use an HTTPS preview/tunnel for test callbacks.
6. Add `/api/payments/agentaos/webhook` during implementation. Register its full HTTPS URL in the dashboard and save the signing secret as `AGENTAOS_WEBHOOK_SECRET`. Verify the raw body with `agentaos.webhooks.verify()` and `x-agentaos-signature`. Validate correlation against the stored checkout, then unlock transactionally once per checkout ID. A redirect or browser event is never proof of payment.
7. On return, use `checkouts.retrieve(sessionId)` as a recovery path. Validate ownership, expected product and metadata before granting access. Delayed webhooks, retries, cancellations and expired checkouts need recoverable states.
8. Replace demo checkout UI only during implementation, displaying the real product currency/price and test-mode status. Disable the free demo-unlock bypass for paid shortlists and production. Do not charge for fictional demo employers.
9. Verify a hosted test payment, unpaid/forged returns, other users' checkouts, duplicate webhooks, invalid signatures and unchanged saved ranking. Deployment and Live activation are separate steps.

## Verification and dependency notes

- TypeScript check passed. SDK import, CLI version and pinned lockfile entries verified.
- The CLI reports `authenticated: false`, `reason: not-logged-in` before separate CLI browser login. This says nothing about MCP OAuth, which is a separate connection.
- `npm audit` reports existing Next.js 16.4.0 advisories (patched version reported: 16.4.3), plus a high-severity Zod advisory through the development-only AgentaOS CLI's Zod 3 dependency. The installed CLI currently has no compatible fix reported by npm. No unrelated framework upgrade or forced dependency override was applied. Review these before deployment or exposing the CLI's MCP server.

## Official references

- [Skill](https://agentaos.ai/SKILL.md)
- [Documentation index](https://docs.agentaos.ai/llms.txt)
- [Complete reference](https://docs.agentaos.ai/llms-full.txt)
- [MCP setup](https://docs.agentaos.ai/mcp/setup)
- [Checkout SDK](https://docs.agentaos.ai/sdk/pay-checkouts)
- [Authenticated paywall pattern](https://docs.agentaos.ai/sdk/paywall-for-logged-in-users)
- [Signed webhooks](https://docs.agentaos.ai/sdk/pay-webhooks)
- [Countries and currencies](https://docs.agentaos.ai/mor/supported-countries)
