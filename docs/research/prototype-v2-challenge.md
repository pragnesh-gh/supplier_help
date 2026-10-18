# Prototype v2: adversarial design review

Reviewed 2026-10-18. Scope: frontend-only design review; no implementation, live company research, or buyer interview. Recommendations below are prototype decisions, not procurement policy. `.env` was not read.

## Verdict and evidence

Proceed with one coherent journey, provided that system membership, research identity, comparison selection and recommendation status remain separate. The dangerous failure is a polished train dashboard making invented supplier capability or a saved corporate disclosure look like verified procurement intelligence.

Reviewed [v2 brief](../prototype-v2-brief.md), [existing template](../../prototype/workbench.template.html), [review record](../prototype-review.md), [dataset audit](../data-audit.json), [metric definitions](../risk_criteria_description.md), [company fixture](company-fixture.md), [buyer workflow](buyers-and-workflows.md), [prior decisions](review-and-decisions.md), [delivery plan](../delivery-plan.md), README and challenge brief. Existing source claims were read as repository evidence, not independently reverified online in this review.

The audit records 10,000 unique rows and 46 columns. There is no train-system mapping, geography, verified company identity, qualification or prior-use field. Existing code already preserves max-20 selection across filters and clears answers on selection changes. It exports a Markdown memo, not a print-ready approval request. Its research form has a Siemens-specific plan even before a supported match; v2 must not carry that misleading behavior forward. Its single global research state and global recommendation fields also need a different conceptual model for multiple research-derived suppliers.

## Decisions that remove ambiguity

### What does clicking a train region mean?

It selects a **train system**, not a geographical region and not proven component capability. Use fixed labels such as doors, bogies, traction, braking, passenger interior and control systems. Geometry is illustrative. Display “Demo system assignments” next to system counts, not only in a footer.

Recommend exactly one primary system per catalog record in this prototype. Assign original rows through a versioned, reproducible fixture keyed by supplier ID; publish the rule and overrides. Ensure the three challenge-example IDs share the doors system so the guided path is coherent. Keep favorite and previous-use fixture rules independent of risk values. Never mutate the source CSV or infer prior use from purchase-order volume. The resulting derivative is an augmented demo dataset, not newly verified supplier data.

Counts mean unique catalog records, including explicitly added research records. Initial total is 10,000; adding one new entity produces 10,001 and increments exactly one system. Display “N records · M scored · K research-only”; original numeric aggregates use only records with supplied scores. Favorites, filters, compare selection, research completion and memo creation do not change catalog counts. No trends or percentage changes: there is no historical baseline.

### Can the overview fit on one screen?

Set a desktop target of 1440 × 900 at normal zoom: compact header/scope, train on the left, selected-system summary and radar on the right, at most three supplier cards, bottom Copilot launcher. One clear Discover suppliers action opens a separate route. Do not put filters, the research timeline or twenty suppliers on the overview. Expanded Copilot is a dismissible panel; the collapsed launcher must not cover content. Smaller viewports and increased text size may scroll rather than shrink text to preserve the illusion of one screen.

Hover/focus gives the same short count tooltip. Click/Enter selects a system. Provide labelled system buttons with identical actions, selected state, count and keyboard focus. Orbit/drag must not accidentally select a region; no continuous rotation. Offer a static fallback and reduced-motion behavior. The train must remain optional for completing the workflow.

### What exactly do six radar axes mean?

Use explicitly named **derived risk summaries**, all 0–100, higher worse. This mapping is an equal-weight prototype choice, not a validated model:

- Financial: mean of Financial_Health_Score and Credit_Rating_Score.
- Legal: mean of Compliance_Risk_Score and Governance_Risk_Score; label the detail “Legal & governance.”
- Country: mean of Geopolitical_Risk_Score, Political_Stability_Score and Environmental_Exposure_Score; detail “Country & environmental exposure.” This is a risk proxy, not a country identity.
- People safety: mean of Labor_Stability_Score and Safety_Incident_Score.
- Operations: mean of Operational_Resilience_Score, Quality_Risk_Score, Digital_Security_Score and Sub_Tier_Visibility_Score.
- Reputation: mean of Media_Sentiment_Score and Market_Sentiment_Score.

