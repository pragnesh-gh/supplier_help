# Unified app — follow-up review (798584f...790ea4c)

I only read the code; nothing was changed. `python -m unittest discover -s tests` passed all 26 tests. I probed `Workspace.validate` locally with no paid calls. I did not use a browser.

## Original findings, verified fixed

- **MED token:** Fixed. `chat.js` "Add" now captures `token` before the `await`.
- **MED implicit focus:** Fixed. `selected` is now `state.compare` only, and global counts no longer depend on the selected rows.
- **MED async after reset:** Fixed. `newMemo`, `showRisk`, `addLive` and `printDoc` check `appGeneration`. Reset order is safe:
  - `chat.reset()` → `onSave` first saves the old state.
  - `state = initial()` and `render()` then queue the clean snapshot.
  - The save loop always sends the latest pending snapshot last. `pagehide` re-snapshots the current state.
- **LOW corrupt workspace:** Fixed. The original file is backed up once, and valid fields are recovered.
- **LOW conflicting direction, missing URL, first-row null, mojibake:** All fixed.

## Remaining blocker

### HIGH — The client chat budget still exceeds the server cap, so saves can fail permanently
- The client measures `JSON.stringify` output, which is compact. `boundedChat` caps that at 95,000 bytes (`web/app.js` `boundedChat`).
- The server measures `json.dumps(..., ensure_ascii=False)` with the default separators `', '` and `': '` (`supplier_app/core.py:52`). Every comma and colon gains a space, adding about 4–7% for these messages. Measured ratios: "why high risk" answers 1.042, compare answers 1.064, rank answers 1.059.
- Repro: a chat of 64 real assistant answers (why, compare, rank over 20 IDs) measures 94,979 bytes on the client and 101,071 on the server. The server returns `chat is too large`.
- Any compare- or rank-heavy chat that reaches the trim limit ends up in this state. Every later render re-trims to the same size and is rejected again.
- `restoreWorkspace` also prefers the rejected localStorage recovery copy on every reload. The workspace never saves again, and `printDoc` refuses to print.
- Fix (either one):
  - Server: measure with `separators=(',', ':')`.
  - Client: trim to about 85,000 bytes.
- Add a test that sends a chat of exactly the client's budget through the PUT.

## Minor, non-blocking

### LOW — `drafts` are not bounded on the client
- Each added research supplier stores its full `_record` (actions, entity) at about 2–3 KB.
- Adding about 35 or more research suppliers pushes the drafts past the 100 KB per-field cap, with the same permanent save failure. More than 99 also exceeds the count limit of 100.
- This needs many paid runs, but the limit is reachable.
- Fix: persist `_record` as an `{id, run_id}` reference, or bound drafts the same way as chat.

### LOW — The recovery copy always wins over the server
- `restoreWorkspace` uses the localStorage copy unconditionally, even when another tab has since saved a newer workspace to the server.
- Fix: stamp snapshots with a time or version and keep the newer one.
