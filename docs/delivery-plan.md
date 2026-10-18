# End-to-end delivery plan

## Boundary of this iteration

The end-to-end **prototype journey** ends with a buyer's downloadable sourcing recommendation. It represents all major steps while using deterministic data and fixtures. The end-to-end **challenge application** additionally requires live grounded answers, live public-company research, secure hosting and jury access, plus a recorded two-minute demo. Those are separate milestones, not completed claims.

The latest 2026-10-18 user clarification keeps NVIDIA Nemotron and leaves OpenAI Decisions out of scope. Jev is optional, not an MVP requirement. Initial model candidate: `nvidia/nemotron-3.5-lightning` through OpenRouter. Model family is confirmed; this particular variant remains an engineering choice to evaluate. Classification starts as rules. If evaluation warrants Jev later, use the OpenRouter route and existing OpenRouter credential. An OpenAI-issued credential is not interchangeable with an OpenRouter credential.

## Buyer journey and handoffs

| Stage | Buyer action | System response | Evidence / exit condition |
| --- | --- | --- | --- |
| Define | Describe the sourcing decision | Keep a buyer-entered brief alongside the data | Component suitability is not asserted from this CSV |
| Explore | Search, filter and rank | Deterministic values over all 10,000 suppliers | Show active filters, sort direction, source version |
| Shortlist | Select up to 20 | Keep selection across pages/filters | Enforce the cap without silently dropping items |
| Compare | Inspect risk dimensions and delivery | Matrix, values, and focused risk bars | Lower risk is better; operational percentages are separate |
| Ask | Type or dictate a question | Query validated data and show answer evidence | Unknown questions/IDs fail visibly; no fabricated values |
| Investigate | Name and confirm a real legal company | Plan, fetch, investigate flags and build cited dossier | No automatic mapping to anonymized supplier IDs |
| Decide | Select preferred/alternate and justify | Draft recommendation with unknowns and next action | Buyer owns the judgment; qualification remains unresolved |
| Handoff | Download memo and comparison CSV | Portable record for review in existing tools | IDs, metrics, rationale, source version and limitations included |

## Implementation slices after prototype review

### 1. Data and deterministic query foundation

Preserve original CSV plus SHA-256. Add schema/versioned ingestion into SQLite or another simple store. Use parameterized, allowlisted query operations for search/filter/sort/compare. Validate risk ranges, uniqueness, missing values and score direction. No vector database is needed to sort 10,000 rows. Store user/project context separately from source facts.

Exit: challenge example comparison returns SUPP_00731 financial risk 53, SUPP_00012 54, SUPP_00450 65; selection limit enforced server-side; changed snapshot and missing IDs are handled.

### 2. Grounded Nemotron answers

Server-only OpenRouter adapter. A model proposes a small typed query plan; code validates fields, operators and requested IDs before executing. Return precise values and source cells to the model for wording. Render answer objects into fixed accessible UI components. Validate citations and numbers before display; allow abstention. Keep credentials, cost limits and request logs on the server; redact sensitive fields. Do not stream an unverified numeric claim as a final answer.

Exit: exact arithmetic and ranking fidelity, supported citations, unknown/ambiguous question fallback, schema failures, provider outages and budget exhaustion all have observed behavior. Never invent the unpublished Total Risk Index formula.

### 3. Public-company research

Identity form with legal name, country and website; buyer confirms ambiguous entities. A bounded worker plans research, fetches public primary sources and relevant news, and follows specific flags. Store publisher, title, URL, publication/retrieval dates, supporting passage/page, entity match and status per claim. Show contradictions, stale reports and incomplete searches. Public website text is untrusted data, not agent instructions.

Initial budget proposal: 12 fetched pages, depth 2, 2 narrowly scoped follow-ups, 90 seconds, with partial results on timeout. Tune after observation. Block private/local IP targets and unsafe redirects; do not execute downloaded content. No outreach, supplier contacts or autonomous approval.

