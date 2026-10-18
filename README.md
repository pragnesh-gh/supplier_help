# Supplier Help · Siemens Supplier Risk Intelligence

Supplier research and review tools for the Siemens challenge. This branch adds a local live research agent alongside the original deterministic prototype. It supports investigation and drafting; supplier qualification remains a separate buyer process.

## Research agent

Run from this worktree with Python 3.12+ (no dependency installation):

```powershell
python -m research_agent --env-file ..\supplier_help\.env
```

Open **http://127.0.0.1:8877**. The optional `--env-file` reuses the existing server-side OpenRouter configuration without copying its credential into this checkout. Alternatively, set `OPENROUTER_API_KEY` in the process environment or this worktree's ignored `.env`. Never paste the key into chat or browser code.

Use **Basic** for a bounded first pass over all six categories, or **Deep** for the same coverage plus targeted follow-ups. Enter a legal company name, country/domain when known, and the component or sourcing question. Live research uses the configured Nemotron model and OpenRouter web search, which incur provider charges. The UI shows the actual plan, progress, sources, findings, unknowns and actions. The explicit Siemens historical example works without credentials and is labelled separately from live research.

Research and saved supplier records persist in ignored `.local/research-agent/`. Save a completed investigation to the research list and manage its diligence actions there. Markdown/JSON exports and the printable report use the same dossier. Research-derived suppliers remain separate from anonymized CSV rows and retain unknown numeric scores.

- [Research questions and evidence method](docs/research/deep-research-method.md)
- [Observed synthetic-score patterns and limits](docs/research/score-patterns.md)
- [Running, architecture, and limitations](docs/research-agent.md)

The earlier prototype below remains offline and simulated. Its scope statements apply to that prototype, not the new research-agent route.

## Inputs

- `docs/supplier_risk_dataset.csv`: original challenge data, 10,000 anonymized suppliers.
- `docs/risk_criteria_description.md`: original score definitions. All risk scores run from 0 (no risk) to 100 (maximum risk), including positively named scores.

## Original prototype scope

Explore and filter actual data, compare at most 20 suppliers, inspect evidence, try scripted grounded questions and simulated dictation, review a separately labelled company-research fixture, and export a shortlist memo. No live LLM, web crawling, microphone recording, login, or procurement-system integration is claimed.

The latest clickable prototype lives on `prototype/train-risk-v2`; the earlier layouts remain on `prototype/supplier-workbench`, separate from the research/setup baseline on `main`. No UI choice has been validated by a buyer yet.

## Open the prototype

### New train overview (v2)

On `prototype/train-risk-v2`, open `prototype/train-risk-v2.html` after building:

```sh
python scripts/augment_dataset.py
python scripts/build_v2.py
```

The output embeds the augmented dataset and the 3D renderer for offline use. It starts with a compact train overview; Discovery, comparison, Deep Research and report previews are separate screens. The guided tour walks through the simulated sourcing journey. **My suppliers** adds favorite/previously-used collections with card and trend-row views; click a labelled illustrative sparkline to inspect example values. Comparison includes the same charts. No historical measurements are asserted. Research replay does not call a backend. Speech input remains a later design option; v2 uses text.

The derivative `docs/supplier_risk_dataset_augmented.csv` preserves the original data and adds reproducible demo system/part assignments, relationship tags and six derived risk summaries. The manifest records the allocation, overrides and equal within-axis weights. These summaries do not reconstruct the supplied Total Risk Index. Research-added records have unknown scores and stay separate from the anonymized source rows.

Reports use **Print / Save as PDF** through the browser. They are draft approval requests or limited-scope research reports, not approvals or qualification records. Reloading resets prototype state.

Design evidence: [v2 brief](docs/prototype-v2-brief.md), [bounded rail research](docs/research/train-parts-and-radar.md), [adversarial review](docs/research/prototype-v2-challenge.md), [Opus design review](docs/research/opus-v2-design-review.md), [final visual review](docs/research/opus-v2-final-review.md), and [verification record](docs/prototype-v2-review.md). The brief's final decisions supersede alternatives in the research notes.

### Earlier layouts (v1)

Check out `prototype/supplier-workbench`, then double-click `prototype/supplier-workbench.html`. It embeds all 10,000 supplied rows and needs no server, internet, API key or package installation. The floating bottom switcher chooses three layouts (`?variant=A`, `B`, or `C`). Start the guided demo or explore freely; state resets when the page reloads.

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

Keep OpenRouter credentials in your process environment or ignored `.env`. `.env.example` and `config/models.json` document the proposed backend configuration; the HTML never reads them. The user confirmed Nemotron; the selected initial candidate is `nvidia/nemotron-3.5-lightning`. Its public catalog entry was verified on 2026-10-18, but credentialed model/provider access remains unverified. The baseline uses deterministic logic plus Nemotron. Jev via OpenRouter is an optional later triage experiment; OpenAI Decisions is out of the current scope. There is no image-input requirement. Speech transcription produces text before the language-model step.

```sh
python scripts/check_openrouter.py --catalog
# After supplying OPENROUTER_API_KEY locally; no inference is sent:
python scripts/check_openrouter.py --key
```

These are read-only setup checks, not an implemented LLM backend. They never print credentials. No paid inference has been run.

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