Exclude Total_Risk_Index, Industry_Benchmark_Score, External_Intelligence_Score and ESG_Performance_Score from these summaries to avoid silently duplicating broad indices. Keep all 19 original risk metrics inspectable. Preserve source Total_Risk_Index and source level labels unchanged; do not derive a new overall rating or thresholds from radar area. Operational delivery/confirmation percentages remain separate.

For a supplier, require all contributing fields for an axis or mark that axis unknown. For a system overview, show the arithmetic mean of supplier-axis values and the contributing count for each axis; title it “Mean risk of scored records in [system].” Calculate from unrounded values and round only display to one decimal. State that averages can conceal outliers; show the count of source Critical total-risk records separately. No zero-filled unknowns or polygon for an entirely unscored company. Keep axis order and scale fixed. Focus one supplier at a time; a matrix with numbers handles twenty-way comparison. A supplier's absence of a score is never an advantage in ranking.

### What does “previously used” authorize?

Nothing beyond a labelled relationship fact. Use “Previously used · demo history” and a disclosed fixture date/context, with unknown outcome if none is provided. Favorite is an editable personal preference. Neither implies qualified, preferred, safe or approved. A recommendation for a reused supplier follows the exact same memo flow as a new supplier.

## Deterministic journey

1. Reset to doors, the three challenge IDs available, zero selected, Copilot in **Supplier data** mode. Show which assignments/history are simulated. No recommendation exists yet.
2. Select doors on the train or system buttons; open Discovery with that system as a visible filter. Search, risk level, delivery minimum, favorite and previously-used filters combine with AND; offer explicit Clear filters. Default sort is source total risk ascending with supplier ID as tie-breaker and unknowns last. “Country” filtering is unavailable until country evidence exists; a country-risk score cannot substitute for it.
3. Select SUPP_00012, SUPP_00450 and SUPP_00731. Comparison selection is independent of the result page. Show total selected and selected outside current filters. A 21st addition is blocked with a removal path, without losing any prior selection. Compare presents up to twenty columns with pinned labels/internal scrolling and a focused radar; never twenty overlapping polygons.
4. Ask the default Sourcing Copilot which has the lowest financial risk. Show exact Financial_Health_Score values: 54, 65 and 53 respectively, with source cells. SUPP_00731 is lowest on that specific supplied metric, not automatically the recommended supplier. “Why high?” reports observations and missing total-risk weights, not fabricated causal arithmetic.
5. Explicitly switch to Deep Research. Load the saved Siemens AG example through a named action; show identity and scope before replaying the investigation. For unsupported input, show an empty identity/research state with “No saved example for this entity”; do not attach Siemens findings or pretend a search succeeded.
6. Replay the bounded stages below, finish a limited-scope risk report and open it. Add to suppliers requires a selected primary train system and acknowledgement of the displayed entity scope. It creates a separate `research:` record with unknown scores and a linked report; never a `SUPP_*` mapping. The catalog and train counts update immediately. Adding is not selecting for comparison, favoriting, approving or recording previous use.
7. Return to Discovery via “View added supplier.” If current numeric filters would hide it, use an explicit direct record link and explain why it is outside results; do not silently clear unrelated filters. Re-adding the same fixture entity returns the existing record and does not increment counts.
8. Choose a candidate for further assessment, including a previously-used candidate in the acceptance walkthrough. Create the same standardized approval-request draft, inspect the preview and use Print / Save as PDF. Recommend “Further assessment,” “Conditional shortlist” or “Do not proceed”; do not simulate a contract award. Reset restores the initial fixture state.

Use session memory for this disposable prototype and disclose that reload resets it. Do not promise durable saves. Routes/history should restore navigation within the session without resetting state. Provide a visible reset confirmation when it would discard notes; it must cancel active replay timers too.

## Deep Research: bounded replay and precise templates

Keep “Simulated replay · saved sources · no live search” visible throughout. Stream short observable status events, not invented private reasoning or a fake live crawler log. Offer Pause, Cancel and Show complete example. A suggested replay uses six ordered stages over about 12 seconds; timing is presentation only, not evidence of work performed:

1. **Plan:** identity/scope, source classes, six risk categories, one follow-up maximum.
2. **Company sources:** load the saved report observations with original dates/page references.
3. **News:** “No news search performed in this saved fixture.” Never “No adverse news.”
4. **Public sources:** identify included official assurance pages; explicitly state registry/regulator coverage was not performed where applicable.
5. **Follow-up:** inspect the fixture's disclosed cybersecurity exposure and its saved assurance-process result. This is a disclosed exposure, not an established incident or fabricated red flag. State the stop reason and remaining supplier-specific gap.
6. **Synthesis:** limited-scope TLDR, compact fact card and linked report. Completed replay does not mean complete due diligence.

