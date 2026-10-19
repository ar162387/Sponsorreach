# Research workspace interaction design

## Decisions

- Signed-in users get a compact split view: their shortlist library stays on the left and selected companies appear on the right. Selection is a local state transition with an addressable `?shortlist=` URL; the separate arrow opens the full page. Stars pin lists; filters search the local shortlist library. The first selected list opens automatically.
- Remove the oversized profile/next-step hero cards. Keep the selected profile's background, specialization, skills and location in a disclosure alongside results. The workspace has independent list/detail scrolling on desktop and stacked, bounded navigation on narrow screens.
- Primary company details remain visible: name, town, concise relevance, available email/phone and website/careers/LinkedIn actions. Reveal expands the full explanation, address, additional contacts and job boards. Bookmarked companies share this compact presentation.
- Opening a saved shortlist issues GETs only. Initial fetches use a result-shaped skeleton; matching progress appears only after a `queued` or `processing` response. Ready sessions return the authorized first page plus its cursor, avoiding the previous duplicate results GET. Current sponsor/channel/evidence checks and server-side preview limits still apply.
- Hold previously visited lists in component-local memory to show them immediately on return while revalidating. Fetches are aborted on selection changes and stale responses cannot replace the selected list. The cache is discarded when leaving/unmounting the workspace or on authentication failure; no employer payloads are saved to browser storage.
- Bookmark and star icons update immediately, show pending state, disable repeat requests, and roll back with an error if saving fails. Next.js route loading boundaries and `useLinkStatus` provide visible feedback for full-page transitions. The header/layout remains shared through normal client navigation.
- Search captions stay visible for at least six seconds, up to fifteen seconds for longer text. Pause, page visibility and reduced-motion behavior remain supported. A retrieval failure never starts an animated search claim.
- Future AI outreach is not implemented here. Real email/telephone/application links remain usable; no fake messaging controls or disabled mock outreach workflows are introduced.

## Evidence informing the design

The operator supplied LinkedIn's list/detail reference. [Apollo's saved-record workspace](https://knowledge.apollo.io/hc/en-us/articles/42619944596237-Manage-Saved-Records-in-Apollo) emphasizes keeping saved companies, filtering and actions in one context. [NN/g's skeleton guidance](https://www.nngroup.com/articles/skeleton-screens/) distinguishes content placeholders from process progress. Implementation follows the installed Next.js 16.4 documentation for route loading, Link and useLinkStatus.

## Verification

- 241 backend tests pass, including per-request authentication verification, no queue writes on saved-session GET, and preview withholding.
- 13 frontend tests pass: nine React integration tests in a virtual DOM cover saved versus processing loaders, single-request initial results, optimistic bookmark rollback, expandable contacts, selection/cancellation, cached revisits, star rollback, history restoration and cache clearing on authorization failure; four caption/personalization tests verify contextual copy and reading duration.
- TypeScript and the production web build pass.
- Desktop browser preview and optimistic bookmark/count updates were inspected using a synthetic local identity and fictional companies. Subsequent automation controls stalled; remaining interaction cases were verified by the component tests instead. Mobile breakpoints and reduced-motion rules are implemented; a real mobile-browser visual check remains a verification limit.
- No production accounts or matching jobs are created for UI tests, and no emails are sent. The model/index/engine are unchanged.

## Deployment

The web build is staged on the existing ARM host under `/opt/sponsorreach/research-ui-20261018`. Only the request-scoped auth/first-page API changes are patched against deployed backend source; the experimental skill graph remains disabled. Runtime, Caddy, worker, employer data and database schema are unchanged. Rollback uses the saved API source and `web.previous` together.

### Publication verified

Published on 18 October 2026 UTC (19 October locally). Web/API/worker/Caddy are active. Public account and form routes return 200 with verified TLS, the private account API rejects guests with 401, and the new workspace CSS and company-card JavaScript assets return 200. The existing worker was left running during the web/API switch. No schema, runtime origin, Caddy configuration, catalogue publication or model flag changed.

## In-workspace refinement — 19 October 2026

Signed-in users now create and refine searches within the workspace detail pane. The same three-step Intake component remains the standalone first-time onboarding form; embedded mode omits its marketing aside and accepts an authorized profile snapshot synchronously. It does not perform a second identity/profile lookup or briefly display a blank refinement form. Optional professional fields and separately stored visa timing are restored, and submitting refinement queues a new revision on the same shortlist. Cancel returns to cached companies without changing the saved profile.

The verified, ownership-checked session response includes its complete professional profile and optional visa context. Neither is returned before the verification gate; identity is not included. The overview continues to exclude visa context. These details remain in component memory rather than a persistent employer/profile browser cache.

The authenticated header contains My account with Sign out only. New search is highlighted inside the workspace. Full-page shortlist controls are removed; authenticated legacy results and onboarding URLs redirect into the workspace. Mobile uses distinct list/detail views, a back control, independently scrolling content and a sticky form action row rather than stacking two cramped panes.

Validation: 242 backend tests; 17 frontend tests including synchronous prefill, exact selected profile, optional context preservation, cancellation, in-place submission, new-search isolation and minimal account navigation. Production builds pass. Browser checks used fictional local fixture data on desktop and a 390px-wide iframe test harness for mobile layout, selection, refinement and scroll reachability. No production user searches, emails or account records were created during testing.
