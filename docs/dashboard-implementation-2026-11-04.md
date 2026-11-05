# SponsorReach dashboards

Persistent member and administrator workspaces use Next.js layouts and client navigation. Public pages retain the marketing shell. Legacy account query links and results links resolve to the new member destinations.

## Data and permissions

- GET /api/account/credit-summary returns available, signup, reserved and subscription state for the verified member.
- GET /api/admin/dashboard/summary and /health expose operational summaries to the configured verified administrator only.
- Paginated /api/admin/dashboard/{members,payments,refunds,credits,reservations,checkouts,events,runs,issues,support} accept offset, q, status, environment, start and end. Page size is 25.
- GET /api/admin/dashboard/members/{uuid} returns a read-only account detail with up to 25 recent shortlists, payments and support requests. No profile documents or authentication secrets are exposed.
- Page and API guards require the configured administrator ID and verified email.

## Reconciliation

Scheduled and manual reconciliation share private run records and a ten-minute exclusive lease. Provider work has a three-minute execution budget checked between provider and persistence operations. Expired leases are recorded as interrupted. Full completion requires a complete transaction scan without errors or pending verification. Partial attempts do not update the successful-sync timestamp. Opening financial views reads stored records. Refund and cancellation actions remain explicit and audited.

## Checks

- Full backend suite against the isolated local database passed with 228 tests passed and 27 skipped.
- Payment adapter suite passed all 22 tests. Production Next.js build and TypeScript checks passed locally and on the AWS staging release.
- Synthetic member and administrator browser checks covered desktop and mobile, persistent navigation, back and reload, draft restoration, member lookup before research, credit refresh, and forbidden administrator APIs.
- Automated WCAG A and AA checks passed on sampled member and administrator screens. Horizontal overflow was checked at 390, 768, 1024 and 1440 pixel widths.
- No synthetic accounts or records were inserted into production for testing. Live payments remain disabled.

## Release

The versioned AWS release is /opt/sponsorreach/releases/20261104-dashboard. The previous version is retained at /opt/sponsorreach/releases/pre-20261101-payments-v3-app. Runtime credentials remain in the existing private runtime file. The additive private migration is compatible with the previous release.

Rollback consists of restoring the /opt/sponsorreach/app symlink to the previous version and restarting the API, worker and web services. Dependencies and published research assets are reused. The release runner explicitly imports backend source from the active version.

Live release checks confirmed all four services active, public member and administrator sign-in pages accessible, and unauthenticated private APIs returning 401. The release was switched atomically after staging checks passed. Previous release files remain available.
