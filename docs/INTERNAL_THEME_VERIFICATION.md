# Research Atlas internal theme

30 October 2026. Local implementation; not deployed.

## Scope

`web/app/internal-theme.css`, imported after the existing global stylesheet, applies the muted olive/sand/forest/rust palette, serif display typography, ruled editorial layout, original logo and restrained transitions throughout the application. Every application override is conditional on the absence of the landing marker, preserving the existing landing design.

The update covers the shared navigation/footer, all three intake stages, optional fields, suggestions, skills and review, results/feedback/contact routes, previews and unlock dialog, pagination, account sign-in/history, notices, loading/error/empty/verification states, Terms, Privacy, Contact, Refunds and new not-found/error recovery pages. Unavailable result routes keep their disabled behaviour. Decorative locked-result placeholders are skeleton shapes instead of blurred fictional company descriptions. The form-step entrance respects reduced-motion preferences.

No API, database, authentication, matching, payment, credit or access rules were changed. Future paid-launch copy remains unpublished.

## Verification

- Production build and TypeScript pass on the final source.
- Browser interaction checks used intercepted API responses containing explicitly fictional companies and example.invalid addresses, without modifying application/database records. Checked intake progression and retained values, skill selection, submitted profile, results preview, dialog open/close, free unlock, pagination, account history and intercepted sign-in confirmation. No real email or purchase was sent.
- Verification, queued, failed and empty result states checked with fixtures.
- Eight routes checked at 320, 390, 768 and 1440 pixels: intake, account, results, Terms, Privacy, Contact, Refunds and missing page. No horizontal overflow.
- Escape closes the dialog. Reduced-motion mode leaves no active internal animation.
- Final-build automated axe WCAG 2 A/AA checks report zero violations on those eight routes, including fixture results and sign-in. This is an automated check, not a complete accessibility certification.
- Desktop intake/results visually inspected. Landing isolation confirmed: olive landing background and one visible header; internal routes restore sand and shared navigation.
- Error boundary compiles with the installed Next.js 16 retry API; a deliberate runtime failure was not induced.

## Preview and limits

Final local preview: http://127.0.0.1:3030/match . The regular in-app preview uses the configured backend, not Playwright fixtures. A standalone preview can display unavailable account/catalogue states when no backend is configured. Real matching and email delivery were not retested against production. No deployment or gateway application was performed.
