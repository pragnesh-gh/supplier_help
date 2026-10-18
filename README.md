# Supplier Help · Siemens Supplier Risk Intelligence

Supplier research and review tools for the Siemens challenge. The main branch contains the unified local web app, research engine, historical prototypes, and design references. It supports investigation and drafting; supplier qualification remains a separate buyer process.

## Run the app

Python 3.12+; no frontend installation or build is required.

```powershell
python -m supplier_app --env-file .env
```

Open **http://127.0.0.1:8878**. The app combines the complete supplier catalogue, Discovery, max-20 comparison, collections, approval drafts and a floating Sourcing Copilot. Data questions and bounded company research stay in the same conversation. The compact white-and-red 3D train opens system-specific exploded assemblies in Discovery. Click a part to filter suppliers; system and part assignments remain illustrative. Overview offers Recently viewed and Used before tabs. Discovery opens with a brief assembled-to-exploded turn; reduced motion skips it.

The landing radar defaults to the lowest supplied-total-risk supplier in the selected system or part. Cab glazing follows the train nose surface. From Compare, build a shortlist of 3–5 candidates and save a request for approval to negotiate, including trade-offs, negotiation questions and frozen source evidence. Saved requests live under Approvals and can be printed. See [the shortlist workflow](docs/shortlist-approval.md).

Credentials stay on the server. Without `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`, catalogue/data answers and the offline research example still work; live research reports that it is not set up. Start with `--offline-fixture` to run every research request on the invented offline example (no keys, no network). Live requests incur provider usage. The app is loopback-only, with durable local workspace and dossier storage. It is a single-user local deliverable, not an authenticated hosted service.

The UI uses a compact Material-style presentation layer based on the supplied design references. Google Material Symbols are vendored locally with their license and pinned source manifest in `web/vendor/material-symbols/`; no runtime font or icon CDN is required.

[Local app guide and code map](docs/local-app.md) ? [Implementation contract](docs/web-app-implementation.md) ? [Two-minute demo journey](docs/local-demo-script.md)

## Research engine

`research_agent/` is the research pipeline (Tavily search, Claude gatherer and verifier, exact-quote checks, scoring, HTML/Markdown report). The app calls it through `research_agent/app_adapter.py`; live research needs `pip install -r research_agent/requirements.txt` and the two keys in `.env`. The chat answer is a TL;DR card (score, level, coverage, 6-area radar, cited points); the full report opens from the card and is saved under Reports. CLI: `python -m research_agent "Company" --country DE`.

- [Research method](docs/research/deep-research-method.md)
- [Score patterns and limits](docs/research/score-patterns.md)
- [Research engine verification](docs/research-agent.md)

Research-derived suppliers remain separate from anonymized CSV rows, with unknown numeric scores. Retrieved excerpts and linked source claims do not constitute supplier qualification.

## Inputs

- `docs/supplier_risk_dataset.csv`: original challenge data, 10,000 anonymized suppliers.
- `docs/risk_criteria_description.md`: original score definitions. All risk scores run from 0 (no risk) to 100 (maximum risk), including positively named scores.

## Historical prototype scope

Explore and filter actual data, compare at most 20 suppliers, inspect evidence, try scripted grounded questions and simulated dictation, review a separately labelled company-research fixture, and export a shortlist memo. No live LLM, web crawling, microphone recording, login, or procurement-system integration is claimed.

All development now happens on `main`. Both prototype versions are preserved as separate files under `prototype/`; no branch switching is needed. No UI choice has been validated by a buyer yet.

## Historical HTML prototypes

### New train overview (v2)

On `main`, open `prototype/train-risk-v2.html` after building:

```sh
python scripts/augment_dataset.py
python scripts/build_v2.py
```

The output embeds the augmented dataset and the 3D renderer for offline use. It starts with a compact train overview; Discovery, comparison, Deep Research and report previews are separate screens. The guided tour walks through the simulated sourcing journey. **My suppliers** adds favorite/previously-used collections with card and trend-row views; click a labelled illustrative sparkline to inspect example values. Comparison includes the same charts. No historical measurements are asserted. Research replay does not call a backend. Speech input remains a later design option; v2 uses text.

