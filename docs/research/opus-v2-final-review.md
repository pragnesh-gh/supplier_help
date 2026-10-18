# Opus v2 final UI review

Date: 2026-10-18 · Build: `prototype/train-risk-v2.html` served at `http://127.0.0.1:8765/train-risk-v2.html`
Method: T3 preview, my own tab, no fallback needed. Viewports were 1440×900 and 1440×790. I reviewed Overview, Research (idle, running and complete states) and the research risk-report preview.
Scope: visual and usability only. The parent agent owns functional and PDF QA. I did not review Discovery compare-20 or the approval PDF.

## Verdict

**Accept with fixes.** The build follows the FINAL decisions. It has nine regions with Bogies grouped, a supplier polygon drawn over the P25–P75 band and dashed median, and "Financial (derived)" labelled separately from the supplied total-risk level. It is fully offline, with one network request and a favicon present. The research route is separate and has replay controls. The visual style is restrained and consistent: teal accent, Segoe UI, quiet cards. Fixes 1–3 must be done before demo. Fixes 4–7 are polish within the brief's scope.

## Prioritised fixes

### Must fix

1. **Supplier cards are clipped on Overview.** At both 1440×900 and 1440×790, `.card.supplier-strip` has clientHeight 168 and scrollHeight 195 with `overflow:hidden`. The cards cut off at the action row, and the third card's "Previously used · demo history" tag is half-hidden. That tag is a requested feature, so it must be visible. `.card.copilot` also clips by 9 px (188 vs 197). Fix: give the train card less height. It is 516 px at 790 and the train only fills about 55% of it (see 2). Use the freed space for the strip. Alternatively, move the history/favorite tag inline next to the ID instead of on its own line. Pass condition: no clipped `overflow:hidden` card at 1440×790 or 1440×900.

2. **The 3D train is undersized in its canvas.** The canvas is 850×408 at 790 high, and the train takes up the upper ~60% of it. There is a blank band of roughly 120–150 px between the wheels/rail and the "Drag to rotate" hint. Fix: re-frame the camera so the train fills about 85% of the canvas width and is vertically centred, or lower the target y. Combined with fix 1, this lets the canvas shrink without the model shrinking.

3. **The research CTAs sit below the fold after completion.** At 1440×790 the completed page is 1313 px tall. "View risk report", the system select, the acknowledgement and "Add to suppliers" sit at y ≈ 1006–1188, which is off-screen. The TLDR is the 7th row of an undifferentiated label/value list, and no stats summary is shown even though TLDR and stats were requested. Fix: put a compact summary block at the top of the centre column. It should contain the TLDR (body size, slightly emphasised) and a stat row, for example `6/6 stages · 3 sources · 3 findings · 9 gaps`. Next to it, put the "View risk report" and "Add to suppliers" actions, or make the action footer sticky. Fold Entity, Identity, Scope, Country and Research ID into a 2-column meta grid so each stops taking a full 60 px row.

### Should fix

4. **The research centre column doesn't stream visibly.** While running, the centre column shows the full final form straight away. It fills with placeholder values like "Unknown · company-source stage not covered" and "No final synthesis", and "Next action" is already populated. Progress only shows in the left stage rail (✓ / › / ○). Fix: while the run is in progress, render only the rows for completed stages and show a single "Reviewing company sources…" line with subtle motion. Reveal the remaining rows as each stage completes. Also disable "Start saved replay" while the run is running; it stays enabled now.

5. **The idle research state has two competing CTAs.** "Start saved replay" (primary) and "Load Siemens AG example" (secondary) look like they do the same thing. Fix: rename the secondary to "Show finished example" so it pairs with the header's "Show complete example", or remove it. The disabled Pause/Cancel/Show-complete buttons in the idle header add noise; hide them until a run starts.

6. **The radar has small type and an empty panel.** Axis labels render at about 11–12 px in grey, and the "0" centre label sits on the polygon. The chart occupies 460×247 of a 530×368 panel, which leaves visible empty space at the sides. Fix: bump the axis labels to 12–13 px, drop the "0" label (keep "100"), and let the SVG use the full panel width. Optionally show the focused value after each label, e.g. "Operations 75.5". That value is already in the accessible name and is the most useful number on the chart.

7. **3D hover feedback was absent in one probe.** I hovered over the bogie wheels and saw no visible tooltip or highlight. This is one observation; the parent should confirm. The selected region (Doors) is clear in teal, but nothing indicates which other meshes are interactive. Fix: on hover, tint the region slightly and show a small label with name and count. The renderer's tooltip contract already covers this. Also check the cursor changes to a pointer over hit targets.

## Working well (keep)

- System chips under the canvas: equal width, counts readable, pressed state clear.
- Selected-system header: "700 records · 700 scored · 0 research-only", "supplied total-risk level" wording, and a clear Discover → action.
- Radar legend and the honest footnote ("Assignments are synthetic…"), with "Weights & mapping" disclosure.
- Copilot tab split between Supplier data and Deep Research ↗, with a "Supplied data" scope badge.
- Research source register: per-source publication, covered period and source-check, plus an explicit "no news/registry search performed" callout.
- Risk report preview: one clean document, red limited-scope line, TLDR, and a plan/source-coverage table. Typography is consistent with the app and print-ready in appearance.
- No console errors. The only console output was WebGL ReadPixels perf warnings from the driver, which are harmless.

## Not reviewed (out of my scope or not reached)

Discovery compare-20 layout, favorites persistence, approval-PDF parity between reused and new candidates, actual print output, and mobile widths.
