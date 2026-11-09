# Isolated London pilot

SponsorReach runs on a separate ARM EC2 instance in `eu-west-2`. Existing voice/NIMBSS services are not part of this deployment. This repository contains code and deployment instructions only; credentials, CSVs, candidate data and generated employer/model artifacts stay private.

## Runtime

- Next.js binds to loopback port 3000 behind Caddy HTTPS.
- FastAPI binds to loopback port 8001; the gateway secret is mandatory.
- One matching worker processes match and private interest-cohort jobs only.
- The pinned MiniLM encoder and source-backed onboarding artifacts are bundled offline. No paid embedding key is needed.
- Supabase remains the existing database/auth service. Hosting the application in London does not relocate that database; its current region is Singapore.
- Secrets are retrieved from this application's scoped SSM SecureString parameter. No secrets belong in user data, Git, or command output.
- Public ingress is limited to ports 80/443 after checks. Administration uses SSM, without public SSH. The instance uses standard CPU-credit mode to prevent surplus billing; overload may throttle it.

## Release checks

1. Run backend integration tests against a separate local test database, web type checking and a production web build.
2. Run `package-release.py OUTPUT.tar.gz` locally. It includes only selected application folders and published, non-personal matching artifacts. Keep the tarball out of Git.
3. Upload into the private release bucket, extract to a versioned staging directory, install dependencies and set the private runtime parameter.
4. Run `preflight.py` as the service user on the host. It must confirm encoder output, source-backed suggestions, current index and employer artifact versions before services start.
5. Enable API, worker and web services; verify actual hybrid searches, suggestion calls, memory use, auth ownership and stable results. Build success alone does not establish application readiness.
6. Configure HTTPS and the temporary origin in Supabase's redirect allowlist. Test a real email link with the operator before calling sign-in verified.

Public release additionally needs the final domain and complete operator/privacy information. The temporary site is a test deployment.

## Manual data updates

The scraper is independent. Process each supplied CSV locally, inspect its import/identity/channel report, build the new index and matching/onboarding artifacts locally, then publish approved employer/index changes to Supabase and transfer versioned artifacts to the server. Back up the current publication IDs first. Verify the new source hash and run the same preflight before switching the active model pointer. Roll back index/model pointers together if checks fail.

Do not run scraper, CSV import, employer embeddings, taxonomy downloads or model rebuilding in a web request or the cloud worker. `SPONSORREACH_MANUAL_UPDATES=true` limits claimed job types. Update release manifests when the employer source version changes; do not reuse the initial artifact hash against different employer versions.

## Budget

The advertised t4g.small trial covers up to 750 aggregate compute hours/month through 31 December 2026. Verify the actual bill; it does not cover storage, IPv4, CPU surplus or every other service. Normal compute pricing resumes in January unless AWS changes the offer. The extra $40 credit is pending until the operator completes the activities and AWS awards it. The plan still requires reducing the existing account's spending. Budget notifications are not spending caps.

Never upgrade the account plan, resize the existing server, migrate its databases or create paid extras as part of a routine SponsorReach release.

### Member sign-in and account deletion

- Apply the member-access migration before starting the new web and API release. Keep the Supabase Google and Facebook providers off, keep email confirmations and the existing email OTP templates enabled, and keep the private schemas outside the Data API. Store `SUPABASE_SECRET_KEY` and the existing gateway secret in the private runtime. The database connection must have read access to `auth.users` and `auth.sessions`.
- Google uses the browser Sign in with Google button. Set `GOOGLE_WEB_CLIENT_ID` and register `https://sponsorreach.uk` under **Authorized JavaScript origins**. The button uses a JavaScript callback, so Google needs no redirect URI or client secret for this flow. Set and verify the home page, privacy and terms URLs in Google Auth Platform.
- Set `META_APP_ID` and `META_APP_SECRET` in the private runtime. Register `https://sponsorreach.uk/auth/facebook/callback` under **Valid OAuth Redirect URIs**, `https://sponsorreach.uk/privacy` as the Privacy Policy URL and `https://sponsorreach.uk/data-deletion` as the Data Deletion Instructions URL. Use the dashboard’s required access/review steps before switching the app live. Use separate credentials and exact origins for HTTPS staging. Set `SOCIAL_GOOGLE_ENABLED=true` and `SOCIAL_FACEBOOK_ENABLED=true` independently after each provider passes staging.
- Configure `RESEND_API_KEY`, a verified `SPONSORREACH_DELETION_FROM` sender, and a random `SPONSORREACH_CLOSURE_JOB_SECRET` of at least 32 characters. Install `deploy/install-account-closure-timer.sh` on the service host. Check `journalctl -u sponsorreach-account-closure.service` for unresolved receipt, billing or purge errors. Keep payment reconciliation running to resolve ambiguous checkouts.
- The privacy team monitors `privacy@sponsorreach.uk` and Meta developer notifications, including any user-ID exports before they expire. Verify ownership before running `sponsormatch restore-member ACCOUNT_UUID` or `sponsormatch erase-member ACCOUNT_UUID`. Resolve any pending renewal cancellation before restoring the account. An erasure request is queued immediately. Run `sponsormatch erase-facebook-data APP_SCOPED_USER_ID` or `sponsormatch erase-google-data GOOGLE_SUBJECT` for verified provider-only deletion requests. Confirm completion with the requester and handle processor records or backup retention under the privacy procedure. Restrict these operations to authorised operators and keep the privacy case record separate from the account.
