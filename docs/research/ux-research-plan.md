# End-to-end UX research plan

Prepared 18 October 2026 for the Supplier Help hackathon. This plan covers discovery, concept evaluation, usability testing, accessibility validation, and post-demo learning. It intentionally separates what desk research established from what must be learned from people.

## Research objective

Determine whether procurement professionals can use the proposed workspace to create a correct, evidence-backed, reviewable early-risk shortlist—and which interaction model best supports expert efficiency, occasional-user orientation, and trustworthy AI assistance.

## Current research maturity

| Activity | Status | Evidence |
| --- | --- | --- |
| Challenge and dataset audit | Complete | 10,000 rows, 46 columns, definitions and limitations checked |
| Domain/process desk research | Complete | Siemens roles, tools, supplier-process boundary, rail cybersecurity context |
| AI/speech feasibility research | Complete for prototype decisions | Deterministic baseline, Nemotron candidate, bounded research, simulated speech |
| Prototype feasibility review | Complete | A/B/C layouts exercised across the end-to-end demo |
| Target-user interviews | Not started | Requires access to buyers and reviewers |
| Moderated concept/usability study | Not started | This plan provides protocol and thresholds |
| Accessibility conformance review | Partial | Semantic inspection completed; manual AT and automated audit remain |
| Production telemetry / field study | Not applicable yet | Product is not deployed |

## Research questions

### Decision workflow

1. How do buyers currently reduce a large supplier set and document the rationale?
2. Which facts must be visible before a supplier can enter or leave a shortlist?
3. What makes a recommendation reviewable by engineering, quality, finance, and approvers?
4. Where do handoffs fail between spreadsheets, supplier tools, email, and meetings?

### Information architecture and interaction

5. Do users prefer a persistent workbench, a guided flow, or a comparison-first review?
6. Can users maintain context when moving from discovery to comparison, research, and decision?
7. Can users distinguish risk scores, operational percentages, sourcing risk, and qualification status?
8. Is comparing up to 20 useful, and how many records are typically compared closely?

### AI and trust

9. What questions do users naturally ask of the data?
10. Do source cells, definitions, and limitations create appropriate—not excessive—trust?
11. Do users understand why an unsupported question abstains?
12. Can users keep external company evidence separate from anonymized supplier records?
13. Is editable dictation valuable enough to justify privacy, accuracy, and implementation cost?

### Accessibility and environment

14. What devices, browsers, languages, assistive technologies, and workplace constraints matter?
15. Can keyboard, zoom, and screen-reader users complete the critical journey?

## Hypotheses

| ID | Hypothesis | Evidence needed | Decision |
| --- | --- | --- | --- |
| H1 | Expert buyers will complete candidate discovery faster in variant A than B | Task time, navigation errors, preference rationale | Keep A-style discovery if success is equal and median time is at least 15% lower |
| H2 | Variant C will improve comparison comprehension | Correct trade-off identification and evidence opens | Use C-style matrix if at least 5/6 identify the same factual trade-offs without help |
| H3 | B-style progress cues help occasional reviewers orient themselves | Wayfinding errors and perceived confidence | Add compact progress cues if they reduce wrong-destination actions without slowing experts materially |
| H4 | Persistent source access prevents score-direction errors | Score interpretation and source-cell task | Redesign labels if any participant treats high Financial Health or ESG as favorable |
| H5 | Explicit gaps prevent false qualification claims | Recommendation language and debrief | Block release if any participant believes the tool qualified or approved a supplier |
| H6 | Evidence-first answers calibrate AI trust | Unsupported question, confidence, and correction behavior | Keep evidence adjacent; revise if users accept prose without checking or cannot find support |
| H7 | Voice is optional convenience, not a core need | Contextual inquiry and dictation test | Defer unless at least half of target users report a recurring use case and ID accuracy is acceptable |

These thresholds are pre-committed to reduce post-test preference bias. Small-sample findings remain directional.

## Method sequence

### Phase 1 — stakeholder alignment (60 minutes)

Participants: product owner, challenge/domain expert, engineer, designer/researcher, and data owner if available.

Outputs:

- agreed decision boundary and demo claim;
- stakeholder assumptions ranked by risk;
- confirmed recruitment access;
- known security, legal, dataset, and submission constraints;
- named decision maker for scope conflicts.

Exercise: each person independently writes what the product **does**, **does not do**, and what the jury must understand after two minutes. Resolve contradictions before design work.

### Phase 2 — generative interviews and workflow observation

Recruit 5–8 participants if access permits:

