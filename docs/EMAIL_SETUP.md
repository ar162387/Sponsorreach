# SponsorReach passwordless email setup

Checked 14 October 2026. Email delivery is not yet verified. SMTP settings belong in the Supabase dashboard; adding a Resend API key to the application's .env alone does not configure Supabase Auth mail.

## No-domain private pilot: an existing Gmail account

1. Choose a Gmail inbox you own. A dedicated account is useful, but no domain purchase is required. This is a small-pilot option, subject to Google's sending limits and delivery checks.
2. Turn on Google Account → Security → 2-Step Verification.
3. Open https://myaccount.google.com/apppasswords and create an app password named `SponsorReach SMTP`. Some managed accounts or Advanced Protection accounts do not offer this feature. Use the generated app password, not your normal Google password. Enter it directly in Supabase; do not paste it into chat.
4. Open the SponsorReach Supabase project → Authentication → Email/SMTP Settings. Enable custom SMTP and enter:

| Setting | Value |
| --- | --- |
| Sender name | SponsorReach |
| Sender email | The Gmail address you own |
| Host | smtp.gmail.com |
| Port | 465 (SSL) |
| Username | The full Gmail address |
| Password | The generated Google app password |

Save the settings. This configures the provider; successful delivery still needs an end-to-end test.

## Resend when you have a domain

Add a domain you own to Resend, add its required DNS records, and wait for verification. A Resend test sender cannot provide general public sign-in mail. In Supabase custom SMTP use host `smtp.resend.com`, port `465`, username `resend`, password your Resend API key, sender name `SponsorReach`, and a sender address on the verified domain. Do not invent an address on a domain you do not own. A sending address is not automatically a mailbox that receives privacy requests.

## Local callback settings

In Supabase Authentication → URL Configuration:

- Site URL: `http://127.0.0.1:3000`
- Additional Redirect URL: `http://127.0.0.1:3000/auth/callback**`

Use `127.0.0.1` consistently in the browser. The suffix permits the application's `next` query parameter. For public deployment, replace local settings with the actual HTTPS application origin and its callback. Local links only work on the computer running this website, so remote pilot users also need a hosted application.

Keep the magic-link template's confirmation URL in place and disable provider link tracking if enabled. No user password is required by the website.

After setup, test onboarding with your own address, confirm that delivery and callback work in the same browser, check that previews appear only after verification, and verify that another browser cannot access the saved session. Check Supabase Auth logs for SMTP or redirect errors. No real delivery has been tested yet.

Supabase's built-in mail is restricted to project-team addresses and currently two messages per hour. It is insufficient for public signup. Custom SMTP initially has its own Auth rate limit; review Authentication → Rate Limits before a pilot.

## Privacy inbox and operator

Use an existing inbox you control for privacy requests, or create a dedicated inbox and test receiving mail. The same Gmail inbox may be used if you choose. The operator must be the actual person or legal entity running SponsorReach; the brand name alone should not be used to invent a legal operator. Neither value has been selected yet.

## Official references

- https://supabase.com/docs/guides/auth/auth-smtp
- https://supabase.com/docs/guides/auth/redirect-urls
- https://support.google.com/accounts/answer/185833
- https://developers.google.com/workspace/gmail/imap/imap-smtp
- https://resend.com/docs/send-with-supabase-smtp
