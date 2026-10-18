# Prototype v2: Opus 5.5 pre-implementation design review

Reviewed 2026-10-18. One bounded round, document-only. Nothing implemented. Inputs: [v2 brief](../prototype-v2-brief.md), [risk criteria](../risk_criteria_description.md), [company fixture](company-fixture.md), [adversarial challenge](prototype-v2-challenge.md), [train parts & radar](train-parts-and-radar.md), [v1 template](../../prototype/workbench.template.html), [v1 review](../prototype-review.md), [prior decisions](review-and-decisions.md). Both research notes were present and read. Their data mapping is **still pending parent vetting** because the notes conflict on two points (B1, B2).

One local check was run against the original CSV (read-only, Python stdlib). It informs B3 and B4 below.

## Verdict

**Proceed, with 8 blocking changes.** The direction works: train-first overview, a separate Discovery screen, Copilot defaulting to supplied data, Deep Research as a clearly labelled replay, and one approval-memo route for every recommendation. The challenge note's state invariants, journey, fact-card template and memo template are sound. Adopt them as written unless this review changes them.

The two biggest risks are not visual. (1) The headline radar would be meaningless as specified, because every system mean comes out at about 50 (B3). (2) The guided financial question and the "Financial" radar axis disagree for the same supplier (B4). Without fixing these, the polished overview tells a misleading story.

## Blocking changes

### B1. Resolve the train taxonomy: 6 systems vs 10 regions

The challenge note uses six systems (doors, bogies, traction, braking, interior, control). The train-parts note uses ten regions with quotas. Pick one before generating data. All IDs, buttons, meshes and counts depend on this choice.

**Recommendation: 9 regions.** Merge `wheelsets` into `bogie_structure`, shown as "Bogies & wheelsets" with a quota of 2,000 and parts `bogie_frame, suspension, damper, wheel, axle, axle_bearing`. Keep the other eight regions from the train-parts note. Reason: bogie frame, wheelset and brake disc share the same ~40 px of screen space. Three overlapping hover targets there cannot be told apart by mouse and cannot be explained visually. Braking stays separate because it can also be drawn as an underfloor brake-control/compressor module on the trailer car (see 3D section). Keeping 10 regions is acceptable only with an "Expand undercarriage" interaction, which adds work without adding insight.

The guided path needs SUPP_00012, SUPP_00450 and SUPP_00731 in `doors`. Hash allocation will not put them there. Add an explicit **quota-preserving swap override** to the manifest: each challenge ID swaps region with the first hash-ordered doors member that is not a challenge ID. Record it as `overrides: [{id, from, to, swappedWith}]` and show it on the provenance panel. Quotas stay exact.

### B2. Resolve the radar weights: equal vs unequal

The challenge note says equal weights within each axis. The train-parts note proposes unequal weights (e.g. Legal = 0.70 Compliance + 0.30 Governance). Both use the same columns.

**Recommendation: equal weights (`radar-v1-equal`).** The unequal weights rest on "direct measures receive more emphasis", which is a judgment the source descriptions don't support. Each one would invite a "why 0.7?" question in a demo, with no answer. Equal weights are the least-assumption choice and are easy to state: "Each axis = mean of its listed source scores." Keep weights in the manifest so a later version can change them without code changes. People & safety stays one axis, as the train-parts note says.

### B3. The overview radar must not imply that systems differ

Local check: assign the 10,000 rows to six random groups (the planned allocation is hash-based and independent of risk, so it behaves the same way). Every group's six axis means fall between **49.4 and 50.9**. Every system radar would be a near-identical regular hexagon at 50. A morph animation between systems would show movement that means nothing.

Required redesign of the overview radar card:

- Draw the **system distribution** as a band: P25–P75 per axis as a light filled ring, with the median as a thin line. Do not draw the mean as a polygon. Show the mean and valid n per axis in the axis tooltip and data table.
- Overlay **one focused supplier** polygon (the hovered or selected supplier card; by default the first card). The radar is useful as "this supplier against its system's spread".
- Add one honest caption line: "Assignments are synthetic and independent of risk, so system distributions are similar." This is true and saves a reviewer from asking.
- Do not animate the band when switching systems. Crossfade at 120 ms. Only the supplier polygon may morph (240 ms) when the focused supplier changes.
- Provide a "View as table" toggle with the six values, source columns and weights. This is also the accessible version.

### B4. "Financial" axis vs `Financial_Health_Score` conflict in the guided path

