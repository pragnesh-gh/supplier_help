# Train sourcing overview — prototype v2

Design question: can a buyer start with a train system, understand risk, investigate a company and prepare a consistent approval request without a table-heavy landing page?

## Scope

Frontend-only, deterministic and resettable. Preserve the first prototype. Build the next iteration on `prototype/train-risk-v2`. The user has selected a direction; focus on one coherent new design instead of producing three unrelated alternatives again.

## Proposed experience for review

- Compact desktop overview: navigation, scope/counts, interactive three-dimensional train assembly, selected system summary, six-axis risk profile, a few relevant supplier cards, and a compact Sourcing Copilot entry point.
- Hover or keyboard-focus a train region for supplier counts; click to select system. Keep selection accessible through labelled system controls too. Train geometry is illustrative, not an engineering model.
- Discovery is a separate screen with search, filters, sorting, pagination and compare selection capped at 20. Compare uses small multiples or a readable matrix; never stack 20 radar polygons.
- Supplier favorites and previous-use tags are explicit demo metadata; neither means qualified. Preserve selection while navigating.
- Sourcing Copilot defaults to questions answered from the supplied data. Deep Research opens a clearly simulated investigation with progressive status events, plan, source classes, follow-up, and a fixed summary template.
- The saved real-company example keeps its source links and dates. Unsupported names do not inherit its findings. Add to suppliers creates a separate research-derived record, associated with a selected train system, and updates counts. Unknown scores stay unknown and are excluded from numeric aggregates.
- Risk report and approval request are separate templates. Both support in-app viewing and browser print/save as PDF. Approval request always includes scope, recommendation, alternatives, evidence, unknowns, qualification checks, mitigation owners, reviewer and decision status. Previous use never bypasses this.
- Offer a short guided journey with visible next actions and a reset, plus unrestricted exploration.

## Data rules

Keep the original 10,000-row CSV unchanged. Produce a genuinely augmented derivative with reproducible synthetic part/system assignments and demo relationship metadata. Publish the allocation method and show that these fields are illustrative.

Source scores use 0 = no risk, 100 = maximum risk. The six proposed radar axes are derived summaries with disclosed prototype weights; source Total Risk Index is preserved, because its original weights were not supplied. Exact column mapping is pending the bounded research review.

## Parent research decisions

The bounded research and adversarial review are complete. The parent reopened the ERA LOC&PAS guide and Alstom component portfolio, confirming support for the subsystem taxonomy, not for market shares or supplier assignments. Adopt the ten regions, exact synthetic quotas, stable SHA-256 allocation and weighted axis mapping in `research/train-parts-and-radar.md`. The review's equal-weight alternative is not selected: the weighted heuristic is disclosed prominently as a prototype assumption. Do not override the three challenge IDs into one system; the financial example queries them explicitly across the catalog and states that scope.

Adopt the review's separate catalog / comparison / favorite / research / memo states, unknown-score exclusion, duplicate-add protection, and shared approval template for reused and new suppliers. Keep implementation appropriate to a throwaway prototype: show an incomplete draft honestly rather than build an approval backend. One coherent v2 layout is the user's requested iteration; retain v1 as the alternative for comparison.

## Review sequence

Bounded primary-source research and adversarial design review → Opus 5.5 pre-implementation review → Sol implementation with separated file ownership → browser journey checks → Opus 5.5 visual review → corrections and handoff.

## Final pre-implementation decisions (supersede preliminary choices above)

Adopt Opus B1–B8. Use nine regions by merging wheels/axles into `bogie_structure` (2,000 records); keep the other quotas. Use quota-preserving swaps to put the three challenge-example IDs in doors, and record each swap. Use `radar-v1-equal`: equal weights within each of the six axes, with exact source columns from the research. Original Total Risk Index remains unchanged. The decision changes the preliminary ten-region/unequal-weight choice because it improves hit-target clarity and avoids unexplained numerical emphasis.

Overview radar: focused supplier polygon over the system P25–P75 band and median, with accessible numeric values and mapping details. Every financial answer distinguishes supplied Financial_Health_Score from the derived Financial axis. Research has its own route and explicit replay controls. Both report types use one print root each from the same preview model.

### Shared implementation contract

- Data/build owner: `scripts/augment_dataset.py`, `scripts/build_v2.py`, `docs/supplier_risk_dataset_augmented.csv`, `docs/train-demo-v1.manifest.json`.
- UI owner: `prototype/train-workbench-v2.template.html` (all app CSS/JS, except train renderer).
- Train owner: `prototype/v2/train-scene.js`, `prototype/v2/vendor/three.module.min.js`, license.
- Build output: `prototype/train-risk-v2.html`, fully offline, all source rows embedded. Template tokens: `__DATA_PAYLOAD__` in an application/json script with id `prototype-data`; `__TRAIN_MODULE__` in a module script.
- Payload: `{columns: string[], rows: array[], source: string, sha256: string, manifest: object}`. Original numeric fields and derived risk fields are numbers; demo booleans are booleans. Manifest has `regions: [{id,label,shortLabel,quota,parts:[{id,label}]}]`, `axes: [{id,label,field,components:[{field,weight}]}]`, source/augmentation hashes, version, overrides and provenance. Axis ids: financial, legal, country, people_safety, operations, reputation; appended axis fields are `risk_` + id.
- Train module is the vendored r170 single-file module followed by renderer code. It exposes `window.TrainScene.mount(container, {regions,counts,selected,onSelect})`, returning `{update({counts,selected}),highlight(id),resetView(),destroy()}`. Counts keyed by region id with `{total,scored,researchOnly}`. Renderer uses the vendor module's in-scope class bindings directly and owns tooltip/fallback. UI provides labelled region buttons and initializes on DOMContentLoaded (after module execution).
- App data and state remain in memory. No API calls, no persistence, no runtime network assets. Preserve v1 and `.env`.
