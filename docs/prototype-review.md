# Prototype review record

2026-10-18. Question: can a buyer move from supplier data through evidence to a defensible draft recommendation? The prototype demonstrates that journey; actual buyer validation and the winning layout remain pending.

Sol implemented the first pass after two research agents completed their primary-source notes. The parent reviewed source claims and the full dataset, then exercised the browser flow and fixed observed issues. No production backend or automated UI test suite is included.

## Observed checks

- All 10,000 source rows embedded; searching SUPP_10000 returns the last supplier, rather than a canned subset.
- Low total-risk filter returns 318 suppliers, consistent with the independent CSV audit.
- Selection persists through filtering and A/B/C layout switches.
- 20 selected suppliers block the 21st with visible feedback.
- Financial comparison for the challenge IDs returns 53 / 54 / 65, with SUPP_00731 lowest.
- Source dialogs show actual CSV physical row, column, value, source level and SHA-256.
- SUPP_00018 details expose 19 risk scores plus six operational/supply-chain fields, without fabricated aggregate weights.
- Unsupported capability/qualification questions abstain. Unknown company names do not receive Siemens facts.
- Demo dictation opens an editable transcript and sends through the same deterministic question flow; there is no microphone access.
- All nine guided steps were clicked through to an actual Markdown download.
- Research fixture displays three sourced disclosures and a bounded saved follow-up, with historical scope and remaining evidence gaps.
- Actual research-note, shortlist Markdown and CSV downloads were inspected. CSV contains three expected IDs, exact risk values and the same source hash.
- Reviewer input and a single Record click now persist in the draft and export. The initial rerender-on-blur issue was fixed.
- A stale answer clears when selection changes. Editing decision/research notes marks the recorded draft unrecorded.
- Desktop variants visually inspected; a 390px viewport has no page-level horizontal overflow. Comparison matrices intentionally scroll internally.
- Inline JavaScript syntax checked; no application console error after adding a local inline favicon.
- Opened the HTML through a local `file:///` URL and exercised data answers and decision editing successfully; the prototype needs no server or network.
- Original CSV untouched; GitHub's independent dataset validation passed. `.env` is ignored and no credential pattern was found in tracked files.

## Verification limits

T3's collaborative preview navigation succeeded but snapshots twice timed out with `Preview automation snapshot timed out after 15000ms.` The parent used the Playwright CLI for browser review. Screenshots and downloaded artifacts are local and ignored under `output/playwright/`.

The model catalog check passed. No credentialed inference, live research worker, real speech recognition, deployed authentication or jury access has been tested or implemented. The API key field is intentionally empty for the user to fill locally. This review does not establish that any supplier is qualified or that the UI fits a real buyer's work without user feedback.
