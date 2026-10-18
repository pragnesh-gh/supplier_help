# Integration plan: our `research_agent/` replaces Pragnesh's, chatbot rewired

Decision: the `research-agent` branch package (Tavily + Claude, verification, rules, scoring seam, `report.md` / `result.json`, entry `run_research(...)`) replaces the `research_agent/` package on `origin/main` (OpenRouter + Nemotron + Exa, durable dossiers). The chatbot and report UI in `supplier_app/` + `web/` are rewired to ours through one thin adapter, `research_agent/app_adapter.py`.

Everything below was read from `origin/main` (`git show origin/main:<path>`) and from our working tree. Items marked **ASSUMPTION** concern code still being written (`report_html.py`, `tldr.py`, scoring breakdown); confirm their final signatures before coding the adapter.

Dry run of the merge (`git merge-tree --write-tree HEAD origin/main`): merge base `5e634c6`; the only textual conflicts are `research_agent/__init__.py` and `research_agent/__main__.py` (add/add). Everything else merges cleanly, **which is the trap**: their `core.py`, `server.py`, `demo.py` and `web/` will silently land inside our package unless deleted (section 4).

---

## 1. How the app on main calls its research agent today

### 1.1 Import and call sites (complete list, from `git grep` on origin/main)

| File | Line | What it uses |
| --- | --- | --- |
| `supplier_app/core.py` | 8 | `from research_agent.core import ROOT` (repo root path, used by `catalog()`) |
| `supplier_app/core.py` | 194 (inside `Assistant.answer`) | `from research_agent.core import json_content` (parses the Nemotron reply for the column-picker) |
| `supplier_app/server.py` | 7 | `from research_agent.core import ROOT, ResearchService, Store, OpenRouter, read_environment` |
| `supplier_app/server.py` | 8 | `from research_agent.server import make_handler as research_handler`. `supplier_app` **subclasses their HTTP handler**: `class Handler(research_handler(service, web or ROOT/'web'))`. It inherits `respond`, `validate_host`, `body`, static file serving, `/api/config`, `/api/research*`, `/api/suppliers*`, and overrides `dispatch` for its own routes. |
| `tests/test_research_agent.py` | 11, 13 | `from research_agent.core import (CATEGORIES, OpenRouter, ProviderLengthError, ResearchService, Store, ...)`, `from research_agent.server import make_handler` |
| `tests/test_supplier_app.py` | 11 | `from research_agent.core import ResearchService, Store, OpenRouter` |
| `tests/test_approvals.py` | 10 | same three |
| `.github/workflows/data-check.yml` | | `python -m compileall -q supplier_app research_agent` and `python -m unittest discover -s tests -v` (stdlib only, no `pip install`) |
| `web/*.js` | | Never imports Python. Talks to the HTTP API only (1.2). |

Objects `supplier_app` receives and the members it touches:

- `service` (a `ResearchService`): `.start(values) -> run_id`, `.chat(run_id, message) -> dict`, `.store`, `.client` (OpenRouter: `.key`, `.model`, `.complete(system, prompt, tokens=)`), `.executor.shutdown(...)`, `.config()`, `.finish_report`/`.search`/`.extract` (tests only).
- `service.store` (a `Store`): `.path` (data dir, used for `workspace.json` and approvals), `.get(run_id)`, `.runs()`, `.suppliers()`, `.save_supplier(run_id)`, `.action(supplier_id, action_id, values)`, and tests poke `.data['runs'|'suppliers']` directly (`tests/test_approvals.py` lines 68-69, 111).
- `Assistant.answer` also calls `self.service.client.key` and `self.service.client.complete(...)` for one bounded "which CSV column does this question mean" call. That is **not research**; it is chat routing on Nemotron.

### 1.2 HTTP routes

Server: `python -m supplier_app --env-file .env` (port 8878, loopback only, Host/Origin/Content-Type checks, CSP `default-src 'self'; script-src 'self'; ... frame-ancestors 'none'`). Static files come from `ROOT/web`.

| Route | Handler | Body in / out |
| --- | --- | --- |
| `GET /health` | supplier_app | `{status, catalog_rows}` |
| `GET /api/catalog` | supplier_app | CSV catalog (unrelated to research) |
| `GET/PUT /api/workspace` | supplier_app | favorites, compare, recents, drafts, **chat** (the chat transcript incl. `run_id` per message; up to 100 KB) |
| `GET/POST /api/approvals` | supplier_app | shortlist approval; **freezes a copy of the research run** (`Approvals.submit` calls `research_store.get(record['run_id'])` and stores `snapshot.dossier`; `web/approval.js` line 43-44 reads `dossier.summary`, `dossier.sources[].url/title`, `dossier.id`, `dossier.status`) |
| `POST /api/assistant` | supplier_app `Assistant.answer` | in `{message, mode: auto\|deep, selected_ids[], run_id?, company?, country?, website?, scope?, example?}`; out `{kind: answer\|research\|clarify, answer, citations[], chart?, run_id?, question?}` |
| `POST /api/research` | supplier_app (maps `example` to `demo`) then inherited | in `{company, country?, website?, scope?, mode: basic\|deep, demo?: bool, dataset_context?: [...]}`; out `202 {id, run_id}` |
| `GET /api/config` | inherited | `{live_available, model, categories[], modes, search_engine, demo_company, budgets, evidence_policy}`; `web/chat.js` reads only `live_available` (shows "Live research is unavailable..." when `false`) |
| `GET /api/research` | inherited | `{runs: [{id, company, country, mode, status, created_at, summary}]}` |
| `GET /api/research/<32 hex>` | inherited | the full run object (1.4) |
| `GET /api/research/<id>/export?format=markdown\|json` | inherited | file download; markdown from `markdown_report(run)`, json = run object |
| `POST /api/research/<id>/chat` | inherited | in `{message}`; out `{answer, finding_ids[], source_ids[], new_research:false}`. **No web code calls this route directly**; chat goes through `/api/assistant` with `run_id` (1.6). |
| `GET /api/suppliers` | inherited | `{suppliers: [...]}` |
| `POST /api/suppliers` | inherited | in `{run_id}`; out `201\|200 {...record, created}`; only for `status=="completed"` runs |
| `PATCH /api/suppliers/<20 hex>/actions/A<n>` | inherited | in `{status?: open\|done, owner?}`; out the action |
| static | inherited | `GET /` and `/<path>` from `web/`, dotfiles refused |

Error mapping (kept): `PermissionError`->403, `ValueError/TypeError`->400 (message shown to the user), `KeyError`->404, anything else->502.

### 1.3 Progress / streaming

No SSE or websockets. `POST` returns the run id immediately; a worker thread (`ResearchService.executor`, 2 workers, max 4 active runs) mutates a run dict and calls `store.put(run)` (rewrites whole `state.json`) after every event. The browser **polls** `GET /api/research/<id>` every 1800 ms (`web/chat.js` `poll()`, lines 122-135) while `status` is `queued` or `researching`, and re-renders from the run object. Events are `{at, stage, message}`. The checklist in `progress(r)` (chat.js lines 46-77) is derived from `r.plan[]` (`{category, questions[]}`) plus events: `stage=="search"` and `message.startsWith(category + ":")` means "retrieved", `stage=="search_error"` means "failed".

### 1.4 Run object (what `web/` reads)

`id, schema_version:"research-dossier-v1", status: queued|researching|completed|failed, company, country, website, scope, mode, demo, created_at, completed_at, error, events[{at,stage,message}], plan[{category, questions[]}], sources[{id,title,url,publisher,published_at,accessed_at,excerpt,kind}], findings[{id,category,title,detail,severity,confidence,status,source_ids[],evidence[{source_id,quote,locator?}],follow_up}], categories[{id,label,assessment,confidence,summary,finding_ids,gaps}], gaps[], actions[{id,category,action,priority,status,owner,finding_id?}], summary, entity{requested_name,verification}, limitations[], coverage{state,failed_search_categories}, legacy_scores:null, usage[], research_notes[], dataset_context[]`.