- 2–3 buyers / commodity managers;
- 1 project procurement manager;
- 1 quality or engineering reviewer;
- 1 finance/controller, cybersecurity, or sustainability reviewer;
- optionally 1 approver/council participant.

Prefer target Siemens Mobility roles. If unavailable, use enterprise procurement proxies and label the limitation; proxy preference cannot validate Siemens-specific workflow.

Session: 45–60 minutes, remote or in context. Ask each participant to bring a redacted recent supplier comparison or describe the last real case. Observe artifacts and sequence before asking feature questions.

Key prompts:

1. “Tell me about the last time you had to narrow several suppliers.”
2. “What triggered the work, and what information did you start with?”
3. “Show me how the candidate list changed.”
4. “Which number or document caused the most discussion?”
5. “What had to be true before you could recommend one supplier?”
6. “Who reviewed it, what did they challenge, and what did you send them?”
7. “Where did you leave the system to use a spreadsheet, email, or another tool?”
8. “What happens when evidence is missing or contradictory?”
9. “What would you never delegate to an AI assistant?”
10. “In what setting, if any, would dictation be preferable to typing?”

Do not ask users to design the screen. Ask about behavior, artifacts, decisions, errors, and exceptions.

### Phase 3 — synthesis workshop

Analyze observations into:

- workflow stages and handoffs;
- task frequency, consequence, and current effort;
- information objects and source-of-truth systems;
- behavioral segments rather than demographic personas;
- opportunity statements;
- updated assumptions and design hypotheses.

Tag every insight as `Observed`, `Reported`, `Desk evidence`, or `Team hypothesis`. Record participant count and counter-evidence. Do not convert one quote into a segment.

### Phase 4 — concept and usability evaluation

Run 6 moderated sessions of 45–60 minutes. A within-subject test of all three full variants would create learning and fatigue effects, so use a balanced approach:

- each participant completes the primary journey in one assigned variant;
- each then reviews the comparison and navigation model from the other two variants using short, non-overlapping tasks;
- rotate primary variants and secondary order across participants;
- do not reveal team preference or label variants “simple,” “expert,” or “best.”

Use the supplied challenge rows and reset state between tasks.

#### Scenario

“You are preparing an early risk-screening recommendation for a sourcing review. The data does not establish technical capability or qualification. Create a shortlist, investigate the evidence, and prepare a draft another reviewer could challenge.”

#### Tasks

| Task | Prompt | Observe | Pass condition |
| --- | --- | --- | --- |
| T1 Orient | “Before clicking, tell me what this tool can and cannot decide.” | Mental model, simulation awareness | Identifies early screening and at least one material limitation |
| T2 Find | “Find SUPP_00012, SUPP_00450, and SUPP_00731 and retain them for comparison.” | Search, selection persistence, cap comprehension | Correct three IDs selected without losing prior choices |
| T3 Compare | “Which has the lowest financial risk, and what trade-off would you raise?” | Score direction, matrix use, evidence behavior | Selects SUPP_00731 (53) and identifies a supported trade-off |
| T4 Verify | “Show where that number came from and when the data was current.” | Provenance discovery | Opens the correct source cell and states as-of date is unavailable |
| T5 Boundary | “Which supplier is qualified for railway door systems?” | Response to unsupported intent | Rejects qualification claim and identifies missing capability/qualification data |
| T6 Investigate | “Review the saved Siemens AG example. What is a finding, and what still needs supplier evidence?” | Entity separation, source status, historical scope | Does not map findings to `SUPP_*`; names at least one remaining gap |
| T7 Decide | “Choose a preferred and alternate, record the trade-off and next action.” | Rationale quality, human control | Rationale includes evidence, uncertainty, and actionable follow-up |
| T8 Handoff | “Export what a colleague would need to review your work.” | Export discovery and artifact completeness | Export contains candidates, criteria, rationale, gaps, and source version |
| T9 Recovery | “Remove a selected supplier after recording a draft.” | Stale-state prevention | Notices draft invalidation and can recover without losing unrelated work |

After each task collect:

- success: complete / complete with minor issue / failed;
- time on task;
- wrong turns and moderator interventions;
- critical interpretation errors;
- evidence opened or ignored;
- 1–7 ease rating and one-sentence reason;
- 1–7 confidence in explaining the result to a reviewer.

End with a comprehension check, preference rationale, missing-information question, and “What would stop you using this in real work?”

### Phase 5 — accessibility evaluation

Run before visual polish locks interaction patterns:

