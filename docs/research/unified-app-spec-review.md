# Unified app spec review

Reviewed commit `798584f` against baseline `aaf5b7a`, `docs/web-app-implementation.md`, and `docs/local-app.md`. Scope: frontend/backend seams, source identity, research state, persistence and approval evidence. This is a code review with targeted backend tests, not an independent browser or live-provider audit. No credentials read and no paid calls made.

## Original findings and resolutions

1. **Best delivery ranked worst first — resolved.** `supplier_app/core.py` now distinguishes positive operational metrics from risk scores and honors explicit lowest/highest wording. `test_ranking_direction_matches_metric_meaning` passes.
2. **Research checklist used nonexistent events and marked failures successful — resolved.** `web/chat.js` consumes `search`/`search_error` category events, distinguishes failed retrieval, and labels historical observations separately from live retrieval.
3. **Reset retained prior dossier context and polling — resolved for chat/research responses.** `chat.reset()` clears run/messages, stops polling, and advances a generation token; pending assistant and poll responses check that token. App Reset invokes this method. The separate add-supplier request still has the issue below.
4. **Approval evidence provenance incorrect or absent — resolved.** Original 46 cells and appended demonstration fields now have separate source/hash sections. Research approval drafts fetch the dossier before creation and include its findings/source register; restored research drafts reload their dossier.
5. **Historical paraphrases shown as verified quotations — resolved.** Historical findings now use an explicit unverified-paraphrase label rather than quotation styling, including in the shared report/print template.

## Remaining finding

**P2 — Add-supplier failure handler throws, and pending additions escape Reset.** At `web/chat.js:242`, the `data-chat-add` catch references `token`, but that variable is declared only inside the separate `saved-example` branch. If `/api/suppliers` rejects or the connection fails, the handler throws `ReferenceError` instead of displaying the error. Its success path also lacks a generation check, so Reset while an add is pending can repopulate the cleared workspace. Define a branch-local token before the request and check it after await and in catch.

## Validation

`python -m unittest tests.test_supplier_app -v`: **9 tests passed**. No additional implementation files changed by this reviewer. Final disposition: original five findings addressed; fix the remaining add-request lifecycle/error-handling issue before handoff.
