# SponsorReach hosting check — 18 October 2026

Oracle CLI credentials were verified against the Dubai home region. The AY backend is the only active instance, on an E2.1.Micro. Available A1 quota: 2 OCPUs and 12 GB RAM. Existing boot storage: 47 GB.

One explicitly authorized launch attempt requested a separate SponsorReach A1.Flex instance, 2 OCPUs, 12 GB RAM, Ubuntu 24.04 ARM, 50 GB boot disk. Oracle rejected it with `500 InternalError: Out of host capacity.` No paid alternative, repeated launch loop, or changes to AY were made. Quota availability does not establish physical host capacity.

Next step: retry on direct operator request, or select a separately funded host. No recurring retry job was installed. Do not run the old scraper retry loop: it uses an obsolete image and repeatedly retries ambiguous timeouts.

Production deployment remains pending suitable hosting, public origin, and final operator contact details. CSV processing and employer embeddings remain local; cloud services receive published artifacts only.

## Smaller configurations attempted

At the operator’s request, separate launch attempts for 1 OCPU / 6 GB and 1 OCPU / 4 GB (each with a 50 GB boot disk) also returned `500 InternalError: Out of host capacity.` Duplicate instance checks preceded each request. No background retry loop was started.
