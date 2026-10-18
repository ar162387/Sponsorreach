# Skills and task matching: research, implementation and review

SponsorReach discovers potential employers for outreach. It does not match candidates to complete job specifications, because the imported data mostly describes businesses and historical titles. A company may support several professional functions. Missing descriptors remain a coverage limitation.

## Research decisions

[LinkedIn Skills Match](https://www.linkedin.com/blog/engineering/talent/how-data-is-powering-skills-based-hiring-on-linkedin) describes prioritising explicitly supplied skills, choosing thresholds through relevance/outcome analysis, and the trade-off between precision and coverage. Its learned graph also uses interactions we do not have. We adopt explicit skills and measurable relevance; we do not introduce a GNN without training data.

[LinkedIn skill extraction](https://www.linkedin.com/blog/engineering/skills-graph/extracting-skills-from-content) describes segmentation, contextual interpretation and canonical skill linking. We keep employer spans separate, distinguish the relation in which a subject appears, and preserve user wording alongside derived taxonomy associations.

[SkillSpan, NAACL 2022](https://aclanthology.org/2022.naacl-main.366/) provides expert-annotated hard/soft skill spans from job postings. This supports span-level evaluation. Its annotations are not labels for our employer catalogue, and we have not claimed to train on it.

[Job Posting-Enriched Knowledge Graph for Skills-based Matching](https://arxiv.org/abs/2109.02554) examines enriching structured occupation/skill resources with job information. SponsorReach's graph retains the difference between a taxonomy relationship and an observed employer claim; neither establishes an open position.

[CareerBERT](https://arxiv.org/abs/2503.02056) investigates aligning candidate experience with ESCO occupations through a shared embedding space. Our implementation uses the existing free local encoder and ESCO resources; it does not claim CareerBERT's reported model performance.

[ESCO](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api/esco-web-service-api) supplies occupation labels, alternative labels, hierarchy, ISCO links and essential/optional skill relationships. Its skill links also distinguish knowledge from skill/competence. The previous import dropped that distinction; the new bundle preserves it.

## Implemented representation

The general engine does not contain job-specific employer allowlists or new synonym dictionaries. It uses all 3,039 occupations and 13,474 skills in the pinned ESCO snapshot, plus the recorded employer spans in the local catalogue.

Nodes: candidate interests, explicit candidate skills/tasks, ESCO occupations, ESCO skills/knowledge, employer claims, employers. Edges retain their type: supplied by candidate; occupation alias; narrower occupation; essential/optional task; observed at employer; derived semantic association. Derived edges retain source claim IDs, original spans, employer version, resource URI and similarities. An occupation's skills are suggestions, not qualifications assigned to a person.

Titles provide intent and context. A broad title or acronym can be interpreted using professional background and supplied tasks, without replacing the user's title or asserting a new credential. Unresolved niches retain their original text. Unknown or ambiguous terms are not forced into the nearest category. Generic title clarification is deferred until skills/experience can contribute. Strong, specific, explicitly supplied tasks also have a direct evidence route, so a missing occupation concept does not force a title substitution. Common transferable skills and sources whose stronger relation is a tool, teaching or recruitment remain excluded.

Explicit professional skills narrow task retrieval and receive the largest ranking weight when available. Broad prerequisites and transferable skills cannot establish a function on their own. Knowledge subjects can retrieve candidates and support a core professional activity; they cannot create unrelated internal functions. Task frequency, competing occupation alignment, competing task interpretations and evidence-relation checks limit broad propagation.

The relation checks distinguish doing the work from software tools, education, product supply, membership representation and recruitment for other employers. These are generic relations, not profession-specific exceptions. An HR service, a law service and recruitment for someone else's chef role remain different relations. A sector alone cannot establish a management function.

Employer matching uses individual spans. A company is not assigned one exclusive occupation, and evidence for one function does not transfer to another function in the same record. New graph candidates enter the existing bounded hybrid retrieval. Identity, current relevant sponsor membership, useful channels and current accepted evidence remain required. Graph paths are discarded when their employer version or source span is no longer valid.

Explanations cite recorded work and the connecting task. They do not claim an employer requires every user skill, has a vacancy, or will sponsor the candidate.

### CSV evidence is the foundation

The supplied export contains 6,551 populated Indicative Tags fields, 1,823 populated Job Tags fields and 6,862 populated Reasoning fields across 7,510 company records (before the outreach-route screen). These counts describe populated fields, not independent accuracy measurements. Indicative Tags contribute activity claims; Job Tags contribute historical role claims. The combined Tags display string is retained alongside its source columns, rather than counted as another independent corroborating source.

Every imported row is preserved in `source_records`. Import and baseline activation also retain immutable, field-addressable context observations for Reasoning, Tags, Indicative Tags, Job Tags, Evidence URLs and Field States. Replays do not duplicate them. Their source artifact, record key, original wording and observation time remain available for attribution review. This addition does not change existing semantic document content or require re-embedding.

Reasoning is the scraper judge's extraction and identity rationale, not an unconditional list of company activities. For example, a rationale can explicitly reject a same-name manufacturing website while accepting a care provider's LinkedIn page. Its rejected website must not create manufacturing relevance. Context observations are kept outside accepted professional claims and semantic documents. Additional professional facts found only inside Reasoning need attributable span-level extraction and review before promotion; the current release does not silently promote the whole column. The graph interprets recorded evidence and connects it to user tasks; it does not replace that evidence with taxonomy assumptions.

## Ranking and release control

The graph is enabled explicitly by `SPONSORREACH_ROLE_GRAPH_ENABLED=true`. Without this flag the existing matcher is retained. The graph version and ranking version enter saved result/cache versions. Saved shortlists remain frozen; new searches use the selected model.

The current local candidate is `evidence-12-skills-context-graph-16`. It has not been promoted to the hosted pilot. The paired relevance lab retains the baseline and a prior candidate for regression comparison. See [the evaluation workflow](RELEVANCE_EVALUATION.md). Professional relationship choices are deterministic; unordered iteration must not choose between essential and optional task links. Strong practical core work can remain eligible when a narrower supplied task is absent, while knowledge-only fallback cannot establish practical work by itself. Source-context leakage remains an explicit review finding, especially agency specialisms and generic sustainability wording.

For graph-supported candidates with explicit skills, the initial score is:

`(.65 + .35 Q) × (.20 R + .50 T + .15 V + .10 P) + .05 A + .03 J`

These are engineering weights, not probabilities or measured optimal weights. Evidence gates still precede ranking. The reduced quality multiplier spread prevents a weak general first-party tag automatically outranking a precise supported imported task match. Candidates without explicit skills retain the existing weighting. Unsupported fields contribute no invented skill evidence.

## Local manual data updates

Process the new CSV, reconcile identities and publish its normal search index locally. Rebuild the prospect corpus for that employer snapshot. Build the ESCO onboarding bundle using the pinned source through `sponsor_match.onboarding.build` if its version changed. Then run from the backend environment:

```sh
sponsormatch build-role-graph --prospect-folder /absolute/path/to/prospect/snapshot --output /absolute/path/to/data/role-graph --publish
```

Builds reuse locally cached embeddings for unchanged text. No paid model calls or live scraper connection are introduced. Upload the selected `data/onboarding` bundle and selected immutable graph directory plus `active.json` to the application host. Do not upload the relation-vector SQLite build cache, evaluation profiles, candidate data or unused graph versions. Publish the paired assets while the worker is stopped, validate, and restart it. Retain previous assets and code for rollback.

The graph uses compressed artifacts and bounded matrix blocks; it requires no separate graph database. Published graph/vector files have checksums. A changed company invalidates its old paths until a matching snapshot is rebuilt.

## Evaluation interpretation

The local form matrix covers minimal, complete and multiple-interest profiles, the environmental-engineering example with its spelling variations, acronym-only and broad-title variants, plus technical specialisations and nontechnical professions. Skills, task descriptions, experience, optional preferences and certifications are varied. These checks measure coverage, response changes, consistency, source support and regressions; result counts are not precision.

Development review must inspect concrete source spans, not employer names alone. Distinguish direct relevance, related relevance, insufficient evidence and wrong attribution. Keep unjudged results unjudged. Independent human Precision@3, Precision@10 and NDCG remain separate release measurements. No new held-out accuracy claim is made by this implementation. Zero results are preferable to unsupported departments; sparse occupations still require better employer descriptors.
