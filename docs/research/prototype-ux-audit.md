# Prototype UX audit

Audit date: 18 October 2026. Reviewed `origin/prototype/supplier-workbench` at commit `d2fcb1b` across variants A, B, and C at 1280×800 and 390×844. The review included the rendered UI, accessibility tree, repository review record, template logic, and exported-flow behavior described in the branch. This is a heuristic and expert review, not target-user validation or an accessibility conformance claim.

## Overall assessment

The prototype has a unusually strong truthfulness baseline for a hackathon: it uses all 10,000 records, preserves exact values and source labels, exposes cell provenance, separates anonymized data from real-company research, abstains on unsupported qualification questions, labels simulated behavior, and exports a reviewable artifact.

The principal UX risk is no longer feature feasibility. It is **cognitive structure**: the prototype tries to demonstrate discovery, comparison, assistant, research, decision, export, three layouts, and nine guided demo steps in one disposable page. The next iteration should reduce repeated controls and make the recommended path clearer without hiding evidence.

## Dataset-driven design observations

- 10,000 unique IDs and 10,000 unique generated names make exact ID search and selection persistence essential.
- The dataset has 19 risk measures including total risk, four operational percentages/amounts, and two categorical supply-chain fields. A flat “show everything” default would overload comparison.
- Total-risk distribution is concentrated in High (4,813) and Medium (4,485), with only 318 Low and 384 Critical records. Color labels alone therefore provide weak discrimination; numeric ranking and focused dimensions are necessary.
- Risk labels consistently use Low 0–24, Medium 25–49, High 50–74, Critical 75–100. Total risk does not reach the extremes in this snapshot (6–93), while individual scores do (0–100).
- Purchase-order exposure ranges from EUR 10,000 to EUR 50,000,000; delivery ranges 65.48–100%; confirmation ranges 61.47–100%. Formatting, units, and separation from risk scores matter.
- Total risk is most correlated in this dataset with operational resilience, quality, sub-tier visibility, digital security, and financial risk. These correlations do not reveal the unpublished aggregate formula and must not be presented as causal weights.

## What should be preserved

1. The visible “lower = lower risk” legend.
2. Numbers plus source labels, not color alone.
3. Persistent selection across filters and layouts.
4. A hard 20-record cap that never silently removes a record.
5. Exact source-cell dialog with row, column, definition, and snapshot hash.
6. Clear separation between risk scores and operational percentages.
7. Unsupported-answer abstention and named missing data.
8. Separate real-company identity and sourced dossier.
9. Editable dictation before explicit submit.
10. Buyer-owned rationale, draft invalidation, and provenance-rich export.

## Variant assessment

| Variant | Strengths | Risks | Best use hypothesis |
| --- | --- | --- | --- |
| A — Data workbench | Efficient scanning; filters, table, and assistant visible together; familiar to spreadsheet-heavy users | Long result table pushes assistant context away; dense first impression; main action hierarchy competes with demo controls | Primary discovery workspace for frequent users |
| B — Guided sourcing | Strong orientation, visible stage sequence, clear working-state summary | Large rail consumes width; linear framing may feel slow; later-stage evidence is less visible while exploring | First-run guidance and occasional reviewers, not necessarily a permanent mode |
| C — Comparison review | Evidence and trade-offs lead; values align well across suppliers; direct recommendation path | Starts from a seeded shortlist, so discovery is less obvious; repeats CSV/export actions; longest page; horizontal matrix on mobile | Primary compare/review surface after candidate selection |

## Findings by severity

### High — fixed layout switcher can obscure working content

The A/B/C switcher is fixed at the bottom center. At 390×844 it overlays the comparison card and can cover controls or the current keyboard focus. This conflicts with WCAG 2.2 focus-not-obscured intent and is not part of the product workflow.

**Recommendation:** keep the switcher only for research builds. Move it into a non-fixed prototype toolbar or ensure the page reserves its full height and focused elements scroll above it.

### High — variant C duplicates primary export actions

Variant C shows “Export shortlist CSV” and “Download shortlist CSV” in adjacent header/state areas, followed by “Compare 3” even though the comparison is already present. This weakens hierarchy and makes actions appear inconsistent.

**Recommendation:** one compact action group: `Edit shortlist`, `Write recommendation`, and an `Export` menu or secondary action. Keep the comparison count as status, not another action when already on the comparison view.

### High — long pages separate cause, evidence, and action

At desktop the rendered content heights were approximately 2,556px for A, 2,673px for B, and 3,479px for C. Variant C reached roughly 4,637px at 390px width. Long pages are not inherently wrong, but the user loses selection status and the relationship between comparison evidence and final rationale.

**Recommendation:** use stage-level pages or anchored sections, a compact sticky workspace header that does not obscure focus, and a decision summary adjacent to the comparison. Paginate/virtualize production result tables; do not render a 25-row discovery table above every later task.

