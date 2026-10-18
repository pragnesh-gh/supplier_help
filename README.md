# Supplier Help · Siemens Supplier Risk Intelligence

Research and a disposable, deterministic HTML prototype for the Siemens challenge. This is a design review workspace, not a production procurement system.

## Inputs

- `docs/supplier_risk_dataset.csv`: original challenge data, 10,000 anonymized suppliers.
- `docs/risk_criteria_description.md`: original score definitions. All risk scores run from 0 (no risk) to 100 (maximum risk), including positively named scores.

## Current scope

Explore and filter actual data, compare at most 20 suppliers, inspect evidence, try scripted grounded questions and simulated dictation, review a separately labelled company-research fixture, and export a shortlist memo. No live LLM, web crawling, microphone recording, login, or procurement-system integration is claimed.

The clickable prototype lives on `prototype/supplier-workbench`, separate from the research/setup baseline on `main`. No UI choice has been validated by a buyer yet.

## Open the prototype

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
- [Buyer roles, demographics and existing tools](docs/research/buyers-and-workflows.md)
- [Model, speech and agent research (with current scope update)](docs/research/models-speech-and-agents.md)
- [End-to-end build plan, deliverables and two-minute demo script](docs/delivery-plan.md)
- [Reproducible dataset audit](docs/data-audit.json)

## Repository access

Private by default because the supplied dataset has no redistribution licence in this workspace. Share repository access with the jury explicitly before submission. No licence is asserted over the supplied inputs.

Research and delivery notes are in `docs/`. The deployed app, authentication and two-minute final video remain subsequent implementation milestones.
