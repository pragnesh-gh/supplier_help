# Unified app preflight review

Baseline: `aaf5b7a` (main). Reviewed: `docs/web-app-implementation.md` (uncommitted), `research_agent/core.py`, `research_agent/server.py`, `prototype/train-workbench-v2.template.html`, `scripts/build_v2.py`, the in-progress `web/` shell, and the dataset header. This is a preflight on architecture, routing, identity and security, not a code review. Final code review happens in a separate round after commit.

Scope stays as the user set it: localhost only, no login, no deployment. Items are ordered by how much rework they cause if missed.

## Blockers (fix before integration)

### B1. Contract field mismatch: `example` vs `demo`
The spec says `POST /api/research {…, example:boolean}`. `ResearchService.start` reads `values["demo"]` and rejects a non-boolean value. If the frontend sends `example`, the Siemens saved-example path silently becomes a live run, which fails with no key and spends money when a key is set. **Fix:** use `demo` everywhere (the API source of truth is core), and correct the spec line.

### B2. 16 KB body cap breaks `PUT /api/workspace`
`server.py` sets `MAX_BODY = 16 * 1024`. A workspace with persisted chat, drafts and 20 compare IDs will exceed that within a few turns, and every save will then fail with a 400. **Fix (pick one, keep it simple):**
- The server appends chat turns itself inside `POST /api/assistant`. The client never PUTs `chat`, and `PUT /api/workspace` covers only favorites, compare, drafts and region, under its own cap (e.g. 256 KB). Server-side caps: chat at most ~200 turns, drafts at most ~50, each text field bounded.
- Otherwise, raise the cap for this one route only. Do not raise it globally.

The first option is preferred: the transcript stays authoritative and a stale tab can't overwrite chat.

### B3. Shared `.local/research-agent/state.json` across two processes
`Store` keeps everything in memory and rewrites the whole file on every event, using a fixed `state.json.tmp` name. On startup it marks every `queued` or `researching` run as `failed`. If the legacy server (8877) and the new app (8878) use the same data dir:
- they lose each other's updates,
- they race on the tmp file,
- starting one process fails the other's live runs.

**Fix:** give `supplier_app` its own default data dir (e.g. `.local/supplier-app/`), and keep workspace state in a separate file rather than inside the research `state.json`. Document that the legacy server is standalone. A corrupt `state.json` currently raises on startup; at minimum show a clear error instead of crashing in a loop.

### B4. Auto-routing must never web-research a CSV supplier name
CSV names are generic synthetic labels (`Apex Technologies 491`, `Global Solutions 900`). Stripping the number or fuzzy-matching would point web search at real, unrelated companies, and the results would sit next to anonymized scores as if they belonged together. Required behavior:
- An exact `supplierID` (`SUPP_\d{5}`) or exact `Supplier Name` resolves deterministically to a dataset answer, never to web research.
- Web research starts only from a company the user typed, together with an explicit confirmation step. `kind:"clarify"` returns prefilled `{company,country,website,scope,mode}` and nothing is spent until the user confirms. This also bounds paid calls: auto mode can cost one cheap classification call at most, never a 6–13-request run.
- When a research run is started from a CSV row's context, the UI must state that the row is synthetic and is not mapped to the researched entity. `save_supplier` already sets `legacy_scores: null` and `numeric_scores` to null; keep it that way and don't copy CSV scores onto the saved record.

### B5. "Research can use supplied data": define where the CSV context goes
`start()` accepts only `company`, `country`, `website`, `scope` (scope capped at 1,600 chars and part of the saved-supplier identity hash). Putting CSV rows into `scope` would:
- change supplier identity (one entity researched twice with different selected rows becomes two "suppliers"),
- leak synthetic scores into web-search prompts as if they were facts,
- truncate silently.

**Fix:** keep CSV context out of the search and extraction prompts. Attach it as a separate `dataset_context: {supplier_ids, columns, values, sha256}` on the run or in the chat turn, and show it beside the dossier, labelled "supplied synthetic data, not evidence about this entity". If core has to change to store that field, it's a small additive field; tell the parent. Extraction can't cite CSV cells anyway, because `ground_findings` requires quotes from the web excerpts, which is correct.

## High (design now; cheap if done early)

### H1. Dataset answers: the LLM selects, the server fills values
For `POST /api/assistant` data answers and charts:
- The LLM (if used) returns only `{supplier_id, column}` references and a whitelisted `metric`.
- The server checks that each ID is in the catalog and each column is in `columns`, then fills `value` and `row` from the catalog. Apply the same pattern as `ground_findings`: drop any reference that fails, and count the drops.
- Chart `points` are computed on the server from cells. They are never numbers the model wrote. `metric` must be a numeric column; `*_Level` columns are text.
- Cap `selected_ids` at 20 and validate them against the catalog. Cap rows sent to the provider (20 rows × the needed columns, not all 60).
- Answers about the total must say the weighting is unknown. `docs/research/score-patterns.md` shows the unweighted mean doesn't reproduce `Total_Risk_Index` (r = 0.99, only 2,186 of 10,000 exact matches). The `risk_*` axes are an illustrative equal-weight grouping (`radar_mapping_version`). They are not the source model.

