# CSV outreach screening — 14 October 2026

Scope: `scraper_data.csv`, 7,510 nonempty employer records. Original CSV is unchanged. This is structural screening, not proof of deliverability, employer attribution or professional relevance.

| Classification | Employers | Action |
| --- | ---: | --- |
| Potential digital route | 6,544 | Retain for evidence/channel validation |
| Postal address only | 726 | Retain for review; exclude from recommendations without an accepted useful digital channel |
| Ambiguous/unusable digital fields | 39 | Retain for review; no inferred outreach route |
| Neither digital contact field nor postal address | 201 | Archive outside live employer tables with verified backup |

No duplicate source IDs were found. There are 22 possible normalized name/town duplicate groups, requiring identity review. Shared names or domains do not authorize merging.

Cleanup archives complete selected database records in a checksum-verified gzip JSON file before deleting them from employer/evidence tables. Minimal source dispositions retain canonical IDs and archive hashes; original raw source payloads are replaced by archive references. Thus these rows no longer occupy full employer records, but a small audit trail intentionally remains. Postgres can reuse deleted-row space; this does not promise immediate physical database shrinkage.

The operation refuses to archive records with reviewed/indexed evidence, saved matches, linked identities, other source namespaces, or additional contact information. Imports automatically screen future no-route records. Replaying a CSV does not recreate archived employers; a later batch with contact information restores the same canonical ID. Existing employers keep historical information if a later row is incomplete.

Commands from `sponsormatch/backend`:

```sh
uv run sponsormatch audit-csv ../../scraper_data.csv --output ../data/cleanup/audit.json
uv run sponsormatch cleanup-catalogue ../../scraper_data.csv --namespace local:nocodb:company-enrichment-v2 --output ../data/cleanup/current
```

The second command mutates whichever database is configured. Keep archives securely backed up independently of the laptop before production use. Do not replace the live database with a raw CSV export.

Results still require identity, current sponsor membership, accepted professional evidence and an accepted fresh contact channel. These counts are not launch-ready recommendation counts. The next step is targeted evidence validation, followed by real document embeddings and index publication.