Fields `web/app.js` `riskDocument(r)` (line 1205) and `web/chat.js` `progress(r)` actually dereference: `id, company, status, demo, country, website, scope, entity.verification, dataset_context, summary, error, plan[].category/.questions (crashes if `questions` missing), findings[].id/title/category/severity/confidence/detail/evidence[].quote/.source_id/.locator, gaps, limitations, actions[].action/.owner/.status, sources[].url/title/id/excerpt, events[].at/stage/message, mode, plan.length`.

### 1.5 Persistence

- Ignored `.local/supplier-app/` (app default `--data-dir`; the old standalone server used `.local/research-agent/`; `.local/` is in main's `.gitignore`).
  - `state.json`: `{"runs": {id: run}, "suppliers": {supplier_id: record}}` written atomically (`state.json.tmp` -> replace) on every event. On startup, any run still `queued`/`researching` is flipped to `failed` ("local server stopped").
  - `workspace.json` (+ `.recovery.json`), approvals (`Approvals(directory,...)`).
- Supplier record (from `Store.save_supplier`): `{id: sha256(company|country|website|scope|provenance)[:20], company, country, website, scope, run_id, added_at, summary, legacy_scores:null, actions[], demo, schema_version:"research-supplier-v1", provenance, entity, numeric_scores:{<6 categories>:null, total:null}}`. In the UI it becomes a catalog row with id `research:<id>`; the radar is deliberately not drawn for it (`web/app.js` line 130, `r._research`).
- Dossier JSON schema `config/research-dossier.schema.json` and `config/research-taxonomy.json` (the latter read by `research_plan()` for the per-category questions shown in the UI). The schema is referenced only from `docs/research-agent.md`.

### 1.6 Clarification flow

Two layers, both synchronous in `Assistant.answer`, none inside the research run:
1. Missing company: returns `{kind:"clarify", question}`; `chat.js` sets `state.clarify` which opens the "Company identity and research scope" form (`company, country, website, scope` fields); submitting the form calls `send("Research "+company, identity)`.
2. Company name equals an anonymized CSV supplier: `{kind:"clarify"}` asking for a real legal name.
There is **no** mid-run "which of these companies?" step; their agent never asks. Ours does (status `needs_clarification` after the identity step), so this is new UI (section 3.5).

### 1.7 Report display and export

- Chat bubble (`chat.js progress()`): when `status=="completed"` shows "TLDR" = `r.summary`, counts (`sources`, `findings`, categories covered), buttons `data-chat-report` ("Read report" -> `onReport(run, true)` -> `showRisk(run)`) and `data-chat-add` ("Add as unscored supplier" -> `POST /api/suppliers`).
- `showRisk(run)` (`web/app.js` ~1208): re-fetches the run, opens a dialog with "Print / Save as PDF" (`printDoc(riskDocument(r))`, browser print), an `<a href="/api/research/<id>/export?format=markdown">` link, and "Add as unscored supplier". `riskDocument(r)` renders the run object into HTML client-side (identity, plan, findings with quotes, gaps/limits, buyer actions, source register, activity). The Reports page (`reports()`, line ~1190) lists `state.reports` with an "Open dossier" button.
- Approval memo evidence appendix reuses `riskDocument(r._report)` for research candidates (`memoDocument`, line ~1269).
- Export server-side: `markdown_report(run)` in their `core.py`, JSON = the run object.

### 1.8 Chat follow-up on a run

`web/chat.js send()` posts `/api/assistant` with `run_id: state.run.id` when a completed run is open and the message does not name a company or `SUPP_` ids. `Assistant.answer` then calls `service.chat(run_id, message)` and maps `source_ids` to `citations: [{id, kind:"web", title, url}]` by looking them up in `run['sources']`. `ResearchService.chat` is **deterministic** (no new search): keyword routing for "score/rating" ("No numeric supplier risk score was calculated..."), "gap/missing/unknown", "subsidiary/legal entity", then either keyword overlap on findings (demo or no key) or one Nemotron call that selects `finding_ids`. It returns canned wording if nothing matches.

### 1.9 Tests that depend on the old package

| File | Depends on | Disposition |
| --- | --- | --- |
| `tests/test_research_agent.py` (270 lines, 15 tests) | `research_agent.core.{CATEGORIES, OpenRouter, ProviderLengthError, ResearchService, Store, ...}`, `research_agent.server.make_handler`, their extraction/Exa/Nemotron internals | Delete from `tests/`; keep a copy in the reference folder; replace with `tests/test_app_adapter.py` (section 4, step 9). Its HTTP-boundary tests (static boundary, no secret in `/api/config`, cross-origin/Host/content-type rejection) must be re-pointed at the new handler, not lost. |
| `tests/test_supplier_app.py` | `ResearchService(Store(tmp), OpenRouter({}))`, `Assistant(service, data)`; `test_research_immediate_and_context_separate` monkeypatches `service.start`; `test_http_contract...` expects 400 with the word "unavailable" when no key | Change setup only (4.9). |
| `tests/test_approvals.py` | same three; pokes `store.data['suppliers'|'runs']` | Change setup; keep `Store.data` dict layout so the pokes still work. |
| `tests/test_shortlist.mjs` | frontend shortlist logic, no research | unchanged |
| `.github/workflows/data-check.yml` | `unittest discover -s tests`, `compileall`, no pip | Needs a `pip install -r research_agent/requirements.txt` step and a `pytest research_agent/tests` step (4.10). |

---

## 2. Gap table

"Port" = copy the logic into our package or `supplier_app`; "Adapt" = reimplement against our data model; "Drop" = do not carry over.

### 2.1 What theirs has and ours lacks

| Capability (theirs) | Where | Decision | How |
| --- | --- | --- | --- |
| Durable run store: `Store` with `state.json`, atomic write, interrupted-run recovery, `runs()`, `get()` | `core.py` `Store` | **Port** (keep file format) | `research_agent/app_adapter.py` `Store`. Same `{"runs","suppliers"}` layout so `Approvals`, `Workspace(research_ids)` and existing `.local/supplier-app/state.json` keep working. Add per-run `schema_version` so old and new runs coexist (3.1). |
| Saved suppliers + action checklist (`save_supplier`, `action`, hash id, dedupe) | `Store` | **Port** unchanged except `numeric_scores` (still `null` while scoring is a placeholder) and actions built from our `next_steps` / red-amber flags | adapter `Store` |
| Background execution, 2 workers, "max 4 active runs", start validation | `ResearchService.start` | **Adapt** | adapter `ResearchService.start` validates, builds the run dict, submits `_execute`, which calls `run_research(...)`. Lower active cap to 2 (each of our runs already fans out 6 threads and ~20 paid Tavily calls). |
| Polling API contract (`/api/research*`, `/api/suppliers*`, `/api/config`) | `server.py` | **Port the handler into `supplier_app/http_base.py`**, not into `research_agent/` | `supplier_app` is the only HTTP consumer; our package stays HTTP-free. Copy their `Handler` (respond, validate_host, body, dispatch, static) and add the new report routes (3.4). Standalone `python -m research_agent` stays a CLI (ours). |
| Chat over a finished run (`chat(run_id, message)`) | `ResearchService.chat` | **Adapt** | new `research_agent/run_chat.py` (3.3). Deterministic first; reads `result.flags/areas/followups/next_steps/limits/scores`; no model call needed for v1. |
| Dossier JSON schema (`config/research-dossier.schema.json`), taxonomy (`config/research-taxonomy.json`) | root `config/` | **Drop** (keep in reference copy) | Our contract is the pydantic `ResearchResult`. Optionally emit `docs/result.schema.json` from `ResearchResult.model_json_schema()` in a script. Per-area questions in the UI plan come from our `PlannedSearch` list. |
| `safe_url()` (display-only link sanitizer; blocks non-http(s), credentials, private IPs) | `core.py` | **Port** | into `research_agent/app_adapter.py` (or `untrusted.py` beside our wrapper) and call it on the `website` input in `start()` and on every `source.url` copied into the run. Ours currently validates nothing on the website input before searching. Also keep the JS `safeURL` in `web/api.js`. |
| Saved offline example (Siemens AG, `demo.py` `apply_demo`) | `demo.py` | **Adapt** | Replace by our offline fixture: load `research_agent/examples/sample_result.json` (fictional Veltrava Rail Components GmbH) or run `run_fixture` machinery from `__main__.py` with `FakeLLM`/`FakeSearch`. Keep the `demo: true` flag and the "no live search performed" banner (`result.notice`). Drop the Siemens-only restriction and the hardcoded Siemens button text. The historical Siemens paraphrases are not source quotations and fail our quote check by design. |
| Nemotron / OpenRouter / Exa path (`OpenRouter.complete`, `annotation_sources`, `ground_findings`) | `core.py` | **Drop completely** (code, config, env vars, docs, tests). Decision: OpenRouter, Nemotron and Exa leave the repo. | See 2.3 for the one non-research OpenRouter use (CSV column picker) and its replacement. |
| Safety/boundary tests (static boundary, no secret in config, cross-origin, chunked body, 16 KB body cap) | `tests/test_research_agent.py` | **Port** | into `tests/test_app_adapter.py`, against `supplier_app.server.make_handler` |
| Category plan with per-category questions in UI | `research_plan()` | **Adapt** | `plan` built from `result.plan` grouped by `umbrella`; `questions` = the query strings; placeholder list of 6 areas before the plan event arrives |
| Dataset context handling (`dataset_context` kept apart from public facts) | `start()` | **Port** | run dict keeps `dataset_context`; never passed to `run_research` |
| Deep vs basic mode | `start(mode)` | **Adapt** | ours has one pipeline. `basic` -> `max_followups: 0`; `deep` -> default config (2 follow-ups). Everything else identical. Show in `/api/config.modes`. |
| Markdown export `markdown_report(run)` | `core.py` | **Drop** | use our `report.md` (`render_markdown(result)`); export JSON = `result.json` (+ run envelope) |
| Standalone UI `research_agent/web/*`, `server.py`, `__main__.py` (port 8877) | | **Drop** | main's README already says to use 8878; keep a copy in reference only |

### 2.3 OpenRouter / Nemotron / Exa removal: every use, and what replaces it

Full inventory on `origin/main` (`git grep -i "openrouter\|nemotron\|exa"` outside docs/research history):

| Use | Where | Research? | Decision |
| --- | --- | --- | --- |
| Category searches (Exa through OpenRouter), extraction, deep reconciliation, chat finding-selector | `research_agent/core.py` | yes | Gone with the package; replaced by Tavily + Claude in our pipeline. |
| **CSV column picker** in `Assistant.answer` (`supplier_app/core.py` ~line 194): one bounded Nemotron call, reached only when no column name, alias or risk keyword matched | `supplier_app/core.py` | **no** (the only non-research LLM use) | **Make it deterministic; no model.** Why: it chooses from a closed list of numeric columns, the answer is rebuilt from real cells anyway, and an unmatched question already has a safe fallback (the clarifying question listing what can be inspected). A model would add cost, a key dependency and a prompt-injection surface for plain CSV Q&A. Work: extend `metric_aliases` (e.g. "late"/"on time" -> `Supplier Delivery Rating`, "spend"/"orders" -> `Purchase Order Volume (EUR)`, "changes" -> `Order Change Rate`, "reliab" -> `Order Confirmation Rate`, "credit"/"cash" -> `Financial_Health_Score`), add token-overlap matching against column names, delete the `if metric is None and self.service.client.key:` block and the `json_content` import. Everything else in `Assistant.answer` (ids, name matching, intents, ranking, counts, citations) is already deterministic. Nothing in `supplier_app/` uses a model afterwards. |
| Key check script | `scripts/check_openrouter.py` | no | Delete; `python -m research_agent --check` covers keys. |
| Config | `config/models.json` (`language_model` provider/model/base_url/credential_env, `decision_triage` future Jev via OpenRouter) | no | Rewrite: `language_model` -> `{"provider": "anthropic", "credential_env": "ANTHROPIC_API_KEY", "models_from": "research_agent/config/settings.yaml", "used_for": ["research"]}`; delete the `decision_triage` Jev-via-OpenRouter entry (or mark "not planned"). Keep `mode`, `speech`. |
| Env | `.env.example` (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`) | no | Delete these three; add `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`. |
| Docs | `README.md` lines 25 and 89, `docs/research-agent.md`, `docs/local-app.md`, `docs/delivery-plan.md`, `docs/research/models-speech-and-agents.md`, `docs/prototype-*`/`unified-app-*` reviews | no | Rewrite README, local-app, research-agent, delivery-plan statements; leave dated review notes under `docs/research/` as history but add one line at the top of `models-speech-and-agents.md`: "Superseded: research uses Claude + Tavily (2026-10)". |
| Tests | `tests/test_research_agent.py` (FakeClient/OpenRouter), `tests/test_supplier_app.py`, `tests/test_approvals.py` (`OpenRouter({})`) | partly | See step 9. |
| `read_environment(env_file)` (merge `--env-file` + `os.environ`) | their `core.py` | no | Keep the 12 lines, moved to `supplier_app/env.py` (still needed for `--env-file`). |
| Code search to prove removal | | | CI/test assertion: `git grep -il "openrouter\|nemotron\|\bexa\b" -- . ':!docs/reference' ':!docs/research'` must return nothing. |

There is no `supplier_app/openrouter.py`, no `OPENROUTER_*` variable and no chat-routing model. Per spot: dataset Q&A routing = deterministic (above); company-name detection (3.8) = deterministic; chat over a research run (`run_chat`, 3.3) = deterministic in v1 because it only selects among already-verified flags (if a model is ever needed there, use `research_agent/llm.py` `LLM.structured`, not another provider); research itself = Claude via `research_agent/llm.py`. Claude is the only model anywhere.

### 2.2 What ours has and theirs lacks

| Capability (ours) | Decision | Notes |
| --- | --- | --- |
| Entity resolution with `needs_clarification` (candidates + question) | **Expose** via adapter status `needs_clarification` + UI (3.5) | New UX step the app does not have |
| Trusted-source allowlist, denylist, open-web gap fill with `unverified` labels | Keep | surfaced through `sources[].trust`, TL;DR chips and report.html |
| Exact-quote check + verifier + rules.yaml colours, knock-outs, verdict | Keep | replaces `ground_findings` |
| `scoring.py` seam, `scores` per area + total, scoring breakdown | **Expose** | radar and "How was this scored?" (3.6). Never merged into dataset rankings |
| Budgets (22 searches, 19 extracts, 120 s), `status: partial` | Keep | adapter maps `partial` to run status `completed` with a limitation line and `coverage.state="partial"` |
| `report.md` (two-page), `result.json`, `report_html.py` | Keep | served by new routes |
| `tldr.py` chat summary | Keep | `run["tldr"]` (3.2) |
| Progress events with `kind`, `data`, `elapsed_s` | Keep | mapped to `events[]` (3.2) |
| Config in YAML + prompts, `--check`, `--fixture`, `diff_runs` | Keep | CLI unchanged |
| Tests (pytest, ~12 modules, offline fakes) | Keep | stay at `research_agent/tests/` |
| Disk output `research_agent/output/<slug>-<date>/` | Keep for CLI; app writes its own copy next to the run (below) | |

---

## 3. Thin adapter design

Goal: `supplier_app` and `web/` see the **same run object and routes as today**, filled from our `ResearchResult`. New UI is additive.

### 3.1 Files

```
research_agent/app_adapter.py   # Store, ResearchService, run_from_result(), safe_url(), load_env()
research_agent/run_chat.py      # chat(run, message) -> {answer, finding_ids, source_ids, new_research}
supplier_app/http_base.py       # ported from their research_agent/server.py (HTTP only, no research logic)
supplier_app/env.py             # read_environment() only (merge --env-file with os.environ)
```

`app_adapter.py` public surface (what `supplier_app` imports):

```python
ROOT: Path                                   # repo root (parents[1])
class Store:                                 # same members as theirs
    def __init__(self, path)                 # .path, .data={"runs":{},"suppliers":{}}, lock, flush()
    def put(self, run) / get(run_id) / runs() / suppliers() / save_supplier(run_id) / action(sid, aid, values)
class ResearchService:
    def __init__(self, store, env=None, *, llm=None, search=None, runner=None)   # llm/search/runner injectable for tests
    store; executor                          # ThreadPoolExecutor(max_workers=2), same shutdown calls
    def config(self) -> dict                 # {live_available, categories, modes, budgets, demo_company, evidence_policy, search_engine:"Tavily", model:<gatherer>/<verifier>}
    def start(self, values: dict) -> str     # returns 32-hex run id
    def chat(self, run_id, message) -> dict  # delegates to run_chat.chat
    def retry_with_identity(...)             # not needed: client re-POSTs /api/research (3.5)
```

`supplier_app` import changes (exhaustive):

- `supplier_app/core.py`: line 8 `from research_agent.app_adapter import ROOT`; line 194 (the column-picker block) is deleted together with the `json_content` import; `Assistant(service, data)` keeps its signature and gets a larger alias table (2.3).
- `supplier_app/server.py`: line 7 `from research_agent.app_adapter import ROOT, ResearchService, Store`; `from .env import read_environment`; line 8 `from .http_base import make_handler as research_handler`; `main()` builds `env = read_environment(args.env_file)`, `service = ResearchService(Store(args.data_dir), env)`. `Assistant(service, data)` and `make_handler(service, web=None, data=None, workspace=None)` keep their signatures.

### 3.2 Mapping `ResearchResult` onto the run object

`ResearchService._execute(run)` calls `run_research(run["company"], run["country"] or None, run["website"] or None, on_progress=cb, config=cfg_for(mode))` in the executor thread, then `run_from_result(run, result)`.

Environment: before the first call `load_env(env)` copies `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `RESEARCH_*` from the merged env dict into `os.environ` with `setdefault` (our config and SDK clients read `os.environ`, not a dict). `live_available = bool(ANTHROPIC_API_KEY and TAVILY_API_KEY)`; `start()` raises `ValueError("Live research is unavailable: configure ANTHROPIC_API_KEY and TAVILY_API_KEY on the local server.")` (contains "unavailable", which `test_supplier_app` checks).

Status:

| `result.status` | run `status` | extra |
| --- | --- | --- |
| (running) | `queued` then `researching` | |
| `ok` | `completed` | |
| `partial` | `completed` | `coverage.state="partial"`, limitation "Stopped at the time limit; findings so far", unchanged otherwise |
| `needs_clarification` | `needs_clarification` (**new**) | `clarification: {question, candidates[]}`; treated as terminal by the poller; not saveable as a supplier |
| `error` | `failed` | `error = "; ".join(result.warnings)[:600]` |

Progress callback `cb(ev: ProgressEvent)` (runs on our worker threads; guard with the run lock, throttle `store.put` to at most once per 500 ms plus a forced flush on `done`):

| Our `ev.kind` | run `events[]` entry | Notes |
| --- | --- | --- |
| `identity` | `{at, stage:"identity", message}` | |
| `plan` | `stage:"plan"`; also (re)build `run["plan"]` from `ev.data["steps"]` grouped by `area`: `[{category: area, questions: [query,...]}]` | six entries always, so the checklist shows all areas; `questions` must exist (the old UI crashes without it) |
| `search` | `stage:"search"`, message prefixed `"<area>: "` and `area` field added; area from `ev.data["step"]` (`"operations-2"` -> `operations`) | keeps `startsWith(category + ":")` working with no JS change |
| `extract`, `verify`, `followup`, `report` | `stage` = kind | |
| `warning` | `stage:"search_error"` if message starts with "Search failed"/"Could not read", else `stage:"warning"`; `area` when known | |
| `done` | `stage:"complete"` | |

Category ids: ours are `financial, legal, country, people, operations, reputation`; theirs used `people_safety`. New runs use ours everywhere; old runs keep theirs (the UI only prints the id, with `_` replaced by a space).

`run_from_result(run, result)` fills (legacy-compatible fields in bold, everything the old UI dereferences):

| Run field | From |
| --- | --- |
| **`summary`** | `result.summary` (falls back to `result.verdict`) |
| **`entity`** | `{requested_name: company_input, verification: "confirmed from sources: <legal_name> (<country>)" \| "confirmed from user input" \| "unverified", legal_name, country_code, website}` |
| **`sources[]`** | `{id: s.id, title, url: safe_url(url), publisher, published_at: published_date, accessed_at: retrieved_at, kind: tier, trust, excerpt: ""}`. Ours stores no excerpt in `Source`; the quote lives on the flag, so `excerpt` is the joined quotes of the flags citing that source (keeps the "Retrieved excerpt" disclosure non-empty). |
| **`findings[]`** | one per `Flag`: `{id, category: area, title: summary, detail: summary + rule_note, severity: {high:"high",medium:"moderate",low:"low"}[severity], colour, confidence: "medium" if trust=="trusted" and corroborated else "low", status: {confirmed:"disclosed", alleged:"alleged", unclear:"unknown"}[claim_status], source_ids, evidence: [{source_id, quote}], follow_up: matching followup.question or "", trust, company_stated, knockout, stale, signals}` |
| **`categories[]`** | one per `AreaStatus`: `{id: area, label, assessment: status, confidence, summary: finding, finding_ids: flag_ids, gaps: []}` |
| **`gaps[]`** | `result.warnings` + "not assessed" lines for areas with `coverage=="not_assessed"` |
| **`limitations[]`** | `result.limits` |
| **`actions[]`** | `result.next_steps` -> `{id:"A<n>", category:"", action, priority:"high" if any red flag/knockout else "normal", status:"open", owner:""}` |
| `plan`, `events` | above |
| `coverage` | `{state: "partial"\|"complete", failed_search_categories: [areas whose steps failed]}` |
| `completed_at`, `usage` | now; `[result.stats.model_dump()]` |
| **new** `schema_version` | `"research-run-v2"` (old runs: `"research-dossier-v1"`, left untouched) |
| **new** `result` | `result.model_dump(mode="json")` (full structured result: flags, areas, scores, followups, sources, plan, stats, fingerprint). Omitted from `GET /api/research` list; included on `GET /api/research/<id>`. |
| **new** `verdict`, `scores`, `tldr`, `scoring` | `result.verdict`; `result.scores.model_dump()`; TL;DR dict; scoring breakdown dict (below) |
| **new** `report_md`, `report_html` | stored as files next to `state.json`, not inside it: `<data-dir>/runs/<id>/report.md`, `report.html`, `result.json` (keeps `state.json` small; one `state.json` rewrite per event is already heavy). The run holds `report: {md: true, html: true}`. |

TL;DR: `run["tldr"] = tldr.build_tldr(result)` (**ASSUMPTION**: returns a JSON-serializable dict like `{headline, verdict, chips: [{label, tone: red\|amber\|green\|grey, count?, area?}], one_liner}`; adapt keys to the final `tldr.py`). Backward compat: `run["summary"]` is still set, so the old completion block keeps working until the chips land.

Scoring breakdown: `run["scoring"]` (**ASSUMPTION** about the final function; one of `scoring.explain(result.scores, result.flags, cfg)` or a method on `ScoreCard`): `{scale: "0 = no risk, 100 = maximum risk", total: {score, level, weights, method}, areas: [{area, label, score, level, coverage, trusted_pages, unverified_pages, method, contributions: [{flag_id, summary, colour, weight/points}], sub_scores}], notes: []}`. While scores are `None`, the breakdown must still return the method note ("not scored yet") and per-area coverage so the button works.

Persistence of `result` for the audit trail: `approvals` snapshots `store.get(run_id)`; since `result` is part of the run object, a frozen approval then contains the structured evidence too.

Demo / offline example: `start({"demo": true, ...})` skips key checks and runs `_execute_demo`: loads `research_agent/examples/sample_result.json` (`ResearchResult.model_validate_json`), emits a few synthetic `events` from `result.trail`, sets `demo=True`, `notice` shown. `company` is forced to the fixture's company. `config()["demo_company"]` returns that name so `chat.js` stops hardcoding "Siemens AG".

### 3.3 Chat over a run (`research_agent/run_chat.py`)

`chat(run, message) -> {"answer": str, "finding_ids": [...], "source_ids": [...], "new_research": False}` (identical shape; `Assistant.answer` needs no change). Behaviour, in order, all from `run["result"]` (legacy v1 runs return "This is a pre-migration dossier; open the report" and an empty list):

1. Score/rating/radar/"how was this scored" -> state the per-area scores or "not scored yet" with the method note; cite nothing.
2. Gaps/unknown/"not assessed"/"missing" -> areas with `coverage != "assessed"` + `limits` + `next_steps`.
3. Entity/subsidiary/group -> `entity`, `clarification` history, flags with `entity_match`-style rule notes.
4. Verdict/summary/"what do we know" -> `verdict`, `summary`, top flags (red first).
5. Otherwise keyword-overlap ranking of flags (title + area + event_type), top 3; refusal wording if none ("This report does not establish an answer; no new search was performed").
Each flag line includes its `[n]` source marks and trust label (`✅ trusted` / `🟨 not in our trusted source list`), so the existing citation chips in chat (built from `source_ids`) carry the trust distinction. No new search, no model call in v1. Optional v2: one Claude call through `llm.py` to choose `flag_ids` (mirrors their Nemotron selector).

### 3.4 HTTP layer (`supplier_app/http_base.py`, ported)

Keep all inherited routes (1.2) with these changes:

| Route | Change |
| --- | --- |
| `GET /api/config` | `service.config()` (new fields; `live_available` semantic = both keys) |
| `GET /api/research` | rows add `verdict`, `tldr` (small), `has_report` |
| `GET /api/research/<id>` | returns the run object incl. `result`, `tldr`, `scoring` |
| `GET /api/research/<id>/export?format=markdown\|json\|html` | markdown = `report.md`, json = `result.json` envelope (`{run, result}`), html = `report.html` as attachment |
| **new** `GET /api/research/<id>/report.html` | inline `text/html`, for an `<iframe>`. Response CSP for this route only: `default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'`. **Today's global CSP has `frame-ancestors 'none'`, which would block our own iframe**; `report_html.py` therefore must be script-free (the global `script-src 'self'` also forbids inline scripts) and draw the radar as inline SVG. |
| **new** `GET /api/research/<id>/scoring` | the `scoring` breakdown JSON (same as `run["scoring"]`; separate route so the button can fetch lazily after a rerun of scoring) |
| `POST /api/research` | accepts `country`, `website`, `scope`, `mode`, `demo`, `dataset_context`, plus optional `parent_run_id` (clarification retry, 3.5). 202 `{id, run_id}` unchanged. |
| `POST /api/research/<id>/chat`, `POST /api/suppliers`, `PATCH /api/suppliers/.../actions/...` | unchanged contract |

Also fix while here: `body()` limit is 16 KB for research routes; keep. `Handler.respond` takes an optional `csp=` override so only `report.html` loosens `frame-ancestors`.

### 3.5 Clarification flow (new, small)

- Server: run ends with `status="needs_clarification"` and `run["clarification"] = {"question": "...", "candidates": [{legal_name, country_code, country_name, website, description}]}`.
- `Assistant.answer`: unchanged for the first call (it returns `kind:"research"` immediately).
- `web/chat.js poll()`: terminal on anything except `queued|researching` (already true); in `progress(r)` add a block when `r.status === "needs_clarification"`: the question, one button per candidate (`data-clarify-index`), and a "None of these" hint that opens the identity form.
- Click handler: `POST /api/research {company: cand.legal_name, country: cand.country_code, website: cand.website, scope: r.scope, mode: r.mode, dataset_context: r.dataset_context, parent_run_id: r.id}` then `poll(newRunId)`; append an assistant message with the new `run_id`.
- Because the new call passes country/website, our `identity` step resolves to one entity (`confirmed_by: "user_input"`). The old run stays in the Reports list labelled "needs clarification" (filter these out of the Reports page if it looks noisy).

### 3.6 `web/` changes

All other files (`app.js` catalogue/radar for dataset rows, `train.js`, `supplier-ring.js`, `approval.js`) are untouched.

**`web/api.js`**: none.

**`web/chat.js`** (progress block, `progress(r)`, lines ~46-77):
1. TL;DR chips. Replace the completion block's `<h3>TLDR</h3><p>${esc(r.summary)}</p>` with: verdict line (`r.tldr.verdict`), a chip row `r.tldr.chips.map(c => '<span class="chip chip-'+tone+'">'+label+'</span>')` (red/amber/green/grey counts and "N areas not assessed"), the one-liner, and keep the counts line and the two buttons. Fallback to `r.summary` when `r.tldr` is absent (legacy runs).
2. Buttons: "Read report" (existing `data-chat-report`), add "How was this scored?" (`data-chat-scoring`), keep "Add as unscored supplier".
3. Checklist: use `e.area === p.category` in addition to the `startsWith` test; show "Search failed" for `stage==="search_error"`; label "Not assessed" when `r.categories` says so.
4. `needs_clarification` block (3.5) and `failed` text.
5. Saved example button: text from `state.config.demo_company` ("Open offline example (fictional company)"), request `{demo:true, example:true, mode:"deep"}` without `company: "Siemens AG"`.
6. Click handler: `data-chat-scoring` -> `onScoring(state.run)` callback (new in `createChat({...})` options, wired in `app.js`).

**`web/app.js`**:
1. `showRisk(run)` (line ~1208): for `r.schema_version === "research-run-v2"` render `<iframe class="report-frame" src="/api/research/<id>/report.html" sandbox="" title="Research report"></iframe>` (the radar is inside the report) above/below the action row; actions: "Print / Save as PDF" (`iframe.contentWindow.print()`), "Export report (HTML)" and "Export Markdown" links, "How was this scored?" button, "Add as unscored supplier". For old runs keep the existing `riskDocument(r)` path.
2. `riskDocument(r)` (used by the approval memo, `memoDocument`): keep as is; it still works because the run object stays legacy-compatible (3.2). For v2 runs, prepend a one-paragraph verdict and a flag table from `r.result.flags` (colour, area, summary, trust, `[source]`) so the memo shows our colours and trust marks; do not iframe inside the print root.
3. `scoringDialog(run)`: `dialog("How was this scored? - " + run.company, ...)` rendered from `run.scoring` (fetch `GET /api/research/<id>/scoring`): scale line, total score/level/method note, a table per area (score, level, coverage, trusted/unverified pages, contributing flags with colour and `[n]` links via `safeURL`), the "never ranked against dataset suppliers" note. When all scores are `null`: "No score yet: the scoring method is still being agreed. Here is what the evidence covers", then coverage per area. `onScoring` callback and `data-live-scoring` buttons share it.
4. Radar for research runs. The existing `radar(r, region, table)` draws the dataset's six axes from CSV columns and intentionally refuses research rows (`r._research` at line 130). Do **not** reuse it for agent scores (different axes, different method; the repo rule is real-company scores never share a chart with dataset suppliers). Add `agentRadar(scores)` (or render it server-side inside `report.html`, preferred because the radar then also exists in the print/export copy): six spokes in our area order (financial, legal, country, people, operations, reputation); axis value = `area.score` when not `null`; areas with `coverage==="not_assessed"` or `score===null` are drawn as hollow markers at the rim labelled "Not assessed" (never as 0); legend shows level bands (Low 0-24, Medium 25-49, High 50-74, Critical 75-100). If no area has a score, show "Not scored yet" instead of an empty polygon.
5. `reports()`: show `r.tldr?.verdict` and chips instead of `r.summary` when present; label `status` "needs clarification".
6. Remove the "saved historical example" wording where `r.demo` now means "offline fictional example".
7. Add small CSS to `web/ui.css` (or `styles.css`): `.chip`, `.chip-red/amber/green/grey`, `.report-frame{width:100%;height:70vh;border:1px solid var(--line)}`, scoring table.

**`web/index.html`**: none (the dialog and `#print-root` exist).

### 3.8 Research triggers: hybrid (user decision)

**Rule:** the "Deep research" button and an explicit "research X" request **start a run immediately**. Any other real company name (not a dataset supplier) gets a **one-click "Research <company>?" card** with a time/credit note. Nothing else starts research.

**How "Auto" routing works today** (`Assistant.answer`, `supplier_app/core.py`, all deterministic):

1. Identity extraction: regex `supp_\d{5}` ids (unknown id -> `clarify`); then every catalog name found as a whole-word, case-folded substring (`self.names`). Explicit ids/names override the UI selection (`selected_ids` is only fallback context).
2. `explicit_research = bool(values['company']) or the message contains: research, investigate, web search, latest news, public sources`.
3. `research = explicit_research or (mode == "deep" and no dataset rows matched and no run_id and not a global data question)`. Today the chat's Auto/Deep dropdown is therefore the Deep trigger, and Auto only researches on keywords or the identity form (`company` set).
4. When `research`: company = `values.company`, else only a hardcoded "Siemens AG" regex, else `clarify("Which real legal company should I research?")`. A company equal to an anonymized CSV name -> `clarify`. Otherwise `service.start(...)` and `kind:"research"` + `run_id`.
5. Else: completed `run_id` and no dataset rows -> `service.chat`; otherwise dataset intents.

Gap: in Auto, "Tell me about Knorr-Bremse" or just "Knorr-Bremse" falls to the final `clarify('Select suppliers or name exact supplier IDs...')`. Nothing detects a real company name. CSV supplier names are anonymized, so a real company never matches `self.names`; the dataset match stays the first gate and is not loosened.

| Trigger | Condition | Result |
| --- | --- | --- |
| Deep research button | New `#deep-research` button in the chat composer (replaces the Auto/Deep select). Company from the identity form if filled, else the textarea, else the last company in the conversation. Sends `{company, mode:"deep", trigger:"button"}` | Starts immediately (`kind:"research"`). If no usable company, opens the identity form. |
| Explicit request | Message starts with `research`, `investigate`, `deep research`, `due diligence on`, `check out` (+ name), or contains the existing keywords with a detected name | Starts immediately, as today, now with name extraction instead of the Siemens shortcut. |
| Other real company name | No dataset id/name matched, no explicit keyword, not a follow-up on an open completed run, and the detector finds a company-like span | `kind:"offer"`. Spends nothing. UI shows the card; one click starts the run. |

Server change: the old rule "Deep mode with no dataset match starts research" is **removed**. A run starts only from the button, an explicit request, the identity-form submit, or a clicked offer. `mode` stays in payloads only as run depth (`deep` = default config with follow-ups, `basic` = `max_followups: 0`).

Detector (`supplier_app/company_detect.py`, deterministic, no model):
- candidates: quoted strings; text after "about/on/for/of/regarding" up to punctuation; the whole message when it is 1-6 tokens; runs of capitalised tokens (allowing `&`, `-`, `.`), optionally ending in a legal suffix (`AG, GmbH, SE, SA, S.p.A., N.V., B.V., Ltd, Limited, Inc, LLC, PLC, Corp, Co, KG, AB, Oy, A/S, Pty, Sdn Bhd, KK`).
- reject: any dataset id/name match; words from the existing intent lists (compare, rank, lowest, count, formula, weight, trend...); generic nouns (supplier, risk, company); bare column names/aliases.
- confidence: legal suffix, or >=2 capitalised tokens, or the user typed only the name -> offer; a single capitalised word -> offer with "Did you mean the company ...?" wording.
- Ambiguity is not resolved here. The offer passes the raw name; our identity step decides and returns `needs_clarification` with candidate buttons (3.5). One clarification flow.

Offer response (new `kind`; unknown kinds render as plain answers in old JS):

```json
{"kind":"offer","answer":"\"Knorr-Bremse\" is not in the supplier catalog. It looks like a real company.","company":"Knorr-Bremse","country":"","website":"",
 "offer":{"label":"Research Knorr-Bremse?","note":"Takes about 1.5 to 2 minutes and uses up to 22 Tavily searches (about 42 credits) plus Claude usage. Public sources only; results are not matched to the catalog.",
          "estimate":{"seconds":[80,120],"searches_max":22,"tavily_credits":42,"pages_max":19}}}
```

`estimate` and `note` come from `service.config()["budgets"]` (from `settings.yaml`), never hardcoded in JS.

`web/chat.js`:
- Response handler: `kind === "offer"` pushes a message carrying `offer`/`company`; render a card with `offer.label`, `offer.note`, buttons "Research" (`data-offer-start`) and "Not now" (`data-offer-dismiss`, sets `dismissed` on the stored message). "Research" calls the same `send("Research " + company, {company, country, website, trigger:"offer"})` as the identity form, then `poll(run_id)`; the card then reads "Research started". Offer messages live in the workspace chat transcript (plain objects, under the 100 KB cap).
- Deep research button: `startFromInput()` as in the table; remove the "Research depth" select.
- Guardrails: never auto-start; dataset matches always win; a completed-run follow-up stays chat unless the message explicitly asks to research a different company; one open offer per company; server refuses a third active run (message shown in chat).
- Tests (`tests/test_supplier_app.py`, offline): "Tell me about Knorr-Bremse AG" -> `offer`; "Knorr-Bremse" -> `offer` (soft wording); "Research Knorr-Bremse" -> `research`; button payload (`company` + `mode:"deep"`) -> `research`; "SUPP_00012" / catalog names / "Why is SUPP_00012 high risk?" / "compare these" -> dataset answer, never offer; anonymized-name guard still `clarify`; Deep mode alone no longer starts research.

### 3.9 NotebookLM-style inline citations in the chat (port into `web/chat.js`)

Source of truth: the report agent's structured citation data and the reference page `research_agent/templates/citation_demo.html` (**neither was in the tree when this plan was written; `research_agent/templates/` did not exist. Confirm field names**). The plan assumes:

```json
"citations": [{"n": 1, "source_id": "S3", "title": "...", "publisher": "...", "url": "https://...", "trust": "trusted|unverified", "published_date": "2026-03", "retrieved_at": "...",
               "quote": "exact words from the page", "quote_before": "...", "quote_after": "...",
               "text_fragment": "#:~:text=start,end", "flag_ids": ["F2"], "area": "legal"}]
"tldr": {"verdict": "...", "chips": [...], "segments": [{"text": "Two minor fines were reported", "cite": [1, 4]}]}
```

`tldr.segments` splits the TL;DR into text runs with the citation numbers each rests on. Without `segments` (older runs) the UI prints `summary` followed by the chips.

Adapter (`run_from_result`): store `run["citations"]` and `run["tldr"]["segments"]` from the report agent's builder, so the same numbers appear in chat, `report.html` and `report.md`. `text_fragment` is built server-side from the exact quote (`#:~:text=` + percent-encoded start words, `,`, end words for long quotes; plain text for short ones; commas, dashes and ampersands encoded) and appended to `safe_url(url)` only for http(s) URLs; length <= 600 and charset validated. Deep links are best effort (PDFs, dynamic pages, reflowed text may not scroll), so the panel always shows the quote itself. The browser receives URLs and quotes only, never page text.

`web/chat.js` port (keep the existing dataset `citation()` chip for CSV cells untouched):

1. **Chips.** `tldrHtml(run)` escapes each segment's `text`, then appends `<button class="cite-chip" data-cite-run data-cite-n aria-label="Source n: title">n</button>` per number. Trusted = filled chip; unverified = outlined chip with a marker (mirrors the report's 🟨). Chat follow-up answers from `run_chat` return `citations` extended with `n, quote, text_fragment, trust, publisher, published_date`; `citation()` renders `kind:"web"` entries with a `quote` as the same button chips (not external links).
2. **Side panel.** One shared `<aside id="cite-panel" hidden>` appended to `document.body` by `createChat` (no `index.html` change). `openCite(runId, n)` renders: source card (publisher, title, published date or "date not stated", retrieved date, badge "Trusted source" / "Not in our trusted source list", company-stated note, domain); the quote with context, `<span>before</span><mark>quote</mark><span>after</span>`, every part through `esc()`, never raw page HTML; "Also supports" chips for other flags/areas using that source; "Open source" (`safeURL(url)`) and "Open at quote" (`safeURL(url)+text_fragment`, note about PDFs/dynamic pages); "Copy quote". Verification line: "Quote checked against the page text we retrieved" (or "from the search snippet; full page not read" when `text_origin` is `search_snippet`).
3. **Interaction.** Second click on the same chip closes. `Esc` closes the panel first, then the drawer (extend the `keydown` handler before `close()`). Focus goes to the panel header and returns to the chip. Non-modal, `aria-live="polite"`. Include the panel's buttons in the Tab-trap list, or render it as a bottom sheet inside the drawer under 720 px.
4. **CSS** (`web/ui.css`): `.cite-chip` (inline, ~20 px, 28 px touch target), `.cite-panel` fixed right with width `min(420px, 100vw)` positioned beside the existing `#chat-drawer` rule's width (read it, do not hardcode), `mark` highlight with a `forced-colors` fallback.
5. **State.** `state.cite = {runId, n}` is not persisted. Chat messages store only `run_id`; chips are re-rendered from `GET /api/research/<id>` after reload.
6. **Report parity.** `report.html` (iframe, script-free) uses the same numbers; the numbers link to its own reference list with plain anchors. The chat panel is the only interactive citation viewer.
7. **Module and tests.** New `web/citations.js` with pure helpers (`tldrHtml`, `findCitation`, `quoteParts`, `fragmentLink`) imported by `chat.js`; test them in `tests/test_citations.mjs` (Node, like `tests/test_shortlist.mjs`). Python test: every `n` used in `segments` exists in `citations`, each quote is non-empty and present in the retrieved text, fragments are well formed, no fragment for non-http URLs. Manual: chip opens the panel with the highlighted quote; Esc order; 390 px width.

### 3.7 `Store.save_supplier` and the unscored-supplier tag

Unchanged in behaviour. `numeric_scores` stays `{<areas>: null, total: null}` until the scoring method exists, and the UI keeps saying "scores remain Unknown". When scoring lands, put them in a separate read-only `agent_scores` key, never in the CSV-compatible `numeric_scores`/`Total_Risk_Index` columns. Dedupe hash input is unchanged; add `entity.legal_name` to the record so two inputs that resolve to one company are visible.

---

## 4. Merge procedure

Run from the primary checkout once the other agents' work on `research-agent` is committed (the working tree currently has many uncommitted edits plus untracked `scoring.py`, `dates.py`, `config/scoring.yaml`, `data/`, tests; commit all of that first, or the merge will refuse or mix them).

```sh
# 0. Safety: everything committed, tests green on our side
git status --short                      # must be clean
pytest -q research_agent/tests
git tag pre-main-merge                  # easy rollback: git reset --hard pre-main-merge

# 1. Start the merge without committing
git fetch origin
git merge --no-commit --no-ff origin/main
#   expected conflicts: research_agent/__init__.py, research_agent/__main__.py (add/add)
#   expected clean adds that we must remove: research_agent/{core,server,demo}.py, research_agent/web/*

# 2. Keep a copy of theirs for reference, outside any importable package
mkdir -p docs/reference/pragnesh_research_agent
git archive origin/main research_agent tests/test_research_agent.py config/research-dossier.schema.json config/research-taxonomy.json \
  | tar -x -C docs/reference/pragnesh_research_agent
#   -> docs/reference/pragnesh_research_agent/research_agent/{core,server,demo,__main__,__init__}.py, web/*
#   no __init__.py is added at docs/reference/..., pytest/unittest discovery in tests/ does not enter it;
#   rename the .py files to .py.txt if you want compileall/mypy/IDEs to ignore them completely:
find docs/reference/pragnesh_research_agent -name '*.py' -exec sh -c 'mv "$1" "$1.txt"' _ {} \;

# 3. Conflicts under research_agent/: take ours
git checkout --ours research_agent/__init__.py research_agent/__main__.py
git add research_agent/__init__.py research_agent/__main__.py

# 4. Remove their files from the live package (they merged cleanly, so git will not warn)
git rm -f research_agent/core.py research_agent/server.py research_agent/demo.py
git rm -rf research_agent/web
git rm -f config/research-dossier.schema.json config/research-taxonomy.json   # now only in the reference copy
git rm -f tests/test_research_agent.py                                         # copy kept in reference
#   check nothing else of theirs sits under research_agent/: 
git ls-files research_agent | grep -v -E '^research_agent/(tests/|config/|prompts/|examples/|data/|[a-z_]+\.(py|md|ini|json|txt)$|\.env\.example$|\.gitignore$)'

# 5. Add the adapter pieces (section 3.1) and rewire supplier_app imports
#    research_agent/app_adapter.py, research_agent/run_chat.py
#    supplier_app/http_base.py (from the reference copy of their server.py), supplier_app/env.py (read_environment only)
#    edit supplier_app/core.py, supplier_app/server.py

# 6. Root-level files that merged "cleanly" but are now wrong (check each, edit by hand)
#    .env.example        add ANTHROPIC_API_KEY=, TAVILY_API_KEY= and DELETE OPENROUTER_API_KEY / OPENROUTER_MODEL / OPENROUTER_BASE_URL; delete scripts/check_openrouter.py; rewrite config/models.json (2.3)
#    .gitignore          already ignores .env, .env.*, output/, .local/ (keep); nothing to add
#    config/models.json  language_model block rewritten to Anthropic (research only); delete decision_triage/Jev-via-OpenRouter
#    README.md           "Research engine" paragraph (line 25) and key sentence (line 89): replace OpenRouter/Exa/port 8877 text
#    docs/local-app.md   code map row for research_agent/
#    docs/research-agent.md  rewrite header: pointer to research_agent/README.md; archive Nemotron verification record
#    docs/local-demo-script.md  Siemens example step -> offline fictional example (or a live run)
#    docs/research/unified-app-*.md  historical, leave

# 7. Web changes (section 3.6): web/chat.js, web/app.js, web/ui.css

# 8. Dependencies: main promises "no installation". Research now needs pip packages.
#    Document in README: python -m venv .venv && pip install -r research_agent/requirements.txt
#    (anthropic, httpx2, pydantic, PyYAML, python-dotenv). The app must still start without them:
#    import research_agent lazily inside ResearchService._execute so catalogue/chat-on-CSV work with stdlib only,
#    and config()["live_available"] is False with a clear message when the import or the keys are missing.

# 9. Tests
#    tests/test_supplier_app.py   setUp: ResearchService(Store(tmp), {})   and  Assistant(service, data)
#                                  (test_research_immediate... keeps monkeypatching service.start)
#    tests/test_approvals.py      setUp: Store(tmp) from app_adapter; ResearchService(store, {}); keep store.data pokes
#    tests/test_app_adapter.py    NEW, offline, no keys, injected llm=FakeLLM, search=FakeSearch:
#         start() validation (company required, bad mode, demo flag), 'unavailable' without keys
#         run completes -> run dict has summary/sources/findings/plan[].questions/categories/actions/tldr/scoring
#         needs_clarification run -> status + clarification payload; not saveable as supplier
#         partial -> completed + limitation; error -> failed with message
#         progress events -> events[] with area prefixes; checklist-compatible
#         Store: persistence round trip, interrupted run recovery, save_supplier dedupe, action PATCH partial update
#         chat(): score question, gaps question, relevant flag, no-match refusal; never calls the network
#         HTTP: static boundary (/../.env, /.env 404), /api/config has no secret, cross-origin 403, Host 403,
#               content-type 400, 16 KB body cap, report.html content-type + CSP frame-ancestors 'self',
#               export formats, legacy v1 run still served
#    (all of this is a port of the boundary tests in the deleted test_research_agent.py)

# 10. CI (.github/workflows/data-check.yml)
#    add:  - run: pip install -r research_agent/requirements.txt
#          - run: pytest -q research_agent/tests
#    keep: unittest discover -s tests, compileall -q supplier_app research_agent
#    Do not let compileall/unittest see docs/reference (the .py.txt rename above handles it).

# 11. Verify, then commit the merge
python -m compileall -q supplier_app research_agent
python -m unittest discover -s tests -v
pytest -q research_agent/tests
git add -A && git commit      # merge commit; message lists: replaced research_agent, adapter, reference copy location
```

Files to delete (summary): `research_agent/core.py`, `research_agent/server.py`, `research_agent/demo.py`, `research_agent/web/{app.js,index.html,styles.css}`, `tests/test_research_agent.py`, `config/research-dossier.schema.json`, `config/research-taxonomy.json`. Files kept for reference: `docs/reference/pragnesh_research_agent/`.

### Environment variables and `.env` location

| What | Theirs | Ours | After the merge |
| --- | --- | --- | --- |
| Research LLM | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (nemotron), `OPENROUTER_BASE_URL` | `ANTHROPIC_API_KEY`; optional `RESEARCH_GATHERER_MODEL`, `RESEARCH_VERIFIER_MODEL`, `RESEARCH_*_EFFORT` | Research uses ours. |
| Search | Exa through OpenRouter (same key) | `TAVILY_API_KEY` | New second key required. |
| Chat routing | OpenRouter (same client) | none | None. Deterministic; no key, no model. |
| File | repo-root `.env` via `--env-file .env` (read by `read_environment`, `os.environ` wins) | `research_agent/.env`, then CWD `.env`, via `python-dotenv` in `research_agent/__main__.py` | `python -m supplier_app --env-file .env` is unchanged for users: `read_environment()` merges the file and `os.environ`, and the adapter copies the research keys into `os.environ`. A single root `.env` with all three keys works; `research_agent/.env` still works for the CLI. Root `.env.example` documents all keys. |

### How to run afterwards

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r research_agent/requirements.txt
cp .env.example .env            # fill ANTHROPIC_API_KEY, TAVILY_API_KEY (optional OPENROUTER_API_KEY)
python -m supplier_app --env-file .env          # app at http://127.0.0.1:8878
python -m research_agent --check                 # key/config check, no paid calls
python -m research_agent --fixture               # offline CLI demo
python -m research_agent "Knorr-Bremse" --country DE --website knorr-bremse.com   # CLI run, writes research_agent/output/
```

Manual smoke test: open 8878, chat -> identity form -> "Open offline example" (no keys) -> TL;DR chips, Read report (iframe with radar), "How was this scored?", Add as unscored supplier, ask "what is still unknown?" in the chat (answers from the run), create a shortlist approval with the research candidate and confirm the frozen snapshot shows summary and sources. Then one live run with keys, including an ambiguous company name for the clarification buttons.

---

## 5. Risks, what to tell Pragnesh, order

### Top risks

1. **Silent clean merge leaves a broken hybrid.** Only `__init__.py` and `__main__.py` conflict. Their `core.py`/`server.py`/`demo.py`/`web/` are plain additions and will sit next to our modules; `supplier_app` would keep importing them and the app would appear to work on the old stack. Mitigation: step 4 deletions plus a test that asserts `import research_agent.core` fails and `supplier_app` imports only `research_agent.app_adapter`.
2. **Approvals, workspace and saved suppliers depend on the old `Store` layout and run shape.** `Approvals.submit` snapshots `research_store.get(run_id)`; `Workspace` validates `research:<id>` ids from `store.suppliers()`; existing `.local/supplier-app/state.json` holds v1 runs and saved suppliers. A different on-disk format or missing fields (`plan[].questions`, `sources[].url`, `summary`) would break approvals, the Reports page or the memo appendix. Mitigation: keep `state.json` layout and legacy fields, per-run `schema_version`, legacy runs read-only and rendered by the old `riskDocument`; adapter tests that load a v1 fixture.
3. **Stdlib-only promise and CI break.** Main states "no package installation"; CI runs `unittest discover` with no `pip install`; our pipeline needs `anthropic`, `httpx2`, `pydantic`, `PyYAML`. Mitigation: lazy import in `_execute`, `live_available=False` when deps/keys are missing (catalogue and CSV chat still work), CI gets a pip step and a pytest step, README documents the venv.
4. **Different cost, latency and failure shape.** One run is up to ~22 Tavily searches (~42 credits at advanced depth), ~20 page reads and 40-100 s, with `partial` at 120 s; their run was 6 Exa searches in one provider. Two workers x 6 threads can hit rate limits; a `needs_clarification` result is new and the UI must handle it. Mitigation: active-run cap 2, `basic` mode = no follow-ups, clear status mapping (3.2), clarification UI (3.5), surface `stats` and `warnings` in the report.
5. **Security regressions in the web layer.** The report iframe needs `frame-ancestors 'self'` on one route while the global CSP forbids framing; `report.html` must be script-free and every URL passed through `safe_url`/`safeURL` (source URLs come from the open web; the website input was previously sanitized by their `safe_url`). The Host/Origin/body-size checks live in the ported handler and must stay covered by tests. Mitigation: per-route CSP, `sandbox=""` iframe, tests listed in step 9.
6. Smaller: (a) category id mismatch `people` vs `people_safety`; (b) dataset radar vs agent radar must stay separate, scores never ranked with the CSV; (c) the offline example is now fictional (the Siemens demo story in `docs/local-demo-script.md` changes); (d) deterministic chat is weaker than their Nemotron-assisted selector until v2; (e) the `tldr.py` / `report_html.py` / scoring breakdown shapes are not final, so the adapter mapping in 3.2 may need small edits; (f) OpenRouter/Nemotron/Exa are gone: research needs `ANTHROPIC_API_KEY` + `TAVILY_API_KEY`, dataset Q&A needs no key; (g) removing the model column picker means a few oddly phrased CSV questions get the clarifying question instead of a guessed column (fix by growing the alias table).

### What breaks for Pragnesh

- `from research_agent.core import ...` and `from research_agent.server import make_handler` no longer exist; `python -m research_agent --env-file .env` (port 8877 standalone UI) is gone; the CLI is now `python -m research_agent "<company>"`.
- Live research needs `ANTHROPIC_API_KEY` + `TAVILY_API_KEY`; OpenRouter, Nemotron and Exa are removed from the repo entirely; dataset Q&A routing is deterministic and needs no key.
- Dossier schema and taxonomy files are removed from `config/`; the export JSON is `ResearchResult` (`result.json`), not `research-dossier-v1`.
- Their Siemens saved example is replaced by an offline fictional example.
- Any local branch of theirs touching `research_agent/` will conflict; changes in `supplier_app/`, `web/`, `tests/` (other than `test_research_agent.py`) are not touched except for the import lines and the research UI blocks listed above.
- Old local runs stay readable; their old chat on a v1 run is limited to "open the report".

### Message to send Pragnesh (draft)

> We are merging `research-agent` into main. Decision: our `research_agent/` (Tavily + Claude, trusted-source allowlist, exact-quote checks, red/amber/green rules, scoring seam, HTML report) replaces yours under the same name, and the chatbot is rewired through `research_agent/app_adapter.py`. Your `research_agent/{core,server,demo}.py` and `web/`, the dossier schema/taxonomy and `tests/test_research_agent.py` are copied to `docs/reference/pragnesh_research_agent/` (not importable). `supplier_app/` keeps working: only its imports change (`research_agent.app_adapter` for `ROOT/Store/ResearchService`; your HTTP handler moves to `supplier_app/http_base.py` and `supplier_app/env.py`, code unchanged). Routes, `/api/assistant` and `/api/research*` shapes, `state.json` layout, approvals and saved suppliers are unchanged; the web gets TL;DR chips, a report view with radar, a "How was this scored?" button and a clarification step. You will need two keys (`ANTHROPIC_API_KEY`, `TAVILY_API_KEY`) and `pip install -r research_agent/requirements.txt`. OpenRouter, Nemotron and Exa are removed from the repo entirely. Please do not push changes to `research_agent/` or `tests/test_research_agent.py` on main until the merge lands; tell us if you rely on anything in your package that is not listed here.

### Order of steps

1. Freeze: ask Pragnesh to hold pushes touching `research_agent/`, `supplier_app/`, `web/chat.js`, `web/app.js`. Commit all of our work; tag `pre-main-merge`.
2. Finish `report_html.py`, `tldr.py` and the scoring breakdown, and fix their output shapes (the adapter mapping depends on them).
3. Write `research_agent/app_adapter.py` + `run_chat.py` and `tests/test_app_adapter.py` against a throwaway copy of `supplier_app` on our branch (no merge yet).
4. `git merge --no-commit origin/main`; steps 2-4 of section 4 (reference copy, take ours, delete theirs).
5. Rewire `supplier_app` imports; add `http_base.py`, `env.py`; delete the model column-picker and extend the alias table; add a test that greps for openrouter/nemotron/exa outside docs history; fix `tests/test_supplier_app.py` and `tests/test_approvals.py` setup; run unittest and pytest.
6. Web changes (TL;DR chips, report iframe + radar, scoring dialog, clarification buttons); manual smoke test with the offline example, then one live run.
7. Update `.env.example`, README, docs, CI; commit the merge; push the branch and open the PR rather than merging straight to `main`.
8. Message Pragnesh with the draft above; ask them to rebase any open work and re-run their live checks on the new stack.
