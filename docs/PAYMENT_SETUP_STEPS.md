# Where to put payment settings

## Local setup — do this first

1. Open https://app.agentaos.ai and select **Test**. Go to **Settings → Developers → API Keys** and create a test application secret key.
2. Open `/Users/syedshahabdurrehman/Code/hermes-agent/scraper/sponsormatch/.env` in your editor. This is the application's existing private environment file. Do not replace its database/auth settings. Add or update the keys below, one per line. Replace the example values; never paste the actual secrets into chat or `.env.example`.

```dotenv
AGENTAOS_API_KEY=YOUR_TEST_APPLICATION_SECRET
AGENTAOS_TEST_PRODUCT_ID=ff02e1f3-2a13-4eb9-ab18-0440e03527e3
AGENTAOS_BUSINESS_ID=b460db5b-7fdb-49ff-a81c-cc15f343e90c
AGENTAOS_RETURN_ORIGIN=https://sponsorreach.uk
BILLING_MODE=off
SPONSORREACH_ADMIN_USER_IDS=YOUR_VERIFIED_SUPABASE_USER_UUID
SPONSORMATCH_SUPPORT_EMAIL=YOUR_MONITORED_SUPPORT_EMAIL
SPONSORMATCH_PRIVACY_EMAIL=YOUR_MONITORED_PRIVACY_EMAIL
SPONSORMATCH_CONTROLLER_NAME=YOUR_LEGAL_OPERATOR_NAME
SPONSORMATCH_OPERATOR_ADDRESS=YOUR_BUSINESS_ADDRESS
SPONSORMATCH_OPERATOR_JURISDICTION=YOUR_COUNTRY_OR_JURISDICTION
SPONSORMATCH_OPERATOR_REGISTRATION=YOUR_REGISTRATION_NUMBER_IF_APPLICABLE
```

3. Find the administrator UUID in the existing Supabase project: **Authentication → Users → your verified account → User UID**. Use the UUID, not your email. Only one administrator is permitted; multiple UUIDs deny access. Missing/malformed IDs deny all admin access. Never use a service-role key as a user ID.
4. Keep `BILLING_MODE=off`. This is not a payment activation instruction: the infrastructure is implemented, but completed provider acceptance tests and launch requirements remain outstanding.
5. Tell the agent that the test key is saved. Do not send its value. The agent can check presence without printing it. The application runner (`python3 sponsormatch/scripts/dev.py` from the scraper workspace) loads this file for web/API/worker. A standalone `npm start` does not automatically load the parent environment file.

## Webhook secret — deployed endpoint, sales remain disabled

In AgentaOS Test mode, use **Settings → Developers → Webhooks**. The endpoint is `https://sponsorreach.uk/api/payments/agentaos/webhook`. Register it only after the deployment health check passes. Without the signing secret it intentionally refuses delivery. Put the revealed signing secret in the same private `.env` as `AGENTAOS_WEBHOOK_SECRET=YOUR_SIGNING_SECRET`. A localhost HTTP preview is not a public webhook endpoint.

## Production — separate from local configuration

The London deployment reads this application's JSON **SecureString** parameter at **AWS Systems Manager → Parameter Store → eu-west-2 → /sponsorreach/london/runtime**. Preserve every existing JSON field and add the equivalent keys there, using the appropriate production credentials only when the verified release is ready. Never replace the JSON with a dotenv block. Do not paste secrets into tickets, chat, Git, screenshots or terminal commands. The agent will handle restarting services and checking the release after configuration. Updating the local `.env` does not change production.

## What is available now

`/admin` provides backend-authorised payment/refund database records and account support conversations, including audited replies and close/reopen. Provider synchronisation and refund requests are connected server-side; a pending request is not a completed refund. `/account/support` is the customer conversation page; it does not send email notifications. `/account/billing` is the credit/usage dashboard. The matching additive migrations have now been applied to the configured SponsorReach database. The local connected administrator preview is http://127.0.0.1:3042/admin; live sales remain disabled.


## Selected administrator: email and password, without email codes

The only requested administrator is **accessgpt69@gmail.com**. Local `SPONSORREACH_ADMIN_EMAIL` is set to this address. Keep the UUID allowlist restricted to this one account.

In your Supabase project, open **Authentication → Users**. If the account does not exist, choose **Add user → Create new user**, enter that email and a strong password, and enable **Auto Confirm User**. This confirms that manually provisioned account without sending it a verification email; do not disable confirmation for ordinary customers. Do not send the password in chat.

Copy that user's **User UID**, then set `SPONSORREACH_ADMIN_USER_IDS=THE_COPIED_UUID` in the private local `.env`. If the account already exists, use its existing UUID and its password; do not create a duplicate. Password reset/setting for an existing account should be done through the project's supported Auth administration, never by directly editing password hashes.

The /admin page now supports email/password sign-in. Both the selected email and the server UUID allowlist are checked; the backend independently enforces administrator UUID authorization. No emailed code or sign-in link is requested by this route. Initial manual provisioning must be completed before it can work.

The supplied AgentaOS test key has been stored in the private local `.env` with owner-only file permissions; it has not been written to documentation or source control. Billing remains off.


## Remaining values you supply privately

The test API key, test webhook signing secret, test product, business ID, private service secrets and single administrator identifiers have already been configured. Do not paste them again.

1. Already registered by the owner: AgentaOS **Test → Settings → Developers → Webhooks** for `https://sponsorreach.uk/api/payments/agentaos/webhook`, its signing secret has been saved as `AGENTAOS_WEBHOOK_SECRET` in the private local `.env` and encrypted AWS parameter. The agent handles service refresh.
2. Operator and contact emails are saved. Supply the full business contact address; “Romford, UK” is a town/country, not a complete contact address. Keep any further details in the same private `.env` and production JSON.
3. Complete merchant verification and payout setup in AgentaOS. Do not turn on live mode yet. The agent must verify actual renewal and completed refund and launch requirements first.

Changing these files does not itself restart the deployed service. Tell the agent “settings saved” without sending secrets; it will refresh runtime and verify them.
