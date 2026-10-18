# SponsorReach search-quality evaluation

Search quality needs labelled examples of useful results. Runtime success, embedding similarity, an LLM judge's confidence and a populated contact field cannot establish relevance. SponsorReach now has a local relevance lab that freezes inputs and evidence, compares rankers, collects judgments and produces a failure list. It introduces no paid API or cloud service.

## What research and established systems do

| Practice | Primary source | SponsorReach implementation |
|---|---|---|
| Evaluate typical queries against manually rated documents, then compare precision and ranking-sensitive metrics | [Elastic ranking evaluation](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval) | Frozen form profiles and pooled employer judgments; per-query and occupation slices |
| Pool results from multiple systems to make assessment practical | [NIST TREC relevance judgments](https://trec.nist.gov/data/reljudge_eng.html), [TREC overview](https://trec.nist.gov/pubs/trec30/papers/Overview-2021.pdf) | Union of compared top-ten results; deduplicate employer/profile pairs; retain unknown labels |
| Combine offline quality analysis with online experiments and operational guardrails | [Microsoft pre-experiment practices](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/patterns-of-trustworthy-experimentation-pre-experiment-stage), [during-experiment practices](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/patterns-of-trustworthy-experimentation-during-experiment-stage/) | Offline paired comparisons first; later controlled traffic experiments with latency/error guardrails and useful outreach feedback |
| Treat LLM relevance assessments as a fallible measurement instrument | [NIST: Don't Use LLMs to Make Relevance Judgments](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=958495), [research on limitations of replacing humans](https://arxiv.org/abs/2412.17156) | AI development scores and human scores cannot be combined or relabelled automatically. Human calibration and adjudication remain required |

These sources concern their own systems and datasets. They do not establish SponsorReach accuracy. A/B testing is not a substitute for a review set at this application's present traffic level. Clicks are affected by position, the preview boundary and presentation; contact clicks alone are not relevance labels.

## What the lab measures

* **Direct Precision@3 and @10, fixed slots:** direct results divided by K. A single relevant result fills one of three preview slots and scores 1/3. An entirely unjudged query is excluded from accuracy averages, including an empty query. An empty output for a query with judged relevant pooled employers scores zero.
* **Returned precision:** direct results divided by actual returned results, reported separately. This exposes the difference between accuracy among returned companies and useful preview coverage.
* **Task Precision@K:** direct results with reviewed support for at least one supplied professional task, divided by K. A general software provider can be professionally relevant while lacking evidence of mobile development. Unmarked task fit is unknown, not false.
* **NDCG@K:** graded ordering quality, with direct grade 3, related grade 1, and other reviewed grades 0; gain is `2^grade - 1`. The entire frozen pool must be judged before computing its ideal ranking. A pool with no positive gain has undefined NDCG. A second task-sensitive NDCG uses gains 7 for specific direct support, 3 for broad direct support and 1 for a related career.
* **Pooled recall at saved depth:** recovered judged direct employers divided by direct employers in the judged pool. This is neither exhaustive catalogue recall nor Recall@200. The lab's default saved depth is ten. Retrieval-stage traces help locate misses but do not create exhaustive gold labels.
* **Coverage, abstention and failures:** result availability, unfilled preview slots, failures, slice counts and judgment coverage remain visible. An abstention is not automatically a false negative; the evidence pool must support that conclusion.
* **Uncertainty:** paired deltas use the same judged profiles on both runs, with family-cluster bootstrap intervals. Small-sample warnings are included. Intervals from a small, selected development sample do not establish population performance or release readiness. Aggregates based on different subsets must not be compared as if paired.
* **Reviewer agreement:** nominal Cohen's kappa, exact agreement and an adjudication queue. Distinct reviewer IDs are required, but local self-reported identities are not independently authenticated.

Internal compatibility scores remain available in expandable technical traces. They are ordering features, not accuracy, employment or sponsorship probabilities. Accuracy comes from comparing ranked outputs against judgments.

## Review rubric

Judge against the supplied role, background and explicit tasks, using the complete recorded activity/role context. A phrase inside an agency's recruitment specialisms is not necessarily its own professional function. A generic sustainability value is not technical environmental work. Product supply, software for a profession, teaching and doing that profession are distinct relationships.

Choose direct, related, insufficient evidence, irrelevant or wrong entity. Related means a substantive career alternative, not simply weaker evidence for the original role. Mark task fit as specific, broad or contradicted; leave it unreviewed when unsure. Specific means the record supports at least one important supplied task or its justified semantic equivalent; it does not mean every skill, qualification or software version is required or present. Record a short source-based reason.

Review explanation support and useful channels separately. The lab does not infer deliverability or current open vacancies from their presence. Reviewers see company evidence before optional technical traces; ranker name, rank and score are initially hidden, and presentation order varies across pairs. Avoid opening technical traces during a blinded assessment.

## Reproducible workflow

Run in the backend Python environment with `PYTHONPATH=backend/src`. All outputs below belong in the ignored `.local` directory and remain private.

```sh
# 80 occupations sampled independently of company/result success, three variants each.
python scripts/relevance_lab.py sample --output .local/profiles-240.json

# Same profiles and unchanged source snapshot; diagnostics bypass result-cache hits.
python scripts/evaluate_skill_graph.py --baseline --profiles .local/profiles-240.json --output .local/baseline.json
python scripts/evaluate_skill_graph.py --profiles .local/profiles-240.json --output .local/candidate.json

python scripts/relevance_lab.py build --run a_baseline=.local/baseline.json --run b_candidate=.local/candidate.json --output .local/relevance-lab
python -m http.server 4013 --bind 127.0.0.1 --directory .local/relevance-lab

# Export reviews from the report. Defaults to human labels only.
python scripts/relevance_lab.py score --benchmark .local/relevance-lab/benchmark.json --reviews .local/relevance-lab/reviews.json --output .local/scorecard.json
python scripts/relevance_lab.py agreement --benchmark .local/relevance-lab/benchmark.json --first .local/reviewer-a.json --second .local/reviewer-b.json --output .local/agreement.json
```

The sampler spans available ISCO major groups and keeps all variants of each two-digit family in the same proposed split. Full-context profiles and skill choices are explicitly synthetic personas, not qualifications inferred for actual users. Reserved splits are only valid held-out tests if their labels and related families have not informed tuning elsewhere. The existing hand-written development scenarios are not held-out. Do not use the reserved judgments to tune a change and still call them held-out.

The earlier 59-profile regression matrix complements the 240-profile ontology sample. It varies minimal forms, complete forms, multiple interests, the environmental example and technical specialisations. Further field-ablation scenarios are available in `scripts/profile_matrix.py`. These test sets are not a statistical sample of actual future user traffic.

Snapshots bind reviews to exact form inputs, employer evidence and compared versions. Changed source snapshots, mismatched profiles, duplicate results, stale hashes and conflicting reviews fail closed. Adding a new ranker changes the frozen packet; review against the new packet rather than silently reusing browser exports. A result's professional relevance can remain stable across rankers, but changed evidence or explanations need fresh assessment.

## Debugging loop

1. Start with the largest per-family failure or a user-reported search, not the aggregate mean.
2. Inspect the full record and explicitly mark the expected professional relationship.
3. If a judged relevant employer was missed, inspect branch retrieval, fusion pruning, gate reason and final ranking. Missing trace data is reported as unavailable rather than guessed. Traces are local/operator-only, never added to public API results.
4. Fix the general representation or decision rule. Add a regression test with contrasting cases. Avoid an employer allowlist or an occupation-specific exception.
5. Replay the identical frozen inputs, inspect paired changes and affected occupational slices, then assess a fresh reserved set before promotion.
6. Have a second person independently review at least 20%, prioritising disagreements and risky failures. Adjudicate the differences. AI-assisted diagnostics can prioritise review, but cannot establish human acceptance thresholds.

On 18 October the comparison exposed a law profile dropping from supported employers to zero. Tracing identified over-restrictive task narrowing and occupational competition. Generic changes recovered supported legal-service candidates. It also exposed recruitment-context leakage, broad engineering tags and sustainability values being mistaken for technical work. These findings are regression evidence and unresolved quality risks, not proof that the new ranker is globally better.

## Promotion and online validation

Keep the candidate behind its existing feature flag. Require sufficiently covered, independent reviewed results on reserved occupational slices; the original targets remain 90% direct P@3, 80% direct P@10 and 98% explanation support, plus no unsupported vacancy or sponsorship-willingness claims and reliable identity/sponsor linkage. These are product targets, not statistical guarantees. Specify minimum per-slice sample counts and intervals before using them to promote.

At low traffic, first run the candidate as a shadow comparison. Once enough users exist, randomise at account level, maintain a stable control, define the primary useful-outreach outcome in advance and monitor errors, queue delay, latency, broken channels and abstention as guardrails. Do not repeatedly peek and declare a win on whichever metric rises. Preserve impressions and positions. Neither a contact click nor a paid unlock proves relevance or sponsorship success.

The local lab never grants automatic release approval. It reports what is known, what remains unjudged and what needs investigation.
