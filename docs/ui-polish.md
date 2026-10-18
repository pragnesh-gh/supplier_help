# UI polish: Material-style sweep

A presentation-only pass over the unified web app. It borrows tokens and component rules from the design references in `docs/ui-ux/{explore_supplier,compare_vendors,supplier_profile}/DESIGN.md` and applies them where they suit the existing app. The app was not replaced. There are no backend or data changes, and the UI makes no new claims about verified or live status.

## Files

- `web/ui.css` is loaded after `styles.css` and `approval.css`. It holds the tokens (Figma palette: primary `#1f5f5b`, outline `#c9d4d1` / `#dfe6e4`, soft risk pills, 4/6/10px radii; the legacy `styles.css` names `--accent`, `--bg`, `--line`, … are aliased to these roles) and the component rules. Layout grids stay in `styles.css`.
- `web/icons.js` provides `icon(name, size)`, which returns a decorative `<span class="msi" aria-hidden="true">`. The span is coloured by `currentColor` through a CSS mask. Unknown names render nothing. `arrow_back` is the `arrow_forward` file mirrored with CSS.
- `web/vendor/material-symbols/` contains the 17 official Material Symbols SVGs (Apache 2.0, pinned upstream commit; see its README and manifest). They are served locally, with no font, CDN or network dependency.

## Design choices

- **Icons supplement text.** Visible labels are kept. Icon-only controls are the close, remove and favorite buttons and the chat send button, and each has an `aria-label`. The ad-hoc glyphs `☆★↺→←?✦✕↑` are gone.
- **Button hierarchy.** Each view has one filled primary action (Discover, Compare, Build shortlist, Compare selected). Secondary actions are outlined, and tertiary actions are quiet text buttons. Disabled buttons use a flat container instead of 45% opacity.
- **Focus.** Controls get a 2px primary outline with a cyan aura from the design brief (`#00BEDC` at 45%). Fields get a primary border with the aura. The primary outline keeps the indicator at ≥3:1 contrast, which cyan alone does not reach on white. Invalid fields show an error border after user interaction (`:user-invalid`).
- **Segmented controls.** One `.toggle-group` style covers the Overview collection tabs, the radar Chart/Table toggle (it now names both states and uses `aria-pressed`), and the My suppliers collection and layout groups (`role="group"` + label).
- **Chips.** Part filters are Material filter chips: a check icon shows when pressed, and counts use a mono font. Risk badges are 20px, bordered and colour-coded. `Low` now has its own colour, and `Critical` carries a diamond glyph so the level is not shown by colour alone. Citation chips are single-line and numbered, with a document icon for dataset cells and the full label in a tooltip.
- **Typography.** Supplier IDs use a monospace font. Table headers are 11px uppercase on a muted surface. Printed and dialog documents keep plain headers. Numeric cells use tabular figures.
- **Empty states.** Recently viewed, Used before, Discovery with no results, Compare with nothing selected, My suppliers and Reports each have an icon, a short reason and a next action.
- **Compare.** The title actions are grouped. Each column header has an icon-only remove button. The focused supplier column is tinted and marked with `aria-current`. The level row uses risk badges.

## Preserved behaviour

These are unchanged: the compact overview (fits 1440×790 with three recent cards; bottom card edge at 743px), the 3D train and system radar, the lowest-total-risk default, Recently viewed / Used before, the finite Discovery intro animation, the 20-supplier compare limit, 3–5 approval candidates, research inside the same chat, and the chat focus trap with Escape returning focus to the launcher. The ring/telemetry components were not reintroduced.

## Verification (2026-10-18)

- Isolated QA server (`:8881`, `output/ui-polish-qa` storage, no `.env`). The user workspace on `:8880` was not touched.
- T3 preview at 1440×790 and 390×844 (iPhone 12 Pro). No horizontal page overflow on mobile.
- `node --check` on every changed JS file; `node tests/test_shortlist.mjs` and `python -m unittest tests.test_supplier_app` pass.
- Screenshots are in `output/ui-polish/` (gitignored).

## Known limitations

- At widths up to 1050px the header utility actions (Data & assumptions, Guided journey, Reset) are still hidden. This predates the sweep.
- On mobile the primary nav scrolls horizontally, and the Discovery table scrolls sideways instead of reflowing into cards.
- Favourites use the Material `bookmark` / `bookmark_filled` (FILL 1) glyphs everywhere; the on state is the filled glyph on an accent-tinted container plus `aria-pressed` and a tooltip. The `star` assets remain in vendor but are unused.
- `approval.js` markup was out of scope, so the Approvals page was polished through CSS only. For example, "Back to comparison" has no icon.

Parent verification: all 33 Python tests and both JavaScript tests pass. Independent Standards and Spec reviews found no unresolved issues. Selected favorites now use the filled Google star asset as well as aria-pressed and amber styling.
