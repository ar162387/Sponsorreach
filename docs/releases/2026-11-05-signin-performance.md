# Immediate guest sign-in rendering — 5 November 2026

Signed-out `/account` previously mounted the full client account workspace, displayed its skeleton, then requested account overview, anonymous match history and catalogue status before showing sign-in. It now renders a dedicated guest section and email form directly in the server response. Form availability comes from existing server configuration. Signed-in dashboard and account routing remain unchanged. Expired-session and failed-association notices are preserved.

Removed the route-level workspace skeleton; authenticated client workspace components continue to provide their own loading states.

Verification: production build and type checking pass. Browser checks confirm the email field and submit button are visible with JavaScript disabled. With all API calls blocked, the hydrated guest form is visible and editable. The local check made zero initial API requests. The public browser check observed only the header’s independent identity refresh; there were no overview, history or catalogue requests, and blocking that refresh did not delay or hide the form. The expired-session notice remains visible. Staged and live server checks confirm the form is in the initial HTML and no workspace skeleton is rendered; malformed sign-in notice keys do not break rendering.

Deployed `/opt/sponsorreach/releases/20261105-signin-fast` over the previous `/opt/sponsorreach/releases/20261105-search-fix`. The OTP deployment from the other chat completed during staging; the final staged build incorporates that deployed update. API, worker and web services are active. The previous release is retained for rollback.
