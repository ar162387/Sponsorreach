# sponsorreach.uk domain cutover

Operator requested domain instructions on 18 October 2026. Namecheap BasicDNS is selected. Read-only checks found the apex on Namecheap's forwarding address and `www` pointing to `parkingpage.namecheap.com`. EC2 `i-0964a42fab919398d` in London is running with public IPv4 `13.40.164.65`.

## Verified deployment — 18 October 2026

- Authoritative Namecheap DNS publishes `A @ 13.40.164.65` and `CNAME www sponsorreach.uk`. Google public DNS also resolves the apex. Some local resolvers still have negative cache entries during propagation.
- Caddy serves the apex with a valid public certificate. HTTP redirects to HTTPS; HTTPS `www` redirects to the apex, preserving path and query.
- `APP_ORIGIN=https://sponsorreach.uk` is saved in both SSM SecureString `/sponsorreach/london/runtime` and `/etc/sponsorreach/runtime.json`. Only the web service was restarted. Web, API, worker and Caddy remain active.
- Landing, onboarding and account routes return 200 over validated HTTPS. Social image metadata uses the new origin. A malformed same-origin sign-in request reaches validation (422); a foreign-origin request is rejected (403). No email was sent. Guest account history remains protected.
- The new domain was also opened successfully in the browser and its onboarding form rendered.
- Server rollback copies are private under `/opt/sponsorreach/domain-20261018/`; local runtime backups are ignored under `.local/domain-cutover/`. Never commit these credentials.
- The temporary hostname remains available for transition. Cookies are domain-specific: users may need to sign in again on the new domain. Existing account data is retained.
- **Pending operator step:** update Supabase Site URL and callback allowlist as described below, then verify email delivery and an authenticated return to the new domain. HTTPS does not verify this external setting.
- Matching configuration is unchanged; the experimental skill graph is still disabled. No new AWS resources were created.
- The deployment startup script regenerates Caddy from the app origin. Preserve the current multi-host Caddy configuration when using that script during a future redeployment; otherwise the `www` and temporary-host blocks would be lost.

## Procedure and rollback reference

1. In Namecheap, remove the apex URL Redirect shown in the operator's screenshot. In Advanced DNS, replace conflicting apex forwarding/A records and the `www` parking record with `A @ 13.40.164.65`, `CNAME www sponsorreach.uk`, TTL Automatic. Preserve unrelated DNS, MX and TXT records. Keep BasicDNS; no new hosting/PremiumDNS/SSL purchase is needed.
2. Check authoritative and public A/AAAA/CNAME answers. Remove an incorrect apex/www AAAA only if it points elsewhere and is not intentionally in use. Check CAA if certificate issuance fails. The current IP is automatically assigned and can change on an EC2 stop/start; select a stable-IP policy before relying on the domain long term. Do not silently allocate new billable resources.
3. Back up Caddy configuration and private runtime locally on the server. Add both apex and www to Caddy, serve the app at the apex and redirect www to the apex. Validate before reload. Existing 80/443 ingress and automatic HTTPS should suffice. Obtain and verify the public certificate, HTTP redirect and www redirect before changing the app origin.
4. Update `APP_ORIGIN` to `https://sponsorreach.uk` in both the private SSM runtime parameter and `/etc/sponsorreach/runtime.json`, without printing secrets. An edited runtime file alone can be overwritten by deployment startup scripts. Restart only SponsorReach app services as needed. Check same-origin protection, secure cookies, canonical links and public metadata. Keep a reversible rollback.
5. After HTTPS works, operator sets Supabase Site URL to `https://sponsorreach.uk` and adds `https://sponsorreach.uk/auth/callback**`, retaining local/temporary callbacks during transition. The current magic-link flow appends a return-path query, which the narrow callback pattern accommodates. Server callback validation must continue to constrain return paths. Existing browser cookies are domain-specific; users may need to sign in again. Test actual delivery with the operator, not unsolicited test emails.
6. Verify the landing page, onboarding suggestions, authenticated account/history/refinement and an owned saved shortlist. Do not enable experimental matching as part of the domain change. Sender email/domain verification is separate from HTTPS; preserve the current SMTP setup until a deliberate email migration.

References: [Namecheap DNS records](https://www.namecheap.com/support/knowledgebase/article.aspx/208/32/i-dont-want-to-change-nameservers-are-there-any-other-ways-to-point-my-domain-to-your-servers/), [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https), [Supabase redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).