Local check on the challenge IDs (equal weights):

| ID | Financial_Health_Score | Credit_Rating_Score | Derived Financial axis |
|---|---:|---:|---:|
| SUPP_00012 | 54 | 57 | 55.5 |
| SUPP_00450 | 65 | 58 | 61.5 |
| SUPP_00731 | **53** | 76 | **64.5** |

The Copilot answers "SUPP_00731 has the lowest financial risk" from the source column. The radar beside it shows SUPP_00731 with the **highest** Financial axis. A buyer will notice. Required:

- The radar axis label reads "Financial (derived)". The tooltip names both columns.
- The Copilot answer names the metric exactly ("Financial_Health_Score (supplied)"). It adds one line: "On the derived Financial axis (with Credit_Rating_Score), SUPP_00731 is highest at 64.5." Use this as a deliberate teaching moment in the guided journey, not a hidden inconsistency.
- No Copilot answer may use "financial risk" without naming its column or axis.

### B5. 3D implementation contract (works offline via file://)

Build a real, interactive 3D view, not an image. **Recommended: vendored Three.js, inlined at build time.**

- Pin one version and commit `prototype/v2/vendor/three.module.min.js` with its MIT LICENSE and a SHA-256 in the manifest. From r171 onward, `three.module.js` imports `./three.core.js`. Pin **r170 or earlier**, or inline both files. The build script must fail if the vendored file contains any `import` statement. No CDN, and no fetch at runtime.
- `file://` blocks external module scripts in Chromium. The build must **inline** the vendored source and the app code into one `<script type="module">` in the output HTML. This matches how v1 embeds the CSV.
- Camera: PerspectiveCamera with fov 28 (low distortion), 3/4 view from front-left and slightly above. Drag orbits yaw within ±35° and pitch within 8–30°. No zoom or pan. "Reset view" button. No auto-rotation.
- **Render on demand.** Request a frame only on pointer move, drag, tween or resize. Do not run a continuous RAF loop. Pixel ratio = `min(devicePixelRatio, 2)`. Use flat or low-roughness `MeshStandardMaterial` with one hemisphere light and one directional light. No shadows, textures or post-processing.
- Geometry is procedural, about 2–4k triangles. Two cars: a cab car (motor) and a trailer car. Carbody is an extruded rounded profile along the length. Region meshes:
  - `carbody`: body shell and couplers.
  - `doors`: two door leaves per side per car, slightly inset.
  - `interiors`: translucent window band. A cutaway on the trailer car shows seat blocks.
  - `hvac`: roof modules.
  - `electrical_auxiliary`: pantograph and roof boxes on the motor car.
  - `control_cab`: cab nose and windscreen.
  - `traction`: underfloor boxes between bogies on the motor car.
  - `braking`: underfloor brake module on the trailer car, plus disc rings on the axles.
  - `bogie_structure`: bogie frames and wheels.
- **Hit-testing**: raycast against invisible, slightly enlarged proxy boxes per region (`userData.regionId`), not against the visible detail meshes. If proxies overlap, the closest hit wins. A click counts only if the pointer moved less than 4 px; otherwise it is a drag and does not select.
- Hover shows an HTML tooltip anchored at the pointer: "Doors · 700 suppliers · 700 scored · 0 research-only · demo assignment". The hovered region gets an emissive tint at 0.35. The selected region gets an accent material.
- **Labelled system controls are mandatory and equal**. A row of buttons (`aria-pressed`) under the canvas, each showing label and count. Focusing a button highlights its region in 3D. Enter/Space selects it. The canvas is `aria-hidden` with a visible caption. The workflow must be completable without touching the canvas.
- **Fallback**: if `WebGLRenderer` throws or the context is lost, render an SVG side elevation. It uses the same region IDs as `<path>` elements, with the same hover, focus and click handlers. Print uses this SVG too, because a canvas prints poorly.
- `prefers-reduced-motion`: no camera tween, no pulse. The selection still changes the material instantly.

Why not a hand-written projected renderer: per-face painter's-sort artifacts on interlocking parts (bogies inside the body skirt), hand-written hit-testing, and lighting all cost more than the roughly 650 KB of vendor code. The output is already about 3 MB because of the embedded CSV. A hand-written renderer is acceptable only if vendoring is refused. In that case use SVG polygons with per-object (not per-face) depth sort, non-intersecting parts, and native SVG hover.

### B6. Design for the real viewport, not the screen size

