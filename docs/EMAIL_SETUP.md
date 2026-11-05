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

## Email OTP setup

The app now requests an email code and verifies it in the browser using Supabase `verifyOtp` with type `email`. Existing accounts, SMTP and saved-shortlist ownership rules stay in place.

Before deploying the app change, open Authentication → Email Templates in the Supabase project:

1. Set both **Magic Link** (returning users) and **Confirm signup** (new users) to the HTML in `supabase/templates/email-otp.html`.
2. Set the subject to `Your SponsorReach sign-in code` for both templates. The body must contain `{{ .Token }}` instead of a confirmation link.
3. Keep the existing SMTP sender and credentials. Review Email OTP expiration and rate limits in Authentication settings. The form accepts 6–10 digit codes and offers resend after 60 seconds; Supabase enforces the actual limits and expiry.

The connected Supabase tools cannot update Auth templates. These hosted template changes and real email delivery have not been verified as part of this code change.

Test both a new address and an existing account: request a code, read the email on a different device, and enter it in the requesting browser. Confirm successful sign-in, saved shortlist association and existing credits. Also test an incorrect code, an expired code, resend and reuse of a consumed code. A different browser must not claim a guest shortlist using email alone.

The old `/auth/callback` route remains for previously issued links. Its existing redirect allowlist may remain configured; the new OTP flow does not use it.

Supabase's built-in mail is restricted to project-team addresses and currently two messages per hour. It is insufficient for public signup. Custom SMTP initially has its own Auth rate limit; review Authentication → Rate Limits before a pilot.

## Privacy inbox and operator

Use an existing inbox you control for privacy requests, or create a dedicated inbox and test receiving mail. The same Gmail inbox may be used if you choose. The operator must be the actual person or legal entity running SponsorReach; the brand name alone should not be used to invent a legal operator. Neither value has been selected yet.

## Official references

- https://supabase.com/docs/guides/auth/auth-smtp
- https://supabase.com/docs/guides/auth/redirect-urls
- https://support.google.com/accounts/answer/185833
- https://developers.google.com/workspace/gmail/imap/imap-smtp
- https://resend.com/docs/send-with-supabase-smtp
