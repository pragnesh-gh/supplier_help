# Prototype v2 verification record

Status: complete frontend prototype; browser and print checks passed. Review date: 18 October 2026.

## Required evidence

| Requirement | Evidence to collect |
|---|---|
| Original source preserved | Git diff and original SHA-256 match |
| Augmented dataset | 10,000 rows, original values/order, nine quotas, valid parts, 500 favorites, 1,500 prior-use tags, logged swaps, reproducible output |
| Radar correctness | Six equal-weight mappings recomputed against CSV; explicit 0–100 higher-risk direction; financial distinction; nulls excluded |
| Compact overview | Screenshots and overflow measurements at 1440×790, 1366×640 and 1536×730; narrow viewport accessibility |
| Interactive 3D train | Actual WebGL rendering, hover counts, select, orbit/reset, keyboard alternative and fallback |
| Discovery and comparison | Filters/sort/page; 20-selection limit across pages; remove/re-add; unknowns and preserved selections |
| Copilot | Exact financial example, high-risk explanation with unknown total weights, unsupported-query abstention |
| Research | Planning and observable stage events, pause/cancel/reset safety, unknown-company isolation, dated source links and coverage gaps |
| Add company | Scope/system selection, one new research-only record, count updates, duplicate protection, unchanged numeric aggregates |
| Report templates | Consistent risk report and approval request; previous-use candidate follows same flow; source facts, unknowns, rationale, alternatives and follow-ups |
| PDF path | Same preview/print content; readable actual PDF; draft/limited-scope labels, full source URLs, no app chrome |
| Demo and reset | Complete guided flow and free navigation; reset cancels timers and restores all initial state |
| Offline and integrity | file:// opens; embedded library/data; no API requests or credentials; clean application console |
| Final Opus review | New delegated review round of actual rendered UI; findings resolved and rechecked |

## Preflight evidence

The parent read the original data and research, reopened ERA and Alstom taxonomy sources, and reviewed the completed Opus 5.5 pre-implementation report. The final brief records decisions resolving its taxonomy/weight concerns. Parent recomputation confirmed system means cluster around 50 with risk-independent synthetic assignments. The new design therefore focuses on supplier profiles relative to system distributions.

T3 collaborative preview opened v1 but snapshots failed twice with `Preview automation snapshot timed out after 15000ms.` The Playwright CLI is the documented browser fallback for this session. The local server serves only `prototype/` on port 8765; it does not serve repository credentials.

## Data verification completed

The original dataset audit passed and Git reported no original CSV/audit difference. The parent independently read source and augmented CSVs, compared every original cell in row order, and recomputed all 60,000 derived axis values using an independent arithmetic-mean calculation. All matched.

The three challenge suppliers belong to Doors. Their supplied Financial_Health_Score values are 54, 65 and 53; derived Financial values are 55.5, 61.5 and 64.5 respectively. The manifest logs two required quota-preserving swaps (SUPP_00012 with SUPP_04110, SUPP_00731 with SUPP_05037); SUPP_00450 already belonged to Doors. The generator also checks all nine quotas, allowed part membership, 500 favorites, 1,500 previous-use flags and deterministic regeneration.


## Interaction verification

Independent browser QA matched CSV-backed filter counts: 500 favorites, 1,500 previously-used records, intersection 68, and Doors + High + delivery at least 90 = 140. Pagination, sorting, cross-page 20-record cap and removing/replacing a selection passed. Favorites update immediately and reset restores the original session.

The parent exercised a complete six-stage research replay, pause/resume, cancellation, entity edits and unsupported-company isolation. Scope acknowledgement is required before adding. Adding Siemens AG creates exactly one separate unscored record: catalogue 10,001; Doors 701 total / 700 scored / 1 research-only. Numeric system statistics remain unchanged and repeated add is idempotent. Its detail has Unknown scores and no numeric radar polygon.

The financial source answer distinguishes the supplied metric from the derived axis. Research reports retain source scope, dates, claim limits and unsearched categories. No live news crawl is claimed.

Independent file:// opening initialized all 10,000 records, nine system buttons and the actual train canvas with only the local HTML request. Python syntax checks passed. The final browser session had zero console errors or warnings.

## Visual review response