A "1440 × 900" screen in a Windows browser with tabs and address bar gives an **inner height of about 780–800 px**. A 1366 × 768 laptop with the taskbar gives **about 600–650 px**. Common Windows laptops at 1920 × 1080 with 125% scaling give 1536 × ~730. Test these inner sizes: **1440 × 790, 1366 × 640, 1536 × 730**. Implement the compact mode as `@media (max-height: 720px)`, not by width. Below 600 px inner height, the page scrolls. Text never shrinks below 12 px. Geometry is in the next section.

### B7. Deep Research gets its own route and an explicit state machine

The streamed plan, stage events, fact card, report and source register do not fit in a launcher or drawer. Copilot "Supplier data" mode lives in the overview's right rail. The "Deep Research" toggle navigates to `#/research`, which keeps the Copilot conversation visible as a context strip.

Run state (one active run, immutable `runId`, bound `entityId`):

```
idle ──start(supported)──▶ running[stage 1..6] ──▶ completed
  │                         │  ▲ pause/resume
  │                         ├──cancel──▶ cancelled (partial report, not addable)
  └─start(unsupported)──▶ unsupported (empty identity state, not addable)
completed ──ack scope + choose region──▶ added (catalog +1, region +1, one transition)
any ──reset / new entity / new start──▶ old run's timers cleared; late events dropped by runId check
```

Every queued event checks `event.runId === state.run.id` before it applies. Use one timer handle per run so cancel and reset clear it. "Show complete example" jumps to the end without pretending the remaining stages ran: the skipped stages are marked "shown from saved example".

### B8. One memo document model, printed from a dedicated print root

Adopt the challenge note's approval-request template unchanged. Implementation constraints:

- Preview and print render **the same memo revision object** into `#print-root`. `@media print` hides everything else.
- `@page { size: A4; margin: 16mm 14mm; }`. A fixed header ("APPROVAL REQUEST — DRAFT / NOT APPROVED · memo ID · rev") repeats on every page in Chromium. Tables use `<thead>` so header rows repeat. Use `break-inside: avoid` on fact cards and checklist rows.
- Long URLs: `overflow-wrap: anywhere`. Print the full URL text, not only link text.
- The button is labelled "Print / Save as PDF". After `window.print()` returns, change no state.
- The risk report uses the same print pipeline with a different template and the header "RISK REPORT — LIMITED SCOPE · saved replay".

## Layout geometry

Grid unit 4 px. All sizes are CSS px at 100% zoom.

### Overview at 1440 × 790 inner (standard)

```
┌ Header 56 ───────────────────────────────────────────────────────────────────────────┐
│ ◼ Train Sourcing  | Overview  Discovery  Reports |  10,000 records · demo assignments ⓘ │ Guided tour ▸  Reset │
├──────────────────────────────────────────────────────────────────── padding 16/20 ───┤
│ LEFT 1fr (≈ 852)                                      │ RIGHT 532                       │
│ ┌ Train card  h = 516 ──────────────────────────────┐ │ ┌ System summary h 124 ───────┐ │
│ │ hdr 40: "Doors" · Illustrative schematic · ⟲ view │ │ │ Doors  700 suppliers         │ │
│ │ canvas  ≈ 404 (3D)                                │ │ │ 700 scored · 0 research-only │ │
│ │ system buttons 9 × ~88 w, h 56 (label + count)    │ │ │ 31 Critical total-risk (src) │ │
│ └───────────────────────────────────────────────────┘ │ │ [Discover in Doors →]        │ │
│ gap 16                                                │ └──────────────────────────────┘ │
│ ┌ Supplier cards h 170 ─────────────────────────────┐ │ ┌ Radar h 350 ────────────────┐ │
│ │ tabs 28: Lowest total risk | Favorites | Prev used│ │ │ hdr 36 · chart 260×260       │ │
│ │ 3 cards, each ≈ 272 × 126                         │ │ │ legend/caption 40 · table ⇄  │ │
│ └───────────────────────────────────────────────────┘ │ └──────────────────────────────┘ │
│                                                       │ ┌ Copilot dock h 196 ─────────┐ │
│                                                       │ │ mode: [Supplier data|Deep R.]│ │
│                                                       │ │ last answer (2 lines, scroll)│ │
│                                                       │ │ 2 suggestion chips · input 40│ │
│                                                       │ └──────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

Height check: 56 + 16 + (516 + 16 + 170) + 16 = 790. Right column: 124 + 16 + 350 + 16 + 196 = 702, the same as the left. The "31 Critical" figure is a placeholder; compute it from the data. Column split: 1440 − 40 padding − 16 gap = 1384, so left 852 and right 532. With 9 system buttons at 88 px plus 8 px gaps, the row is 856 wide. Make it a horizontally scrollable row with no visible scrollbar, or use 2 rows × 5 in compact mode. Truncate labels to their short form ("Power & aux") and give the full label in the tooltip.

Expanded Copilot: the dock grows upward into the radar's slot. The radar collapses to a 56 px summary strip ("Radar hidden · show"). Nothing overlays the train or the cards. Esc collapses it.

### Overview at 1366 × 640 inner (compact, `max-height: 720px`)

- Header 48. Padding 12/16. Gap 12. Columns: left 1fr ≈ 838, right 480.
- Left: train card 428 (header 32, canvas 340, buttons 2 rows × 26 = 56 using short labels and counts). Supplier cards 128: 3 cards of 268 × 100 with tabs collapsed into a 120 px `<select>` in the card header.
- Right: summary 96 (two lines) + radar 300 (chart 220) + Copilot dock 160 (one suggestion chip). 96 + 12 + 300 + 12 + 160 = 580 ≈ 640 − 48 − 24 = 568. Trim the radar to 288.
- Below 1280 width: the right column moves below the train and the page scrolls. Never shrink the train canvas below 300 px tall.

### Discovery `#/discover` (1440 × 790)