### High — qualification warning is accurate but not yet a workflow gate

Warnings say capability and qualification are unknown, but the decision form can still feel like a direct selection step. A user may export a preferred supplier without choosing how the missing evidence will be resolved.

**Recommendation:** require at least one next action or explicitly accepted gap before recording the draft. Keep the status “Early-risk shortlist,” and show qualification as `Unknown`, never pass/fail.

### Medium — seeded state may bias evaluation

All variants begin with three challenge suppliers selected. This is useful for a two-minute demo but bypasses discovery and may make variant C look more immediately useful.

**Recommendation:** maintain two entry states: `Guided demo` with seeded records and `New analysis` with an empty shortlist. Usability tests should include both and clearly separate time-to-value from discoverability.

### Medium — hierarchy contains repeated orientation layers

Masthead, hero, project-context card, demo disclosure, tabs/rail, state strip, card heading, and footnote all precede or repeat context. Each element is defensible, but together they delay the working surface.

**Recommendation:** after first-run orientation, collapse the hero into a workspace header: decision title, status, data version, selection count, and primary next action. Keep the prototype/live label persistent but compact.

### Medium — expert and occasional-user modes are implemented as whole-layout variants

The three variants duplicate large parts of the product. In production this could create inconsistent behavior and expensive maintenance.

**Recommendation:** test whether a single architecture with optional onboarding, persistent stage status, and role-focused defaults serves both groups. Retain multiple concepts only until evidence selects reusable patterns.

### Medium — assistant scope is textual, not structurally constrained in the UI

Variant A correctly states scope and the deterministic engine abstains, but a free-form composer still invites unsupported questions. Users may interpret repeated abstentions as low capability.

**Recommendation:** show supported question examples derived from current selection, make scope visible beside the composer, and route unsupported questions into named missing-data or company-research actions.

### Medium — source evidence is excellent but deep

Exact cell provenance is available through values, details, evidence toggles, and dialogs. The number of routes may make users unsure which evidence view is canonical.

**Recommendation:** standardize one evidence pattern: click a value to open an evidence drawer/dialog; answers link to the same object. Use progressive disclosure for file hash and physical column details.

### Medium — mobile is technically responsive but not task-optimized

The page does not create global horizontal overflow, and the matrix scrolls internally. However, the 390px layout retains dense desktop information, duplicates actions, and produces very long vertical navigation. Mobile may be a review surface rather than the primary analysis device.

**Recommendation:** validate real device use. If mobile is secondary, support review, comments, and approval context first; optimize large-scale discovery and 20-column comparison for desktop rather than claiming parity.

### Low — small text and compact controls need measured accessibility review

Several labels are 11–12px and many buttons are 30px high. They may meet some minimum criteria but can be uncomfortable under zoom, touch, or low-vision conditions. Siemens iX recommends at least 24×24px targets and demonstrates larger targets for mobile.

**Recommendation:** use a 14px minimum for supporting UI where space permits, 16px for body/input text on narrow screens, and 40–44px primary touch controls. Verify actual contrast and spacing rather than relying on visual inspection.

### Low — no skip link is visible in the template

The page has semantic banner/main/navigation areas but a keyboard user must traverse repeated header and prototype controls.

**Recommendation:** add a skip link to the current main task and preserve logical focus after rerenders.

## Recommended product direction for testing

Do not ship any variant unchanged. Prototype one hybrid:

1. Compact workspace header with decision title, dataset version, draft status, and selection count.
2. Persistent destinations: Candidates, Compare, Research, Recommendation.
3. A-style candidate table and contextual supported-question panel.
4. C-style comparison matrix as the default after selection.
5. B-style progress summary only for first run or a guided-demo mode.
6. One consistent evidence drawer/dialog across tables, answers, and research.
7. One action hierarchy per page; remove prototype-only controls from production views.
8. Desktop-first analysis with an intentionally scoped mobile review experience.

## Validation backlog

| Priority | Question | Method |
| --- | --- | --- |
| P0 | Do buyers understand risk versus qualification? | T1/T5 moderated comprehension tasks |
| P0 | Can users find, compare, verify, and export without help? | End-to-end usability test |
| P0 | Is keyboard/AT operation complete after dynamic rerenders? | Manual keyboard and screen-reader audit |
| P0 | Which layout patterns improve factual accuracy? | Balanced A/B/C concept test |
| P1 | Which metrics deserve default visibility by role? | Artifact-led interviews and card sort |
| P1 | Is company research one journey or a linked dossier? | Concept comparison with specialists |
| P1 | Does voice solve a recurring problem? | Contextual inquiry and terminology benchmark |
| P2 | Is mobile analysis necessary? | Device/environment survey plus field observation |

The full protocol and decision thresholds are in [ux-research-plan.md](ux-research-plan.md). The product requirements are in [ux-strategy-and-requirements.md](ux-strategy-and-requirements.md).
