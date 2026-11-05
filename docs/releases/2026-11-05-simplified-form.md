# Simplified search form — 5 November 2026

Implemented the requested three-step form changes:

- Step one: combined background field, desired roles and career stage. Removed specialisation, exploration controls and career-idea suggestions.
- Step two: skills, UK location/relocation, visible industries and visible visa timing. Removed experience/projects, related-role selection, professional-context toggle and certifications. Visa fields remain optional without optional labels or a toggle.
- Step three: review and submit. Removed visa fields, repeated credit consent and repeated terms acknowledgement.
- Positive balances appear only in the existing top bar. The form shows a red shortage message only at zero credits.

The form no longer calls catalogue status, role-normalization or suggestion endpoints while progressing through the first two steps. Removed fields are cleared when restoring older drafts/profiles; an old specialisation is folded into the combined background value so useful background text is preserved. Drafts and account isolation remain in place.

## Reproduced failure

The reported input was background `software enginer`, role `manager`, skills `plumber`, `software`, `full stack`, Birmingham and willingness to relocate. The backend rejects the broad role `manager` with `profile_needs_clarification`. The old first-step normalization branch allowed the form to advance despite this unresolved clarification, then hid the final structured 422 behind a generic error.

The form now requests a specific role in step one and keeps the submitted details. It does not silently infer a managerial specialism from conflicting background/skill input. The server continues to enforce its validation. Structured role clarifications now return the user to the role field; field-validation errors and temporary non-JSON service errors are surfaced clearly.

An API regression test confirms that the reported broad role returns this specific clarification without spending credits, while `Software engineering manager` with the same background, skills and location is accepted and can complete a synthetic result delivery.

## Validation

Production build and type checking pass. Component tests cover removed controls, field placement, no consent gate, retained drafts, hidden-field cleanup, early manager clarification and useful server errors. Browser checks confirm mobile layout without horizontal overflow, optional visa fields visible in step two, zero consent checkboxes in step three, valid request construction and no normalize/suggestion/catalogue requests during form progression. Browser result delivery uses an isolated synthetic fixture; API transaction tests use an isolated PostgreSQL database.

Live server logs showed the rejected 422 submissions; the API was active with no crash restarts or OOM indication when checked. Earlier service restarts are present in its logs. This release restarts only the web service; API and worker remain running. Hosted test-card checkout remains enabled.

This UI/validation release does not refresh the outstanding stale official sponsor register or claim to verify positive production employer results.

Release: `/opt/sponsorreach/releases/20261105-simple-form`.
Previous release: `/opt/sponsorreach/releases/20261105-credit-protection`.