Opus 5.5 reviewed the rendered overview and research states and accepted with fixes (see opus-v2-final-review.md). The implementation now places TLDR, concise statistics, risk-report action and acknowledged add controls at the top of research results. While running, the centre progressively reveals evidence; idle controls are simplified and Start is disabled during a run. Radar labels include focused values and omit the centre zero. Train framing uses projected bounds; independent hover probes passed all nine regions including bogies at large and compact canvas sizes. Drag and click are distinct, and keyboard/SVG fallback remains available.

The main overview is checked at 1440x790, 1366x640 and 1536x730, with a vertically stacked mobile layout at 390x844. Original final-review clipping was reduced, then remaining small supplier-strip overflow was corrected in a final shared layout pass. Research remains a scrolling workspace, with primary results/actions visible at 1440x790.

## Deliberate limits

This is disposable interaction code, not buyer-validated production software. Relationships, component assignments and allocation quotas are synthetic. Original Total_Risk_Index weights are unavailable; derived radar axes use documented equal weights. Research is a saved Siemens AG fixture with explicit source gaps. New records are unscored. State is memory-only and reload resets it. Browser print opens the user's print/save dialog; it never marks an approval complete. Speech and live model/research integration remain later work.


The revised eight-step guide was exercised through system selection, Doors discovery, three-example comparison, exact financial answer, research replay, risk report, previously-used candidate review and memo preview. It does not bypass research acknowledgement or simulate a completed print. A reported immediate-Clear filter race was fixed and retested for both text and numeric inputs.


Final compact-layout measurements: body scroll heights exactly matched the viewport at 1440x790, 1366x640 and 1536x730. Supplier-strip content fits (180/182px at normal desktop and 160/162px compact); Copilot content fits. At 390px width there is no horizontal overflow; the page scrolls vertically as intended. Screenshots were visually inspected.


## Final print verification

Real DOM entry exposed and fixed a blur-triggered memo rerender that could lose the next click. The memo now updates its preview without replacing the form. The reused-source and newly researched candidate forms were filled through the same required fields and remained Draft / not approved after becoming Ready for review. Actual Print controls invoked the shared print model.

Chromium A4 PDFs were generated for the research report (3 pages), previously-used supplier request (4 pages, including all source cells) and research-added candidate request (3 pages, including linked claims and source URLs). The parent rendered and inspected every page. A fixed print header had overlapped content; it now flows normally. Final output is readable, with no overlapping header or app chrome. PDF artifacts and screenshots are local QA output under ignored output/playwright; the HTML produces fresh PDFs through the browser.

Verdict: the requested compact train-led design and end-to-end deterministic workflow are ready for interaction review. It is not a validated purchasing recommendation. Retain on the throwaway prototype/train-risk-v2 branch; buyer feedback should precede production implementation.


## UI-reference integration

Merged origin/main through a468710, including three docs/ui-ux folders and UX research. explore_supplier supplies the card-grid and delivery-sparkline inspiration. compare_vendors/code.html and supplier_profile/code.html are byte-identical supplier-profile exports, despite the folder names.

Adopted selectively: a separate My suppliers route, Favorites / Previously used / Both collections quick filters, search, nine-item pagination, Cards / Trend rows views, and inline trends in the existing comparison matrix. The train overview remains compact. All actions share existing favorite and comparison state, including the 20-record cap.

History is a deterministic synthetic 12-week example only for demo previously-used suppliers. Each chart is labelled illustrative; favorites alone do not create history. Research records and other suppliers show History unavailable. Charts share a 0-100 percent scale, open a larger focusable-point chart and accessible values table, and never enter source data, scoring, ranking or memo evidence. No real company identities or certification claims from the references were copied onto anonymized supplier IDs.

Browser checks passed: used collection count1500, history dialog12rows/no NaN coordinates, cards/rows selection persistence, comparison charts for selected records, exact-ID search, empty search results, mobile cards without horizontal overflow, and compact overview at1440x790. Cards and rows screenshots were inspected. Telemetry remains unimplemented.

### Later telemetry option

A later supplier-monitoring feed could retain dated delivery/quality snapshots and explain changes with event timestamps, provenance and last-successful-refresh state. Research execution could separately expose stage progress, source-fetch outcomes and elapsed time. Neither should be represented by a decorative Live badge: freshness and connection failures must be visible. This proposal needs real ERP/QMS or research-run events before it can power real trends; no such integration is included here.
