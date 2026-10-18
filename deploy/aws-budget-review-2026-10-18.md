# AWS budget review — 18 October 2026

Read-only inspection authenticated against the existing AWS account. No resources or service settings were changed.

## Verified findings

- Free plan active; remaining credit $83.10. API expiration 2027-01-29 19:43 UTC (30 January locally). Two incomplete $20 activities: AWS Budgets and Lambda web app. Rewards are pending, not yet included in actual balance.
- Current instance: t3.small, Singapore, x86_64; 20 GB gp3; unlimited CPU mode.
- Read-only SSM sample: 1,906 MiB physical memory, 1,067 MiB available, 296 MiB swap used, 9.9 GB disk free. No kernel OOM entries observed in the last seven days. Postgres service approximately 914 MiB current cgroup memory. One PostgreSQL process showed about 67% lifetime CPU; this is a diagnostic lead, not a proven inefficient query.
- October 1–17 costs excluding credits/refunds: compute $10.4884, EC2 Other $5.8976 (including CPU surplus $4.8728 and gp3 $1.0245), IPv4 $1.995, S3 $0.0523. Estimates may change with billing latency.
- Screenshot forecast $32.48/month; approximately $112.05 for 105 days using 30.4375 days/month. This excludes adding SponsorReach or growth.

## 105-day planning envelope

After both rewards actually post: $123.10, or $1.172/day and $35.17 per 30 days. Aim below $30/month to retain a reserve.

AWS Price List API verified Linux shared on-demand hourly rates: Singapore t3.medium $0.0528; Singapore t4g.medium $0.0424; US East t4g.medium $0.0336.

Assuming 2,520 running hours, one public IPv4 at $0.005/hour, and a $2/month disk allowance:

| Single server | 105-day base estimate | Balance from $123.10 |
|---|---:|---:|
| Singapore t3.medium | $152.66 | -$29.56 |
| Singapore t4g.medium | $126.45 | -$3.35 |
| US East t4g.medium | $104.27 | $18.83 |

These base estimates exclude CPU surplus, data transfer, backups, other services, taxes, migration overlap, and increased usage. CPU surplus is already material; do not promise the US East option fits until that workload is measured/optimized. Four GB combined-host capacity also requires a measured smoke/load test.

## Recommended sequence

1. Operator completes the two reward activities; verify credits post. Do not create a new database or leave experimental Lambda infrastructure running solely for a reward.
2. Identify the sustained PostgreSQL/CPU activity and verify it against useful NIMBSS workload. Optimize only after tests; do not blindly disable unlimited mode, which can throttle the existing services.
3. Measure a compact SponsorReach runtime locally, with one matching worker and offline/manual CSV processing. Reduce redundant model copies before considering the 2 GB host.
4. Compare retaining the optimized existing host with replacing it using one 4 GB Graviton host in a cheaper region. ARM requires rebuilding applications, migration/restore testing, endpoint cutover and rollback. Keep the existing server until validation, but bound overlap costs.
5. Deploy only when the full forecast is below the envelope with reserve. No second always-on instance approved by this review; no paid-plan upgrade or recurring retry job made.

Budget alerts inform but do not cap spending. Credit expiry is a separate deadline regardless of remaining credit.

## Separate instance alternative and newly checked trial

AWS EC2 FAQ explicitly advertises 750 aggregate t4g.small compute hours/month through 31 December 2026, for new and existing customers; separate billing eligibility must be verified. API free-tier usage currently reports no t4g usage entry, which does not prove ineligibility. Infrastructure only: disk, IPv4 and surplus CPU are excluded. Standard on-demand rate in US East confirmed $0.0168/hour.

Without trial: US East small costs about $60.46 extra over 105 days; combined forecast $172.50. Medium costs about $102.79 extra; combined $214.84. Assumes one added public IPv4 and 20 GB gp3, excludes new surplus/traffic/tax/backup charges.

With the trial applying through Dec 31: conservative 105-day calendar from Oct 18 has 75 trial days and 30 paid days. Added small cost approximately $30.22; combined approximately $142.26 (script-calculated exact rounding supersedes these approximate values). To fit pending $123.10 total, existing run-rate must fall below about $26.93/month with no reserve; target $24/month or less and verify SponsorReach fits 2 GB in production. No launch authorized or performed during this cost comparison.

Source: https://aws.amazon.com/ec2/faqs/ sections on T4g free trial. This supersedes the blanket preference for consolidation if trial eligibility, memory fit and sufficient savings are confirmed.
