# Personal sponsor workspace

Each saved shortlist owns its search profile. `/match?new=1` starts a clean search; `/match?shortlist=<id>` restores only that owned shortlist's profile. Draft keys are scoped to account and shortlist. Reset clears professional fields, optional context, selected skills, normalization choices and pending suggestion results. It keeps sign-in and, during refinement, the target shortlist.

Refinement and `POST /api/matches/:id/refresh` enqueue a new revision of the same session. Profile changes create an immutable profile row and update the session pointer. Access/unlock, star and URL are preserved. Requests use an idempotency key; concurrent updates return 409. Queue jobs, stage updates, failures and result publication carry the revision so a stale worker cannot replace a later refresh. Results publish in one transaction. Employer ingestion and index building remain manual and separate.

Stars belong to owned authenticated sessions and sort before other sessions on the dashboard. Bookmarks belong to `(user_id, employer_id)`, not browser component state. A company must be currently visible to the verified owner before it can be bookmarked; locked names cannot be enumerated or bookmarked. Dashboard bookmark cards are rechecked against current identity, sponsor authorization, usable channels and accepted explanation claims. Removing a bookmark does not remove feedback or the employer. The previous Save button's recorded choices are restored once by migration where the original result is still available.

The private bookmark table has RLS enabled with default-deny grants for direct clients. The authenticated server gateway checks user ownership for every route. No new public database grants or client credentials are introduced. Relevant/not-relevant events remain in `sm_private.feedback_events`; an admin interface is deferred.

The account menu opens on hover, closes on pointer leave, outside pointer down, focus leaving or Escape, and supports touch/keyboard activation.

## Validation

A fresh disposable Postgres database passed the full 240-test backend suite on 18 October 2026 (including the additive historical-save backfill). Tests cover profile isolation, refresh retry/concurrency, stale result publication, preserved unlock/star, preview limits, bookmarks and cross-account authorization. Web type checking, production build and personalization unit tests pass. Local UI checks use synthetic identity/company fixtures; no production profiles or emails are created for these tests.

## Production publication — 18 October 2026

Published to `https://sponsorreach.uk` on the existing London instance. The new web build was compiled on ARM in a staging folder before switching. The five backend files were patched against the actual deployed source, preserving the live retrieval/ranking implementation. Both additive migrations applied successfully; web/API/worker/Caddy are active. Experimental skill-graph ranking remains disabled. No instance, database plan or network resource was added.

Rollback code is under `/opt/sponsorreach/workspace-20261018/`: `backend-before.tar.gz` and `web.previous`. The current runtime and Caddy configuration were not changed. Database changes are additive and remain compatible with the previous app code. On rollback, restore code and web together; do not remove bookmark data.

Authenticated interactions were exercised in a local synthetic fixture; live public routes, profile suggestions, reset rendering and unauthenticated access restrictions were checked after publication. The automation browser has no signed-in production session, so a final check using the operator's actual signed-in browser remains useful.