Exit: a real company report with inspectable supporting sources; an ambiguous-company example; a no-evidence result; a simulated prompt-injection page; time/budget caps. Each material risk claim is grounded, qualified and reviewable.

### 4. Optional speech and System One experiment

There is no image requirement in the supplied challenge or dataset. Voice input only needs transcription to text. Scanned certificates, visually complex reports or part photographs would introduce a separate image/OCR requirement if later requested; they are not part of this scope. System One text triage can be useful independently of images, but must demonstrate value over the simpler baseline.

Speech: push-to-talk → stop/cancel → editable transcript → explicit submit → ordinary text answer. Keep supplier IDs visible and resolve ambiguous dictation before submitting. Use Whisper if self-hosting serves the requirements; use managed transcription if deployment simplicity wins. No speech output. Benchmark German/English terms, accents, ID errors and noisy offices before claiming accessibility benefit.

Optional Jev via OpenRouter: classify intent or passage relevance/category behind the research UI. OpenAI Decisions is excluded from this iteration. Measure against rules and Nemotron on labeled examples. A proposed evaluation set is 100–200 passages including irrelevant entities, conflicting evidence and uncertain cases; compare accuracy, abstention, cost and end-to-end latency. Select thresholds from observed errors. Confidence is not a supplier risk probability. Keep final ranking, arithmetic and qualification outside the model.

Exit: measurable improvement justifies another dependency; otherwise retain the simpler path. Optional document uploads can follow, with extraction page references and buyer review.

### 5. Deploy and submit

Choose a hosting target after layout approval. Serve the frontend and authenticated backend over HTTPS, add a jury account/session, server-side secrets, rate limits, timeout/error states and a resettable demo workspace. Do not expose the entire workspace through a static server. Keep dataset licensing/access aligned with challenge rules.

Deliver a live URL and jury credentials through an appropriate private channel. Verify from a fresh browser session. Capture the final two-minute walkthrough only after the working path is stable. Supply private repository access to the jury; keep `.env`, recordings containing credentials and local artifacts out of Git.

## Useful additions in priority order

1. Evidence-linked answers and an exportable shortlist memo: highest value and fit with existing procurement workflows.
2. Explicit missing qualification/component data and next actions: prevents a low risk score becoming a false approval.
3. Read-only SCM STAR / SCM CoRe or SAP imports after confirming actual interfaces; CSV is the first practical handoff.
4. Scenario weighting as a separately named buyer preference score, only after confirming normalized metrics; never overwrite the provided Total Risk Index.
5. Documents, change monitoring and review collaboration after obtaining provenance, timestamps and permissions. A single CSV cannot show trends.

## Submission checklist

- [x] Private GitHub repository with original dataset and dictionary
- [x] Reproducible data audit and continuous data check
- [x] Primary-source research plus parent review
- [ ] Buyer reviews HTML variants and selects direction
- [ ] Live grounded chatbot and bounded real-company research
- [ ] Authenticated hosted app, working jury credentials and access check
- [ ] Two-minute final screen recording
- [ ] Jury repository access granted and all deliverable links checked

## Two-minute recording script (planned)

- 0:00–0:15: Explain the buyer's decision and 10,000-row source; show the score direction.
- 0:15–0:40: Filter/rank, select three suppliers, open comparison; briefly demonstrate capacity for 20.
- 0:40–1:00: Ask the financial-risk question and open cell evidence; show the high-total explanation limitation.
- 1:00–1:25: Confirm a real company, show research plan, a supported finding and a follow-up/uncertainty.
- 1:25–1:45: Demonstrate optional editable speech input without spoken replies.
- 1:45–2:00: Record rationale and export memo with next action; show where a reviewer goes next.

Prototype recordings must explicitly say offline/simulated. The eventual challenge recording should demonstrate the implemented live features, not disguise fixtures as agent results.
