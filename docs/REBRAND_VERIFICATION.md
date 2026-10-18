# SponsorReach UK rebrand verification

Verified locally on 13 October 2026. This verifies the rebrand and frontend journey; it does not establish production catalogue coverage, sponsorship success or readiness to take real payments.

## Checks completed

| Check | Result |
| --- | --- |
| TypeScript (`npm run typecheck -- --incremental false`) | Passed |
| Next.js production build | Passed, including new PNG icon routes |
| Real local profile normalisation → onboarding submission → worker matching | Passed using an explicitly fictional graduate profile |
| Three free company previews → demo unlock | Passed; the same five saved companies were revealed, with no charge |
| Company save feedback and account shortlist history | Passed |
| Dialog initial focus, Tab navigation, Escape close and focus restoration | Passed |
| Keyboard skip link | Passed; focus moves to `main` |
| Homepage text contrast | No failures in the inspected rendered text; two small teal-on-pale labels were corrected |
| Account, onboarding and result-card text contrast | No failures in the inspected rendered text |
| Homepage widths 320, 390 and 1280 px | No horizontal overflow |
| Onboarding, results, account and policies at 390/1280 px | Inspected; no horizontal overflow |
| Source rules for reduced motion | Inspected: animations and transitions are disabled; smooth scrolling falls back to auto |
| Public copy and metadata old-brand audit | No SponsorMatch, “Find my employers” or “next chapter” copy in web app/components/lib |
| Transparent logo alpha and clean light/dark previews | Passed; white derivatives preserve each source alpha byte |
| Favicons | Inspected at actual 16/32/64 px sizes |
| Social graphic | Exact brand/message inspected; exported at 1200×630 px |
| Git whitespace check | Passed |

The contrast inspection uses rendered computed text/background colours; it is not a complete WCAG audit. Responsive visual checks and keyboard checks complement it. Reduced-motion CSS was inspected rather than changing the user's OS preference.

## Isolated UI scenarios

A separate local fixture upstream and frontend on port 3004 exercised states unavailable in the five-company local demo. These fixtures never entered the matching database and were stopped after verification.

- Pagination: 20 cards initially, five appended, then no remaining load-more button.
- Contact mapping: email `mailto:`, phone `tel:`, website, careers, company LinkedIn, LinkedIn jobs and job-board links.
- Verified vacancy: the existing title/URL renders in a separate vacancy section with an application link.
- Empty results: explains insufficient company evidence and suggests useful profile refinements.
- Failed match: shows a new-search action and access to saved shortlists.
- Processing: maps the genuine server stage to sponsorship-specific wording.
- Temporary upstream interruption: retries are bounded, then shows the supplied error and recovery action.

These UI fixtures test presentation and link construction; they do not verify real company contacts, jobs or licences. No external employer links were clicked and no email was sent.

## Boundaries preserved

Routes, API payloads, ranking, evidence gates, browser ownership, auth configuration and server-side withholding remain compatible. The existing legal-controller/privacy-contact configuration is preserved. The unlock is still a demonstration, and fictional sample records remain labelled and non-actionable.

The account page only offers email sign-in when the existing catalogue-status response reports it available. Otherwise it explains browser-only preview access and the existing 30-day session retention.

See `WRITING_GUIDE.md`, `PAGE_COPY_INVENTORY.md`, and `../brand/README.md` for delivery details. Screenshots are under `output/playwright/sponsorreach/` from the scraper workspace root.
