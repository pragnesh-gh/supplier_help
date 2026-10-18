# UX strategy and product requirements

Research baseline: 18 October 2026. This document turns the repository, supplied dataset, prototype, and primary-source desk research into an end-to-end experience strategy for the hackathon. It is a product hypothesis until target buyers validate it.

## Executive decision

Build a **decision workspace, not a chatbot and not an autonomous supplier selector**. The core value is helping a procurement professional narrow 10,000 anonymized risk records into a reviewable shortlist while preserving source evidence, trade-offs, unknowns, and human accountability.

The current prototype already proves that the data can support search, filtering, comparison, exact answers, a separate company-research fixture, and export. The next design iteration should combine:

- variant A's efficient candidate discovery;
- variant C's evidence-first comparison;
- variant B's visible progress and orientation for occasional users.

This hybrid is a testable hypothesis, not a selected design. Buyer research must determine whether users prefer one persistent workspace or a staged flow.

## Challenge in one sentence

Help a buyer make a faster, more defensible **early-risk shortlist** without implying that a risk score establishes technical suitability, qualification, Ready-for-Business status, contract approval, or a real-company identity.

## Product boundary

### The product supports

1. Defining buyer-entered sourcing context.
2. Exploring and ranking only fields present in the supplied snapshot.
3. Selecting and comparing up to 20 anonymized records.
4. Asking grounded questions whose numerical results are computed from validated data.
5. Inspecting the exact source row, column, value, label, definition, and snapshot hash.
6. Researching a separately identified real company with dated, cited evidence.
7. Recording a preferred option, alternate, rationale, unknowns, and next action.
8. Exporting a portable draft for review in existing procurement tools.

### The product does not establish

- component capability, technical fit, capacity, lead time, geography, or unit price;
- supplier registration, qualification, cybersecurity assurance, or Ready-for-Business status;
- the unpublished weights behind `Total_Risk_Index`;
- a mapping between anonymized `SUPP_*` records and real companies;
- live risk status or trends from a snapshot with no as-of date;
- an award, approval, purchase order, or write-back to Siemens systems.

## Evidence available to design

| Evidence | What it supports | What it does not support |
| --- | --- | --- |
| 10,000-row CSV and metric dictionary | Search, supported filters, exact comparisons, source-linked evidence | Suitability, qualification, current events, or identity resolution |
| Siemens procurement publications | Role vocabulary, preselection/qualification boundaries, named Siemens-wide tools | The target team's exact workflow, licences, APIs, or preferences |
| Mobility job postings | Selected roles use supplier follow-up, SAP, Excel, and cross-functional coordination | Workforce-wide demographics or usage frequency |
| Existing offline prototype | Technical feasibility and a set of testable interaction models | Usability, adoption, or a winning layout |
| Siemens iX and W3C guidance | Accessibility and industrial-interface quality criteria | Compliance of the current prototype without testing |

The role and workflow evidence is documented in [buyers-and-workflows.md](buyers-and-workflows.md). Data and AI boundaries are documented in [models-speech-and-agents.md](models-speech-and-agents.md).

## Users without invented personas

Use **role-based archetypes** until interviews produce behavioral segments. Do not assign fictional ages, biographies, or motivations.

### Primary: procurement decision owner

Examples: Buyer, Commodity Manager, Project Procurement Manager.

- Goal: reduce a large candidate set to a defensible shortlist.
- Needs: fast scanning, explicit ranking logic, retained selection, evidence, and export.
- Risk: may over-trust a composite score or assume low risk means qualified.
- Success: can explain why a supplier remains on the shortlist and what must be checked next.

### Secondary: specialist reviewer

Examples: quality, engineering, cybersecurity, sustainability, finance, controller.

- Goal: inspect the dimensions relevant to their responsibility.
- Needs: stable IDs, exact values, definitions, citations, comments, and a narrow review view.
- Risk: receives a flattened recommendation that hides uncertainty or domain-specific red flags.
- Success: can verify a claim and add a review condition without rebuilding the analysis.

### Tertiary: approver or council member

- Goal: understand the recommendation, alternatives, evidence, and unresolved exposure.
- Needs: concise summary with drill-down, provenance, reviewer identity, and next action.
- Risk: interprets a polished AI summary as approval evidence.
- Success: can distinguish facts, buyer judgment, external findings, and missing evidence.

### Operational support

Examples: data steward, system administrator, audit/compliance reviewer.

- Goal: ensure source integrity, access control, traceability, and predictable failure.
- Needs: versioned imports, validation results, logs, permissions, and retention controls.

## Jobs to be done

### Core job

When I have thousands of supplier-risk records and a sourcing question, help me narrow the field and compare the meaningful trade-offs so I can create a reviewable shortlist without losing the source evidence or overstating what the data proves.

### Supporting jobs