Filter rail 264 (system, search, source risk level, delivery minimum, favorite, previously used, Clear filters). Results table 1fr, 40 px rows, about 13 rows per page, pinned header, pagination footer 44. Compare tray 64 px docked at the bottom of the results column only: "7 / 20 selected · 2 outside current filters · Compare →". A blocked 21st selection shows an inline message in the tray with a remove path; it does not raise a modal.

Compare `#/compare`: matrix with pinned first column 220 and supplier columns 112 wide, scrolling inside the matrix. Rows are 6 derived axes, Total_Risk_Index and its level, delivery, and confirmation. Unknown cells are hatched and labelled "Unknown". On the right, a 320 px panel shows the radar for **one** focused column against the band of the selected set. Never overlay 20 polygons.

### Deep Research `#/research` (1440 × 790)

Context strip 40: entity, scope, "Simulated replay · saved sources · no live search", Pause, Cancel, Show complete. Three columns: timeline 340 | fact card + TLDR 1fr | source register 340. The timeline shows the six stages, each with a status icon, a timestamp relative to replay start, and 1–3 short event lines. After completion, a sticky action bar at the bottom of the centre column shows: View risk report, region select, scope acknowledgement checkbox, Add to suppliers.

### Memo `#/memo/:id`

Two columns: form 480 | live A4 preview 1fr, scaled to fit width with a print-equivalent DOM. A status pill (Incomplete draft / Ready for review / Stale) is shown with the list of missing fields.

## Visual system

Understated, closer to an enterprise tool than a marketing page. One accent colour. Colour for risk appears only on data marks.

**Palette**

| Token | Hex | Use |
|---|---|---|
| `--bg` | #F4F6F7 | page |
| `--surface` | #FFFFFF | cards |
| `--line` | #DCE2E6 | borders, gridlines |
| `--ink` | #1E2A33 | primary text |
| `--ink-2` | #56656F | secondary text |
| `--ink-3` | #87949C | tertiary, axis labels |
| `--accent` | #0F6E74 | selection, primary buttons, focused polygon |
| `--accent-soft` | #E3F0F0 | selected chips, band fill (at 60% opacity) |
| `--focus` | #2563EB | focus ring 2 px + 2 px offset (distinct from accent) |
| risk Low | #6E8A96 | source level chip (deliberately not green) |
| risk Medium | #B48A2C | |
| risk High | #B2582F | |
| risk Critical | #8C2B35 | |
| Unknown | #FFFFFF with 45° hatch #B7C0C6 | never grey-filled like a value |
| Simulated tag | #5B4E8C outline chip | "Demo" / "Simulated replay" |

3D materials: body #E6E9EB, roof and undercarriage #3B4651, glazing #A9BCC6 at 55% opacity, hover tint accent at 35% emissive, selected = accent base colour #0F6E74. **Do not colour train regions by risk**; B3 shows they would all look the same anyway.

