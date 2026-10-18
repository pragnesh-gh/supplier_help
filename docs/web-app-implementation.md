# Unified supplier web app implementation

Baseline: aaf5b7a. Work directly on main. Preserve prototype/ as historical references; no new prototype builds for the app.

## User requirements
One runnable web app: all 10,000 CSV suppliers, filtering/ranking, max 20 comparison, six-axis profiles, favorites/prior-use collections, reports and approval drafts. Compact interactive 2D train with system selection and accessible alternatives. Landing has no permanent Copilot panel. Floating accessible chat opens a persistent conversation; deep research and data answers stay there. Observable actual research phases/checklist, clean source citation chips, structured chart cards. Auto routing with explicit optional deep mode, accurate company/CSV identity boundaries. Deep research can use selected supplied-data context. No invented time series or live telemetry. Existing illustrative trends may remain labelled. Save user state, integrate existing research backend rather than separate iframe apps. API secrets stay server-side. All changes on main, review via Opus, commit before handoff.

## Ownership / structure
- Backend agent: supplier_app/*.py, tests/test_supplier_app*.py. Reuse research_agent core; may change core only if required and tell parent. Own backend entry, catalog/query/assistant/session persistence HTTP integration. Default localhost:8878.
- Frontend agent: web/* only. Extract useful v2 HTML/CSS/JS into maintainable files; no build dependency needed. Fetch catalog endpoint and use actual APIs. Keep old prototype untouched. Own chat, train, all UI integration.
- Parent: docs, deployment files, README, integration fixes coordinated, review and browser QA.

## API contract
GET /api/catalog -> same payload as v2 embedded data: {columns,rows,source,sha256,manifest}; row arrays typed as original v2, full 10000 augmented source. Immutable source hash.
GET /api/config -> existing research config with live availability (no secrets).
Existing research routes under /api/research and /api/suppliers retained: GET runs, POST create {company,country,website,scope,mode:basic|deep,demo:boolean}, GET run:id, POST run:id/chat {message}, GET export?format=json|markdown, POST /api/suppliers {run_id}, PATCH supplier:id/actions/A1.
POST /api/assistant {message,mode:auto|deep,selected_ids:[],run_id?:string,company?:string,country?:string,website?:string,scope?:string} -> {kind:answer|research|clarify,answer:string,citations:[{id,kind:dataset|web,title,url?,supplier_id?,column?,value?,row?}],chart?:{type:bar,metric,label,points:[{label,value}]},run_id?:string,question?:string}. Return response field names exactly. Research response returns immediately with run_id; frontend polls GET existing research run and shows actual events/status/plan. Core run shape source of truth inspect research_agent/core.py. No guessed API shape.
GET /api/workspace -> {favorites:[]|null,compare:[],drafts:[],chat:[]} (null favorites means seed defaults). PUT /api/workspace accepts same with bounds/validation, persisted locally per configured storage. Frontend may use own scoped draft fields inside draft objects, but must document. Include selected train region in workspace optional region.
GET /health -> status without secrets.
Server serves web/ only. Legacy research server remains compatible. User confirmed localhost only: loopback and existing host/origin validation; no external deployment or jury login for this pass. Validate untrusted requests and outputs, bound paid calls, no paid calls in tests. Do not print/read .env credential values.

## Routing policy
IDs and exact supplied names resolved deterministically. Clarify ambiguous queries; regex only candidate extraction, not sole intent engine. Answer supported comparisons/explanations from actual cells, totals weights unknown. General supplied-data questions may use bounded provider extraction over selected rows with grounded citations. Web research requires identifiable company; do not silently treat anonymized names as verified legal names. Deep mode adds research depth but retains CSV context. Existing live research uses excerpts and links; show its limits. No fabricated citations or history.

## Acceptance
Full suite + source audit + app served browser flow: train -> discovery -> compare -> data chat citation/chart -> research phase progress -> report/add -> draft -> print; reopen state; unsupported/ambiguous query; no-key graceful explicit unavailability; keyboard chat close/Escape and mobile; static path/credential boundary. One-command localhost launch and honest instructions. User explicitly defers public live URL/jury credentials. A 2-minute demo recording remains a submission artifact to prepare once UI flow passes.