- When a score looks surprising, show the exact cell and definition so I can verify it.
- When several suppliers are close, let me compare the dimensions that matter to the current decision.
- When the dataset cannot answer a question, say what is missing and turn it into a next action.
- When I research a real company, keep that evidence separate from anonymized supplier records.
- When I hand work to a reviewer, preserve the candidate set, criteria, rationale, uncertainty, and source version.

## Experience principles

1. **Evidence before eloquence.** Show values and sources before or alongside generated prose.
2. **Calibrated trust.** State capabilities and limits at the point where they affect a decision. Google PAIR recommends setting expectations early, tying explanations to user actions, and supporting correction rather than maximizing perceived confidence. [Google PAIR: Explainability and Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/)
3. **Risk is not qualification.** Every recommendation surface carries unresolved qualification and suitability status.
4. **Human judgment stays visible.** Separate source facts, system synthesis, external findings, and buyer rationale.
5. **Progressive disclosure.** Default to decision-relevant metrics; make all 19 risk measures and provenance available on demand.
6. **Stable context.** Shortlist, filters, ranking, notes, and research scope persist across the journey.
7. **Reversible actions.** Selection, filters, notes, and draft decisions can be changed; irreversible external actions are out of scope.
8. **Accessible by construction.** Keyboard, zoom, screen-reader, contrast, non-color status, and input-error behavior are release criteria.

## Recommended information architecture

| Area | Purpose | Primary object |
| --- | --- | --- |
| Decision brief | Define purpose, review date, owner, and buyer-entered constraints | Decision workspace |
| Candidates | Search, filter, rank, and build the shortlist | Supplier record |
| Comparison | Review selected suppliers and focused metrics | Comparison set |
| Ask | Ask supported questions and inspect calculation evidence | Grounded answer |
| Company research | Confirm a legal entity and review bounded external evidence | Company dossier |
| Recommendation | Record preference, alternate, trade-off, unknowns, and next action | Draft decision record |
| Export / handoff | Create a portable, versioned review artifact | Memo / CSV |

Use these as persistent destinations on wide screens. On narrower screens, use a compact step indicator plus a clear current-page title; do not force the entire task into one very long page.

## End-to-end journey and required states

| Stage | User question | Required experience | Failure or empty state |
| --- | --- | --- | --- |
| 1. Frame | What decision am I preparing? | Purpose, owner, review date, dataset identity, supported/unsupported facts | Missing context is allowed but labeled; do not invent component data |
| 2. Discover | Which records merit comparison? | Search, supported filters, sortable metrics, result count, retained selection | No results explains active filters and offers reset |
| 3. Compare | Where are the material trade-offs? | Pinned identities, focused dimensions, values plus labels, operational metrics separated from risk | Empty shortlist prompts selection; 20-cap preserves existing choices |
| 4. Explain | Can I verify this answer? | Deterministic result, scope, source cells, metric definition, caveat | Unsupported question names missing data and suggests a valid path |
| 5. Investigate | What public evidence exists about this real company? | Legal-entity confirmation, plan, progress, source dates, evidence status, contradictions | Ambiguous entity, no evidence, stale evidence, timeout, blocked source |
| 6. Decide | What do I recommend and why? | Preferred and alternate, rationale, unknowns, next action, reviewer | Prevent record/export when preference is outside shortlist or rationale is empty |
| 7. Handoff | Can another person review this? | Exported facts, provenance, criteria, notes, limitations, timestamps | Export error preserves work and offers retry |

## Comparison model

The default comparison should answer three layers in order:

1. **Orientation:** identity, total risk, sourcing risk, delivery, confirmation, and historical PO exposure.
2. **Decision-relevant dimensions:** user-selected or role-relevant metrics such as financial, quality, operational resilience, compliance, digital security, and ESG risk.
3. **Full evidence:** all risk metrics, operational fields, definitions, source cell, and provenance.

Do not use a radar chart as the primary comparison: it becomes unreadable with many suppliers and can visually imply a meaningful continuous shape. A matrix with sortable or focusable rows is more inspectable. Show the source label next to the number because the dataset defines thresholds. Preserve `0 = no risk; 100 = maximum risk` wherever positively named fields such as Financial Health or ESG appear.

## Grounded assistant behavior

The assistant is contextual support, not the product's home page.

### Answer contract

Every answer should contain:

- the question interpreted by the system;
- supplier IDs and comparison scope;
- exact metric and direction;
- exact result values calculated in code;
- source-cell links;
- limitations or abstention reason;
- an optional next action.

### Trust labels

Use labels users can act on:

- **From supplied data**
- **Buyer-entered**
- **Company-disclosed exposure**
- **Independent report / allegation**
- **System inference**
- **Evidence gap**
- **Simulated in prototype**

Do not show a generic “AI confidence” percentage beside supplier risk. Model confidence is not supplier-risk probability and may be misunderstood.

## External company research experience