**Type**: offline system stack `"Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif`. Use `font-variant-numeric: tabular-nums` on all figures. Scale: 12 (captions, provenance), 13 (table, chips), 14 (body), 16 (card titles), 20 (screen titles), 28 (single headline count only). Weights 400/600 only.

**Spacing and shape**: 4 / 8 / 12 / 16 / 20 / 24 / 32. Card radius 8, control radius 6. Shadow is only `0 1px 2px rgba(16,24,32,.06)` plus a 1 px border. Icons are 16 px inline SVG with 1.5 px stroke. Do not use an emoji or icon font.

## Motion

| Event | Motion | Duration / easing |
|---|---|---|
| Hover region / button | emissive tint, tooltip fade | 120 ms ease-out |
| Select system | camera tween toward region centroid (max 15° yaw change), summary crossfade | 320 ms ease-in-out; band crossfade 120 ms |
| Focus supplier | supplier polygon morph | 240 ms |
| Research event | line appears with 4 px slide-up, stage icon pending → running (spinner) → done | event gap 1.4–2.4 s, about 12 s total |
| Add to suppliers | count ticks old → new; region pulses once (emissive 0 → 0.5 → 0); toast "Added to Doors · research-only · scores unknown" | 400 ms / 600 ms / toast 4 s |
| Copilot expand | dock height transition | 200 ms |

`prefers-reduced-motion`: every row above becomes instant. Research defaults to "Show complete example" with a manual "Replay" button. No count-up animations on first load, and no looping motion anywhere.

## Reporting honesty checks (additions to the challenge list)

1. The overview caption and the provenance popover state: synthetic system assignment, version `train-demo-v1`, overrides listed, quotas are product choices.
2. Supplier cards tab "Lowest total risk" is labelled "Lowest supplied Total_Risk_Index · not a recommendation". Favorites and Previously used tabs do not reorder by risk silently; each sorts by ID with the sort shown.
3. A research-added record shows the radar empty-state text "No supplied scores, so the radar is not drawn" and **not** an empty polygon. It is excluded from band, mean and n. The system summary shows "research-only: 1".
4. Hover tooltips show count semantics ("suppliers assigned"), never "parts" or "capacity".
5. Copilot data answers always show the column name, the values, and "Show cells". Abstain on capability, qualification, price and lead time.
6. A replay timestamp is never shown as a retrieval date. Source rows show the publication date or "Unknown" and the source-check date "18 Oct 2026 (saved fixture)".

## Implementation guidance for Sol

- Keep v1 untouched. New sources go in `prototype/v2/src/` (`styles.css, data.js, train3d.js, radar.js, discovery.js, copilot.js, research.js, memo.js, app.js`) plus `prototype/v2/vendor/`. A new `scripts/build_v2.py` inlines everything into `prototype/train-risk-v2.html`. A new `scripts/augment_dataset.py` writes `docs/supplier_risk_dataset_augmented.csv` and `docs/train-demo-v1.manifest.json`, then asserts the original hash, 10,000 rows, quotas, 500/1,500 flags and overrides. Split file ownership along these modules.
- Use a single store: `{catalog, regionAssign, favorites, previous, compare[≤20], filters, focusRegion, focusSupplier, copilot, run, reports{}, addedRecords{}, memos{}}`. Derive every count from the store and never cache a count in the DOM. `train3d.js` takes `{counts, selected, hovered}` and emits `select`/`hover`. It never reads the store directly.
- Precompute per-region quartiles and means once at load, about 10k × 6 values. Recompute only the affected region when a research record is added. A research record has null scores, so the stats do not change, but the counts do.
- Embed data as columnar JSON arrays (smaller and faster than parsing CSV at runtime), with the CSV SHA-256 alongside for provenance dialogs.
- Use the Guided tour as an overlay checklist (right-bottom, 300 px wide, collapsible) with the 8 steps from the challenge note. Each step has a "Do it for me" action that performs the same state transition as the UI.

## Conflicts and pending items for the parent

| Item | Challenge note | Train-parts note | This review |
|---|---|---|---|
| Systems | 6 | 10 regions + quotas | 9 (merge wheelsets into bogies) + swap override for challenge IDs |
| Axis weights | equal | unequal | equal (`radar-v1-equal`) |
| Favorites / previous counts | unspecified | 500 / 1,500 | accept |
| Overview radar | system mean polygon | region mean | distribution band + focused supplier (B3) |

The data mapping remains **pending parent vetting** until the first two rows are decided. Nothing in this review was browser-tested. The geometry figures are design targets to verify at the three inner viewports in B6.
