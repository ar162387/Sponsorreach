# London test deployment — 18 October 2026

Temporary URL: https://sponsorreach.13.40.164.65.sslip.io/match

A separate t4g.small (2 GB RAM) in eu-west-2 runs the web app, private API and one matching worker. Existing NIMBSS/voice/AY hosts were not modified. Encrypted 20 GB gp3, required IMDSv2, SSM-only administration, and standard CPU-credit mode. Public ingress is 80/443 only. Trial discounts must be confirmed in actual billing; storage/IPv4 are not free.

The database and auth remain in the existing Supabase Singapore project. Application hosting in London does not imply UK-only data residency.

## Verified

- 217 backend tests, web type check and production build passed locally. Native ARM dependency installation and production web build succeeded on EC2.
- Offline MiniLM384 encoder works on the host, with no OpenAI key or per-query model charges.
- Current 7,309 provided-CSV employers and published index/model source hash match. Experimental rankers remain disabled; runtime reports evidence-11-general-role-context.
- Software developer, waiter and plumber each returned 10 source-backed skill suggestions in preflight. Browser interaction confirmed selectable skills, guidance-only experience prompts and optional work areas.
- API/worker test produced 100 saved software recommendations in hybrid mode. This is a functional test, not a human relevance evaluation. Results were withheld before email confirmation. Synthetic profiles/sessions were removed after successful checks; no test emails were sent.
- HTTPS returns 200 with a valid public certificate. HTTP redirects to HTTPS. Temporary pages carry a noindex header.
- All three services remained active with zero restarts during tests. Preflight peak RSS was 621 MiB; a warm observation showed about 512 MB API, 377 MB worker and 32 MB web in cgroup memory. These are samples, not load-test guarantees.

## Remaining limitations

- First observed search took 39.43 seconds; a changed-profile search on the warm worker took 30.83 seconds. The three-second target has NOT passed. Warm onboarding suggestion response was 0.11 seconds (first API call 12.45 seconds). One worker queues requests; this is a low-traffic test pilot.
- Operator confirmed temporary Supabase URLs were saved. A human still needs to verify actual inbox delivery, click the email link and check account refinement on this origin.
- Final public domain, operator information and public privacy arrangements remain needed before commercial launch.
- Additional $40 credit is pending; the existing account's spending still needs reducing for the full 105-day plan. No existing-server optimization, resize or migration was performed.
- The temporary auto-assigned IP may change on stop/start. Update the origin and auth redirects if that occurs; ordinary app-service restarts do not change it.

## Source and private files

Code: https://github.com/ar162387/Sponsorreach
Local Git checkout: /Users/syedshahabdurrehman/Code/Sponsorreach
Local credentials and private data are ignored by Git. CSV processing, employer/index embeddings and artifact builds remain manual and local. The cloud worker only claims match and private cohort-refresh jobs.