1. Ask for legal name, website/domain, and country.
2. Show possible entity matches and require confirmation when ambiguous.
3. Preview the research scope, source types, page/time budget, and stop conditions.
4. Present findings as claims with publisher, document date, retrieval date, passage/page, entity match, and status.
5. Group contradictions and duplicates; one syndicated story is one underlying source.
6. Allow a buyer note, correction, exclusion, and bounded follow-up.
7. End with findings, gaps, and recommended checks—not a red/yellow/green company verdict.

## Accessibility and industrial UI requirements

Target WCAG 2.2 AA. Siemens Industrial Experience also states a WCAG AA ambition and calls for keyboard operation, non-color cues, predictable errors, programmatic status messages, zoom testing, and multiple input modes. [Siemens iX accessibility overview](https://ix.siemens.io/docs/guidelines/accessibility/overview), [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/)

### Required checks

- semantic landmarks, headings, forms, native controls, and table headers;
- skip link to main content;
- logical keyboard order and visible focus that is not hidden by sticky/fixed UI;
- all functionality available without drag or pointer precision;
- status changes announced without unexpectedly moving focus;
- text and component contrast tested in each state;
- risk conveyed by text/number as well as color;
- 200% zoom and 320 CSS-pixel reflow, with data tables scrolling inside a labeled region;
- touch targets at least 24 by 24 CSS pixels, with 44 by 44 preferred for primary mobile actions;
- dialog focus placement, trapping, Escape behavior, and return to the trigger;
- clear input labels, formats, validation, correction, and error summary;
- reduced-motion behavior and no auto-advancing content;
- VoiceOver/Safari and NVDA/Chrome manual smoke tests before release.

## Content rules

- Lead with the user's task: “Compare shortlist,” not model or technology names.
- Use “lower risk” rather than “better supplier.”
- Use “draft recommendation,” never “approved supplier.”
- Say “No evidence found within this search scope,” never “No risk.”
- Name missing facts and the action needed to obtain them.
- Keep one action per button. Siemens iX recommends explicit, consistent action labels. [Siemens iX button labels](https://ix.siemens.io/docs/guidelines/language/menu-functions-and-ui-labels/button-labels)
- Keep critical instructions persistent; do not hide them only in tooltips. [Siemens iX tooltip guidance](https://ix.siemens.io/docs/components/tooltip/guide)

## Prioritized product requirements

### P0 — hackathon-critical

- Versioned dataset ingestion and visible source identity.
- Search, supported filters, explicit numeric ranking, and reset.
- Persistent selection with a visible 20-record cap.
- Evidence-linked comparison and grounded answers.
- Separate real-company identity and research record.
- Unknown/unsupported states with no fabricated fallback.
- Editable recommendation with alternate, trade-off, gaps, and next action.
- Actual memo/CSV export with provenance and limitations.
- Responsive desktop workflow and baseline WCAG 2.2 AA behavior.
- Explicit “simulated” labels anywhere the prototype substitutes for live behavior.

### P1 — next implementation

- Saved workspaces, reviewer comments, and status history.
- Role-focused comparison presets that users can edit.
- Live bounded research with contradiction and stale-source states.
- Secure authentication, server-held secrets, rate limits, and recoverable errors.
- Optional editable dictation after terminology and privacy validation.

### P2 — only after validation

- Read-only SCM/SAP imports and source-record links.
- Component/BOM context and qualification gates.
- Trend monitoring from genuinely versioned data.
- Scenario weighting as a separate buyer preference model.
- Multilingual workflows and supplier-document review.

## Success framework

Google's HEART framework maps product goals to user-centered signals and metrics rather than optimizing only clicks or speed. [Google Research: HEART](https://research.google/pubs/measuring-the-user-experience-on-a-large-scale-user-centered-metrics-for-web-applications/)

| Goal | Signal | Hackathon metric / threshold |
| --- | --- | --- |
| Effective discovery | User finds and retains intended records | At least 5 of 6 moderated participants complete without moderator rescue |
| Correct interpretation | User understands score direction and boundary | All participants state lower score = lower risk and do not equate it with qualification |
| Evidence use | User verifies before recommending | At least 5 of 6 open one source cell and cite one trade-off in rationale |
| Safe AI trust | User recognizes support and abstention | All participants correctly identify simulated/live state and unsupported answer behavior |
| Efficient handoff | Reviewer can reconstruct the decision | At least 5 of 6 produce an export containing preferred, alternate, rationale, unknowns, next action, and source version |
| Accessibility | Critical flow is operable across modes | No critical keyboard blocker; no WCAG A/AA automated violation accepted without documented exception |

The sample is formative, so thresholds guide iteration rather than prove statistical generalizability.

## Decisions still requiring user evidence

1. One workspace versus guided stages.
2. Which 5–8 metrics buyers need by default for each decision type.
3. Whether company research belongs inside the same workspace or a linked dossier.
4. Whether voice input is useful and socially acceptable in the actual work environment.
5. Preferred export format and required approval metadata.
6. Which existing system is the source of truth and what read/write integration is allowed.
7. Required languages, devices, browser constraints, retention, and access controls.