1. Automated WCAG scan on every major state, including dialogs and error states.
2. Full keyboard path for T1–T9 at desktop width and 200% zoom.
3. NVDA + Chrome and VoiceOver + Safari smoke tests.
4. Reflow at 320 CSS pixels; comparison table may scroll internally but page controls must remain reachable.
5. Contrast check for text, focus, inputs, risk labels, disabled state, and charts.
6. Reduced motion, browser text-spacing overrides, and high-contrast/forced-colors spot checks.
7. At least one session with a participant who relies on keyboard navigation or screen magnification if recruitment access permits.

W3C requires status messages to be programmatically available without stealing focus, which applies to result counts, selection limits, research progress, save state, and exports. [W3C status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)

### Phase 6 — pilot and demo validation

Use 3 people unfamiliar with the project:

- one follows the two-minute demo script;
- one intentionally asks unsupported questions and changes selections;
- one reviews only the exported artifact.

The demo is ready when all three can state the product boundary, the primary journey finishes within two minutes without hidden setup, and the reviewer can reconstruct the recommendation from export alone.

## Measurement scorecard

| Dimension | Metric | Release threshold for the critical path |
| --- | --- | --- |
| Task success | Unassisted completion of T2, T3, T4, T5, T7, T8 | At least 5/6 per task; 6/6 for T5 boundary comprehension |
| Correctness | Correct supplier, value, direction, and evidence | 100% for the financial-risk example |
| Safety | False qualification, identity mapping, or “no evidence = no risk” claim | Zero tolerated |
| Recoverability | Completion of T9 after state invalidation | At least 5/6 without moderator rescue |
| Evidence use | Opens source and includes a limitation in rationale | At least 5/6 |
| Efficiency | Median critical journey time excluding interview probes | Track baseline; target under 8 minutes after one orientation pass |
| Perceived ease | Post-task 1–7 ease | Median at least 5; no task median below 4 |
| Trust calibration | Correctly states live/simulated state and limits | 6/6 |
| Accessibility | Critical keyboard/AT blockers | Zero open critical blockers |

Do not optimize time if it reduces evidence inspection or increases false confidence.

## Analysis plan

1. Log task outcomes and events during sessions; do not rely on memory.
2. Write one observation per note with participant ID, task, timestamp, and evidence.
3. Affinity-group by user goal or breakdown, not by screen.
4. Rate issues:
   - **Critical:** wrong sourcing conclusion, inaccessible blocker, data loss, fabricated evidence, or unsafe identity mapping.
   - **High:** task failure or repeated workaround in a primary flow.
   - **Medium:** delay, confusion, or error with clear recovery.
   - **Low:** polish or preference without task impact.
5. Count participants affected, but preserve minority accessibility findings even when frequency is low.
6. Compare variants on success and errors first, time second, preference third.
7. Document disconfirming evidence and unanswered questions.

## Research operations and ethics

- Obtain informed consent for recording and note-taking.
- Do not request confidential supplier data; use redacted artifacts or the challenge dataset.
- Store participant identity separately from notes and delete recordings on the agreed schedule.
- Do not enter participant or company-confidential content into external AI services.
- Compensate external participants consistently where policy allows.
- Make accessibility accommodations part of recruiting and scheduling.
- Tell participants the AI, research, and speech behaviors that are simulated.

## Instrumentation for a later pilot

Collect event metadata without capturing supplier-confidential text by default:

- workspace created and data version;
- filter/rank change and result count;
- supplier selected/removed and cap reached;
- comparison metric expanded;
- source cell opened;
- question category, supported/unsupported outcome, and correction;
- research started, entity ambiguity, source opened, follow-up bounded, timeout;
- recommendation recorded/invalidated;
- export type and success/failure.

Never log raw voice, free-text rationale, credentials, or fetched document content into general analytics without a separate approved need and retention policy.

## Deliverables by hackathon milestone

| Milestone | Research deliverable | Product decision |
| --- | --- | --- |
| Before next design iteration | Stakeholder assumptions, interview notes, workflow map | Confirm boundary and primary roles |
| Before choosing layout | Moderated test scorecard and issue log | Select/hybridize A/B/C |
| Before live AI | Grounded-answer and abstention evaluation | Decide whether model adds value over deterministic UI |
| Before deployment | Accessibility report and fresh-session pilot | Approve demo and jury access path |
| After demo | Jury feedback and observed failure log | Prioritize production discovery or stop |

## Immediate next actions

1. Recruit at least one buyer, one project procurement role, and one specialist reviewer.
2. Confirm whether sessions may use the supplied dataset and whether recording is allowed.
3. Pilot this protocol internally once and remove leading prompts.
4. Run six balanced sessions; do not choose a layout from team preference alone.
5. Convert only repeated or high-consequence findings into design requirements.
