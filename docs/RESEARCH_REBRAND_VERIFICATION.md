# Employer-research rebrand — 30 October 2026

Implemented in local website source. Not deployed by this change.

- Landing page now leads with “Find companies worth approaching” and explains company context, relevance and available routes.
- Removed deadline pressure, the founder anecdote, fictional landing-page company card and example price. The replacement feature panel explains the service without posing as a company result.
- Updated navigation, metadata, onboarding, account actions and result-access copy. Removed the optional status/timing intake controls; the existing API payload sends null. Previously collected information remains disclosed in Privacy.
- Current free access is explicit. The 800-credit offer, long-term retention, refund promises and payment activation remain future work in `paid-launch/`.
- Added Contact and Payments/refunds pages and expanded current-use Terms. No legal entity, address, response SLA or unimplemented entitlement was invented. Configured contact information is used only when available.
- Removed stale social image metadata; sharing cards use text until replacement artwork is prepared.

## Verification

Production build and TypeScript passed. Browser inspection at 1440px desktop and 390px mobile confirmed the new landing layout; mobile landing/intake and Terms, Privacy, Contact, Payments/refunds and Account had no horizontal overflow. All five policy/account routes returned 200. Rendered visible copy on inspected pages contained none of the three excluded terms and no unresolved editorial tokens.

The standalone frontend preview had no backend configuration, so account/intake API requests were unavailable. No claim is made that live sign-in, matching, saved results or result unlock was tested end to end during this copy change. The existing server-side access logic and payment behaviour were not modified.

Legal operator identity, jurisdiction, business address, provider/privacy arrangements and monitored support remain public-launch prerequisites. The future legal drafts remain unpublished. Production deployment is not performed by this work.
