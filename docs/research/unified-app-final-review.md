# Unified supplier app — final code review

Scope: `git diff aaf5b7a...798584f`. I only read the code and changed nothing. Tests: `python -m unittest discover -s tests -v` passed all 24 tests. I didn't use a browser. I probed the assistant directly in Python with no API key, so no paid calls.

## Earlier fixes verified

These fixes check out:

- Explicit ID precedence (`core.py:103-104`)
- Name boundary
- Metric direction
- Separate `dataset_context` validation (`research_agent/core.py:312-316`)
- Demo alias (`server.py:41-42`)
- 400 KB workspace PUT, with host and origin checks
- Anonymous-identity guard
- Reset generation guards in `chat.js` (`poll` and `send`)
- Citation row numbers: CSV IDs map exactly to physical row−1

## Findings

### HIGH — Workspace saving breaks permanently once chat history grows
- `supplier_app/core.py:52` rejects `chat` when its JSON is over 180,000 characters. The client sends `messages.slice(-200)` (`web/app.js:869`), which caps the message count but not the size.
- One "Why … high risk" answer for 20 selected suppliers is about 27.5 KB (measured). A 20-row compare is about 7.7 KB.
- After about 7 explain answers or about 23 comparisons, every `PUT /api/workspace` returns 400. Favorites, compare, memo drafts and added suppliers then stop saving. The only sign is a toast on each render.
- The same mismatch exists at the request level: `drafts` and `chat` can each be 180 KB, plus 10,000 favorites at about 130 KB. That totals about 490 KB, over the 400 KB `workspace_body` cap.
- Fix: trim the chat on the client by serialized size (oldest first), or trim and compact citations on the server. Make the per-field caps fit inside the body cap.

### MEDIUM — Chat "Add as unscored supplier" error path throws a ReferenceError
- In `web/chat.js:240-252`, the `catch` uses `token`, but `token` is only declared inside the `saved-example` block.
- Repro: click Add on a run that the server rejects (for example, an incomplete run or a duplicate). The result is an uncaught `ReferenceError`, and the user sees no error message.
- Fix: capture `const token = generation` before the `await`.

### MEDIUM — The default focus silently scopes every chat question
- `selected()` falls back to `state.focus`, which starts as `SUPP_00012` (`app.js:41`). As a result, `rows` is almost never empty on the server.
- Repro: "How many suppliers?" with the default state. It returns `clarify` ("Which supplied metric…") instead of the 10,000 count (`core.py:139` needs `not rows`).
- Repro: Deep mode with no company never auto-routes to research.
- Repro: Generic questions without a metric trigger the LLM column picker against one implicit row.
- Fix: send only `compare` as context, or make the server honor an explicit `focus_id` only when the question refers to "this supplier".

### MEDIUM — Async work after Reset is not guarded in `app.js`
- `newMemo` (`app.js:279-314`), `showRisk`, `addLive` and `onAdded` await requests and then write to `state`.
- If a reset happens mid-request, `state.memo` or `state.added` reappears on the fresh `initial()` state and is persisted.
- Fix: reuse a generation counter, as `chat.js` does.

### LOW — A stale or corrupt workspace blocks the whole app
- `Workspace.get` re-validates the stored IDs (`core.py:63-65`). If a `research:` supplier is missing (different `--data-dir`, files removed) or the JSON is corrupt, it returns 400.
- `restoreWorkspace` then throws, and the app shows "Unable to load supplier workspace".
- Fix: on read, filter out unknown IDs and fall back to defaults instead of raising.

### LOW — Ranking a question that says both "lowest" and "highest" picks one direction silently
- `core.py:181`: "rank country risk lowest highest" sorts descending without telling the user. Asking a clarifying question would be safer.

### LOW — Run-chat citations assume `s['url']` exists
- `core.py:132`: a source without a URL raises `KeyError`, which the server maps to a misleading 404 "Record not found".

### LOW — Mojibake in the progress label
- `chat.js` shows "Retrieved ? review remains partial". An em dash was lost.

### LOW — First-row type sniffing
- `core.py:165` and `core.py:150`: when `rows[0][metric]` is missing (None), a numeric metric is treated as text. You then get no chart, and the LLM's allowed columns are reduced.

## Maintainability (smells, non-blocking)

- **Duplicated code:**
  - Building the research supplier row is copied in two places (`app.js` `onAdded` and the `addLive` handler).
  - The `Workspace(... research_ids lambda)` construction appears twice in `server.py`.
  - The memo field list is repeated in `memo()` and `memoDocument()`.
- **Long method:** `Assistant.answer` runs about 110 lines with a string-keyword routing chain. Splitting it into an intent classifier and handlers would help.
- **Long line:** `Assistant.citation` is one long line with repeated `startswith('risk_')` provenance switches.
- **Mysterious names:** `r`, `m`, `b`, `w`.
- **Dead code:** `train.js` returns no-op `destroy`/`resetView`. The listeners live on `#train-scene`, which is re-created on each render, so nothing leaks.

## Security

- No XSS found. Every interpolation goes through `esc`, and URLs go through `safeURL`.
- Writes check Host, Origin and Content-Type, and the server binds to loopback only.
- `.env` is never served.
