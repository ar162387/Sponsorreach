# Personalization implementation plan — 18 October 2026

## Journeys

Guest: public homepage → structured intake → email confirmation → profile-aware loading → up to three complete previews. Existing server ownership and locked-data withholding remain authoritative.

Returning verified user: personalized homepage/dashboard → saved professional profile, recent named shortlists, resume/refine actions. Header clearly shows signed-in status and offers account access/sign-out. Public marketing remains accessible at /about.

Sign-out: revoke the local Supabase session, clear auth cookies and the browser ownership cookie, remove only SponsorReach professional drafts, and navigate to the public homepage. Do not delete the account or its saved history.

## Loading

Keep the existing animation and actual worker stage. A separate supporting line rotates every second through facts about the submitted roles, specialization, user-selected skills, location and related-career choice. Never fake completed checks, counts, probabilities or vacancies. Stop timers on ready/failed/unmount; pause in hidden tabs; provide pause and reduced-motion behavior. Screen readers announce stage changes rather than every rotating sentence.

## Contracts and privacy

Add an owner-authorized account overview returning first name, professional profile and shortlist summaries only. Add bounded professional loading context to already authorized match-session responses after email verification. Never return visa context, identity email, locked employer names/contacts or access tokens for personalization. No schema migration, extra model calls, new ranking configuration, payments or hosting services are needed.

Use verified server-side Supabase identity, Next.js proxy cookie refresh and private/no-store page/API responses for authenticated content. User metadata may support display only, never permissions. Failures show retry UI rather than silently treating an authenticated user as a guest.

## Verification

Backend tests: anonymous overview rejected; own overview only; different account isolation; expired profiles excluded; session context bounded and free of identity/visa; preview and unlock isolation preserved.

Web tests: guest/authenticated navigation; dashboard/empty/error states; sign-out clears drafts and owner state; personalized loading uses submitted facts with no fake progress; reduced motion/pause; mobile layout. Production build and full backend suite before deploying a reversible London release. Human email-link testing uses the operator's own inbox; automated checks do not send email.

## Reference

LinkedIn public post/transcript inspected. Its video reports Unable to play media in the browser, so visual details have not been verified. The implementation follows the user's written requirements and the current design. Its promotional company-count/vacancy claims are not imported into the application.

## Completed validation

218 backend tests and three personalization unit tests pass; TypeScript and production build pass. A synthetic confirmed account in a local production build exercised the dashboard, role-aware loader, pause/resume and sign-out. HTTP checks confirm account isolation, private caching, cross-origin sign-out rejection and POST-only logout. No real verification email was sent. Live verification follows deployment; matching latency is unchanged.

## London release

Deployed 18 October 2026 to the existing separate London instance. Production build completed; web/API/worker health checks passed. Public HTTPS checks passed for intake, public about page, guest navigation, private caching, anonymous overview rejection and sign-out method/origin protection. Prior web and API copies are retained in `/opt/sponsorreach/personalization-20261018` for rollback. No database migration, model change or processing of scraper data was required. Real-inbox sign-in was not repeated during this release.
