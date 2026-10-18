# Shortlist and supplier ring verification

Reviewed against baseline `c7b326f` on 2026-10-18. Spec: `docs/shortlist-approval.md` and the buyer's request for a shortlist approval flow and grouped supplier visualization.

## Standards review

Independent review found a refresh/submission race that could hide a newly saved request. Refresh now merges immutable records by ID. Shared `riskLevel` classification prevents ring counts and Discovery's unknown filter from disagreeing. No repository-specific coding standards were present.

## Spec review

Opus 5.5 reviewed in two rounds. Resolved findings: literal question-mark separators, stale Discovery filters after ring clicks, tour links to the legacy single-candidate memo, silent full-shortlist behavior, ambiguous draft-pool suggestions, missing research-dossier errors, angular score ordering and retained print styles. Existing draft notes are preserved; removal of annotated candidates asks for confirmation in the app. Reports clearly distinguish the legacy assessment from the shortlist request.

The second review confirmed these changes, with two remaining display typos subsequently corrected. The backend fixes the status at awaiting approval and preserves server-controlled source snapshots. No authenticated approval or notification is claimed.

## Verification

- 33 Python tests pass, including count limits, duplicate rejection, required notes, source snapshot immutability, missing research evidence and HTTP write boundaries.
- Two Node tests cover shortlist cutoff/cap/unknowns and full ring counts with a bounded sample and escaped labels.
- Browser test on a separate localhost instance/storage: six comparison candidates suggested five; sixth selection disabled; submitted request survived reload; print document matched saved preview. Production workspace received no test request.
- Ring risk clicks cleared unrelated filters and retained a selected door-drive part; its full count was 233. Supplier and risk controls are keyboard-accessible buttons.
- Desktop ring layout fits beneath the summary; narrow-screen ring and saved request had no horizontal overflow. Preview tool scaling yielded measured viewports of 1441×791 and 427×926 during checks.
- JavaScript syntax and Git whitespace checks pass. Original and augmented CSV files were not modified.

Actual PDF pagination was not rendered in this pass; the browser print document and repeated status-header configuration were checked. Approvals remain local saved requests; reviewer authentication, approval decisions and negotiation tracking are outside this increment.