The derivative `docs/supplier_risk_dataset_augmented.csv` preserves the original data and adds reproducible demo system/part assignments, relationship tags and six derived risk summaries. The manifest records the allocation, overrides and equal within-axis weights. These summaries do not reconstruct the supplied Total Risk Index. Research-added records have unknown scores and stay separate from the anonymized source rows.

Reports use **Print / Save as PDF** through the browser. They are draft approval requests or limited-scope research reports, not approvals or qualification records. Reloading resets prototype state.

Design evidence: [v2 brief](docs/prototype-v2-brief.md), [bounded rail research](docs/research/train-parts-and-radar.md), [adversarial review](docs/research/prototype-v2-challenge.md), [Opus design review](docs/research/opus-v2-design-review.md), [final visual review](docs/research/opus-v2-final-review.md), and [verification record](docs/prototype-v2-review.md). The brief's final decisions supersede alternatives in the research notes.

### Earlier layouts (v1)

From `main`, double-click `prototype/supplier-workbench.html`. It embeds all 10,000 supplied rows and needs no server, internet, API key or package installation. The floating bottom switcher chooses three layouts (`?variant=A`, `B`, or `C`). Start the guided demo or explore freely; state resets when the page reloads.

Rebuild after changing the template or source data:

```sh
python scripts/build_prototype.py
```

Optional local preview, serving only the prototype directory:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory prototype
```

Then open `http://127.0.0.1:8765/supplier-workbench.html`. Never serve the repository root if you have saved `.env` there.

## Setup

Python 3.12+; no dependencies are required for the data audit or prototype.

```sh
python scripts/audit_dataset.py
```

Keep `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` in your process environment or the ignored `.env` (see `.env.example`); the HTML never reads them. `python -m research_agent --check` validates config and keys without paid calls. No paid calls are needed for the automated tests (`python -m unittest discover -s tests`, `python -m pytest research_agent/tests`).

## Read next

- [Reviewed research and design brief](docs/research/review-and-decisions.md)
- [UX strategy and product requirements](docs/research/ux-strategy-and-requirements.md)
- [End-to-end UX research plan](docs/research/ux-research-plan.md)
- [Prototype UX audit and recommended test direction](docs/research/prototype-ux-audit.md)
- [Buyer roles, demographics and existing tools](docs/research/buyers-and-workflows.md)
- [Model, speech and agent research (with current scope update)](docs/research/models-speech-and-agents.md)
- [End-to-end build plan, deliverables and two-minute demo script](docs/delivery-plan.md)
- [Reproducible dataset audit](docs/data-audit.json)

## Repository access

Private by default because the supplied dataset has no redistribution licence in this workspace. Share repository access with the jury explicitly before submission. No licence is asserted over the supplied inputs.

Research and delivery notes are in `docs/`. The deployed app, authentication and two-minute final video remain subsequent implementation milestones.

## Working branch

Use `main` in `supplier_help` for ongoing edits. The former UI and research branches were consolidated on 18 October 2026. The secondary `supplier_help-research-agent` worktree is retained as a detached snapshot; its ignored local runs and exports remain there. Use the primary checkout for new work rather than creating separate feature branches. Historical branch references in review notes describe the original capture, not the current workflow.


### Gretel chat and visual answers

Gretel keeps data questions and public research in one expandable conversation. Ask `Show radar risk profile for SUPP_00012, SUPP_00450 and SUPP_00731` for the six derived axes, or compare a supplied metric for a bar chart. Inline source references open the exact dataset cell or public source; chart cards include an exact-values table. Unknown radar values are omitted, never zero-filled. A completed research dossier can answer `Show evidence coverage chart` with retained-observation counts, explicitly separate from risk scores. The first five radar profiles are plotted for legibility; all supplied profiles remain in the table.

The UI uses the existing palette and local assets. [Visual research and contact sheet](docs/research/gretel-chat-ui.md) document the LangChain inspiration; no LangChain runtime dependency was added.