A run has an immutable run ID and bound entity ID. Starting another run, changing entity or resetting cancels the old run; late events cannot update the new entity. Cancel leaves a visibly partial report with covered and unreviewed sections. For simplicity, enable Add to suppliers only after a completed supported replay and entity-scope acknowledgement; canceled/unsupported runs cannot be added as researched records.

### Compact research fact card

Use this exact field order, showing “Unknown” rather than omitting gaps:

```text
Entity: [legal name] · [entity record ID]
Identity: [source-supported / user-confirmed scope / unresolved]
Scope: [legal entity / group / subsidiary; boundaries]
Country / website / registration identifier: [value + source, or Unknown]
Research: [saved replay / partial] · [report ID + revision]
Evidence dates: [covered period] · [source-check date]
TLDR: [≤3 sentences: observations, limitations, proposed next action]
Findings: [≤3 short claims, each with evidence label and source link]
Coverage gaps: [news / regulators / current status / qualification etc.]
Next action: [specific evidence needed; proposed owner]
System assignment: [buyer-selected demo association; not verified capability]
Actions: View risk report · Add to suppliers / Already added
```

The report expands this card into scope/identity, plan and coverage by source class, six category sections, evidence register, bounded follow-up, contradictions, unknowns and proposed actions. Each category may read “Not assessed”; no numeric company risk scores are generated. Each claim includes claim ID, exact entity scope, claim text, label (company-disclosed exposure, company-stated process, supported event, inference, or evidence gap), source IDs, document date, covered period, supporting page/section, and limits. Do not mark “supported event” unless the saved evidence actually supports one.

Each source entry includes ID, publisher, title, URL, publication date or unknown, source-check date, and page/section. A replay timestamp is not a fresh retrieval date. The existing fixture's parent/group statements and subsidiary-specific assurance guidance retain their distinct scopes. A stated process does not resolve the exposure or prove a supplier passed a control. An unresolved identity blocks entity-specific conclusions; names and shared domains alone do not merge records.

## Approval memo: one required route for every recommendation

“Approval request” is a document type, not an approval status. Choosing Recommend opens a draft keyed to the candidate and decision context. Every recommendation action, including Copilot suggestions promoted to recommendations, favorite cards, previously-used cards and research records, uses this route. A data answer such as “lowest financial risk” is not itself a recommendation. No one-click “reuse approved” shortcut.

Use one preview/print document model, with a concise first page and evidence appendix when necessary:

```text
APPROVAL REQUEST — DRAFT / NOT APPROVED
Memo ID · revision · prepared date · preparer · intended reviewer
Decision context: project, train system, component need, decision sought
Recommended candidate: stable ID, display name, identity/provenance type
Relationship: favorite / previously used / neither; history provenance
Proposed disposition: further assessment / conditional shortlist / do not proceed
Rationale: why this candidate; key trade-offs; buyer-authored judgment
Alternatives: considered candidate IDs, differences, rejection/defer reasons
Selection basis: comparison-set snapshot, criteria, ranking, exclusions
Risk facts: supplied total + six derived axes or Unknown; mapping version
Operational facts: delivery, confirmation, PO exposure; units and limitations
Evidence: CSV hash + row/columns; linked report ID/revision + source references
Unknowns: identity, technical fit, qualification, capacity, price, lead time,
          freshness and any unassessed research areas
Required checks/mitigations: action · owner · due date · evidence needed · status
Requested reviewer decision: pending; reviewer comments blank
Scope statement: demo associations; saved research; no qualification or award
```

Require a candidate, context, rationale, disposition, preparer and a next action before marking the draft ready for review. Missing reviewer/owner/date stays explicitly Unassigned/Unscheduled and prevents a “ready” claim; users may still preview and print an incomplete document marked INCOMPLETE DRAFT. No alternative is acceptable only with a recorded reason. Reused suppliers must state the applicability and freshness of prior evidence; history alone cannot waive checks.

Printing invokes the browser print dialog; label “Print / Save as PDF,” not “PDF saved.” Cancellation must not change approval or export status. Print layout removes navigation and the assistant, expands clipped evidence, preserves source URLs, repeats meaningful headers, and avoids splitting short fact cards. Preserve complete appendix content for twenty candidates rather than compressing everything into unreadable one-page output. A report link alone is insufficient offline: include material claims, sources and scope in the memo appendix.