### H2. No time series
The snapshot has one row per supplier and no dates. Requests for a "trend", "over time" or "last quarter" chart must return a `clarify` or `answer` response saying no history exists. Any existing illustrative trend in the v2 UI keeps its "illustrative" label and is never fed to the assistant as data.

### H3. Progress phases come from real `events[].stage` values only
These stages are emitted: `plan`, `search_query` (×6, all emitted at once before any search starts), `search` / `search_error` (one per category as each completes, 3 concurrent), `extract`, `extract_retry`, `follow_up` (deep only), `partial`, `complete`, `failed`. Map the checklist to these stages:
- Plan, then
- Search 0–6 (count `search` + `search_error` events), then
- Extract, then
- Deep follow-up (0–3) and reconcile, then
- Done or failed.

Don't show percentages or time estimates. Each provider call can take up to 150 s and there's no heartbeat, so the UI should say "waiting for provider" rather than look frozen. Polling `GET /api/research/:id` returns the full run with excerpts, up to 24 KB per source. Poll every 2–3 s, stop on `completed` or `failed`, and stop when the chat closes or the page unloads. After a server restart, in-flight runs come back as `failed` with a message. The persisted chat must re-poll by `run_id` on load and render that state; it must not show a perpetual spinner.

### H4. Citation namespaces
CSV IDs (`SUPP_00001`), research supplier IDs (20 hex characters) and research source IDs (`S1…`) all appear in "supplier" or "citation" contexts. Use `kind: dataset|web`, and use `supplier_id` only for CSV `SUPP_*` values. For web chips, render only `url` values that came from `run.sources` (they've already passed `safe_url`). Show the existing limitation text: "Search provider excerpt; full page not independently verified". Never put a model-written URL in a chip.

### H5. `/api/catalog` provenance
`build_v2.py` serves rows from `supplier_risk_dataset_augmented.csv` (60 columns), but `source` and `sha256` describe the original CSV. Either rename the fields (`source_sha256`) and add `derivative_sha256`, or the "immutable source hash" claim is misleading. Keep the v2 typing rules exactly as they are: numeric columns as int or float, empty values as `null`, two boolean demo columns. Run `json.dumps(..., allow_nan=False)` so a `NaN` can't break the frontend parse.

## Medium (security and robustness, mostly by reusing existing code)

- **Reuse `make_handler`'s guards for every new route.** That means Host allowlist, Origin and `Sec-Fetch-Site` checks on writes, JSON content type only, no chunked bodies, CSP with `connect-src 'self'`, `nosniff`, `no-store`, and binding to `127.0.0.1`. `PUT` needs a `do_PUT` and has to go through `body()`. The legacy handler has no `do_PUT`.
- **Static serving.** `web/app-base.tmp` is currently in `web/` and would be served. Delete build leftovers, or allowlist extensions (`.html .css .js .svg .png .woff2`). Keep the dot-file and `is_relative_to` checks.
- **Render model and CSV text with `textContent` or escaping, never as raw `innerHTML`.** CSP blocks inline script but not markup injection: forged buttons or links in chat. Markdown in answers needs a minimal escaping renderer.
- **Workspace validation.** Accept only known keys. Favorites and compare must be existing `SUPP_*` IDs, deduplicated, with compare at most 20. `region` must be a known `train_region_id`. Draft fields: bounded strings. Write atomically. Reject unknown top-level keys rather than storing them.
- **Errors.** The legacy catch-all returns a generic 502, which is good. Keep provider error text free of keys. `read_environment` merges `os.environ`, so never echo `values` or `config` beyond what `config()` already exposes.
- **No-key path.** `/api/assistant` must still answer deterministic dataset questions, such as ID lookup, comparisons from cells and server-computed charts. Only provider-dependent routes return an explicit "unavailable: no OPENROUTER_API_KEY" response. Tests use a fake client, with no network.
- **Cosmetic.** `HTTP-Referer` is hard-coded to `127.0.0.1:8877`. It's harmless, but update it or make it neutral.

## Router shape (minimal, not overengineered)
1. Deterministic pass: extract `SUPP_\d{5}` and exact names, which become catalog lookups. Regex only finds candidates; it never decides intent on its own.
2. If the message is ambiguous (several names match, or a name matches only after normalization), return `clarify` with the candidates.
3. With selected or resolved rows plus a data question, answer from cells as in H1. A provider call is optional and bounded to one call.
4. If the message names an external company, or mode is `deep` with an identifiable company, return `clarify` with prefilled research parameters. After the user confirms, call `POST /api/research` and return `kind:"research", run_id`. Deep mode only sets `mode:"deep"` and attaches `dataset_context` (B5).
5. Anything else gets a short `answer` explaining what the assistant can do. Don't guess.

## Explicitly out of scope (avoid creep)
Auth, deployment, multi-user sync, websockets/SSE (polling is enough), full-page crawling, numeric scoring of researched entities, and new prototype HTML builds.
