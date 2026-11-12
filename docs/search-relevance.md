# Search relevance contract

| Form input | Matching behavior |
| --- | --- |
| Degree, field of study, or professional background | Supplies embedding context and helps disambiguate a broad Architect title. An explicit target role takes precedence. |
| Desired roles | Supply separate retrieval queries and professional evidence checks. The shortlist interleaves available direct results for multiple requested roles. |
| Career stage | Students and graduates receive an evidence-based preference for recorded junior, graduate, trainee or entry-level work. Career-change and experienced selections do not imply seniority. |
| Skills you want to use | Supply embedding context and count toward relevance when supported by compatible role evidence or an accepted skill claim explicitly linked to the occupation. Canonical equivalents count once. |
| Location preference | Anywhere ignores geographic rank. Prefer sorts area matches first within each role group. Only filters known out-of-area companies and separates unknown locations. |
| Preferred UK location | Matches normalized recorded town, county or workplace strings. The evidence shows which record matched. |
| Include related roles | Adds taxonomy-linked alternative roles to their own group. |
| Preferred industries or areas of work | Applies a preference from accepted company activities through a versioned alias dictionary or literal wording. |
| Current visa route and expiry | Saved as private profile context, separately from ranking. |

Location uses exact normalized strings and reviewed equivalents. City of Edinburgh and Edinburgh are equivalent. City of London and London remain distinct. A company town or county is company-address evidence. A recorded workplace is labeled separately. Distances, commuting areas and remote work require additional evidence.

The three Architect interpretations use independently maintained phrases for building, technology and business. A bare title without sufficient context prompts for a choice. Mixed or incompatible employer evidence cannot qualify on similarity alone. Historical role records and current verified matching vacancies have separate indicators. Skills absent from accepted evidence are labeled unconfirmed.

Unknown-location results appear after the main shortlist in a collapsed section and share the existing credit and batch entitlements. The headline count covers the main shortlist. A shortlist containing only unknown-location companies can still have a nonempty first batch under the existing credit rules. Completely empty shortlists and failed searches use no credit.

The API and worker reuse the current tables. Search and evidence versions are stored with each new shortlist. The embedding cache is local to a worker process, with a 512-vector limit and a 24-hour expiry. Queue, embedding, retrieval, hydration/ranking and persistence timing go to worker logs without profile text.

Data gaps include the absence of recorded workplaces in the inspected 7,309-company catalogue, sparse role-linked skills, limited current vacancy evidence, limited Illustrator coverage within the design profile's first ten, and no supported results for the audited primary-school teaching profile. Location filtering and profession disambiguation fix how existing evidence is applied. They cannot supply evidence absent from the catalogue.