## State invariants and invalidation

- Catalog membership, primary-system assignment, favorite status, previous-use history, comparison set, active research run and recommendation draft are independent state. Use stable IDs, never card position or display name, for joins.
- A research entity has one catalog record; rerunning research creates a report revision, not another supplier. User confirmation can establish intended scope, not verified legal identity or a mapping to an anonymized row.
- Compare contains unique IDs, at most twenty; removing a preferred candidate clears or explicitly invalidates that recommendation. A newly added unscored record can be compared but shows Unknown and cannot win numeric ranking.
- Numeric answer dependencies include snapshot, metric and queried IDs. Changing those marks the answer stale or recomputes it. An explicit-ID answer need not be discarded solely because unrelated filters change; its scope must remain visible.
- Memo revisions snapshot context, candidate set, criteria, evidence/report revisions, mapping version and rationale. Changing a dependency makes an existing ready draft stale and requires regenerated preview. Pure navigation does not. Favoriting alone does not alter risk or recommendation; if printed relationship metadata changes, regenerate that part of the memo.
- Editing discovery filters after creating a memo does not rewrite the historical selection basis silently. Offer an explicit update from current exploration. Preview and print always use the same memo revision.
- Adding a research record updates catalog and system counts in one state transition. It never changes source-score means. Changing its system decrements the old and increments the new once. All labels use the same definitions on overview and Discovery.

## Acceptance checks for implementation review

These are proposed checks, not executed results of this document-only review.

1. At the target desktop viewport, the collapsed overview fits without a supplier table or content hidden behind Copilot. At narrow width/200% text zoom, content remains reachable. Keyboard users can select every train system without manipulating 3D geometry.
2. Count sums equal catalog total. Adding the saved entity increments total and its system once; duplicate clicks/replays do not. Cancel/research-only completion/favorite/compare/memo actions leave counts unchanged. Reset restores original totals and discards pending events.
3. Recompute each radar axis from exact source fields; verify equal weights, fixed axis order, units, missing-value rules and denominator. Adding an unscored company leaves numeric means unchanged. No unknown value displays as zero or green.
4. The challenge financial answer returns 53 / 54 / 65 for the correct IDs, with cell provenance and the original source hash. The derived Financial axis is not substituted for Financial_Health_Score. High-total explanations admit unknown weights.
5. Select twenty across pages and filters; the twenty-first is blocked visibly. Hidden selections remain visible in the tray/count. Removing one frees precisely one slot. Empty results do not clear selections; ties sort consistently.
6. Rename an unsupported research query, cancel at every replay stage, start another entity, navigate away/back, and reset mid-run. No late Siemens claim lands in another entity's view. News gaps never become “no negative news.”
7. Add a supported report, open its catalog card and report link, and verify IDs, scope and report revision agree. An entity's parent/subsidiary distinction survives in card, report and memo. An unknown company never acquires source scores or an anonymized identity.
8. Recommend once from a new supplier and once from a previously-used card. Both require the same memo fields and review flow. Favorite and usage tags never suppress unknowns or checks.
9. Edit rationale, context, comparison membership and report revision after preview; each relevant change makes the prior ready draft stale. Back/forward navigation and opening sources do not erase it. Preview/print contain the same revision.
10. Inspect print preview for a one-candidate memo, a twenty-candidate appendix, long URLs and a research-only candidate. All claims retain evidence/scope, no content is clipped, Unknown remains explicit, and canceling print never marks a request approved or a PDF saved.

## Main pitfalls to reject at review

Reject a photorealistic train that implies engineering-accurate part coverage; system counts masquerading as qualified capacity; synthetic previous-use tags presented as real history; a radar that silently invents an overall risk model; an unscored company winning a ranking; and twenty radar overlays.

Reject live-looking research claims without real retrieval, blanket “no adverse news,” copying Siemens findings to unsupported names, merging corporate entities by string similarity, and adding a company as if it were qualified. Reject global report state that overwrites a previously added supplier's dossier.

Reject an attractive PDF without candidate identity, revision, source dates, material evidence, unknowns and actionable follow-up. The success criterion is a buyer being able to trace a recommendation back to the exact evidence and assumptions while every screen tells the same state story.
