# Supplier Help · Siemens Supplier Risk Intelligence

Research and a disposable, deterministic HTML prototype for the Siemens challenge. This is a design review workspace, not a production procurement system.

## Inputs

- `docs/supplier_risk_dataset.csv`: original challenge data, 10,000 anonymized suppliers.
- `docs/risk_criteria_description.md`: original score definitions. All risk scores run from 0 (no risk) to 100 (maximum risk), including positively named scores.

## Current scope

Explore and filter actual data, compare at most 20 suppliers, inspect evidence, try scripted grounded questions and simulated dictation, review a separately labelled company-research fixture, and export a shortlist memo. No live LLM, web crawling, microphone recording, login, or procurement-system integration is claimed.

The clickable prototype will live on `prototype/supplier-workbench`, separate from the research/setup baseline on `main`. No UI choice has been validated by a buyer yet.

## Setup

Python 3.12+; no dependencies are required for the data audit or prototype.

```sh
python scripts/audit_dataset.py
```

Keep OpenRouter credentials in your process environment or ignored `.env`. `.env.example` documents the proposed backend configuration; the HTML never reads it. Model choice is provisionally NVIDIA Nemotron 3.5 Lightning, subject to confirming the user's intended model and checking account/provider access. Optional Jev and OpenAI Decisions are alternative future triage adapters, not requirements for this prototype.

## Repository access

Private by default because the supplied dataset has no redistribution licence in this workspace. Share repository access with the jury explicitly before submission. No licence is asserted over the supplied inputs.

Research and delivery notes are in `docs/`. The deployed app, authentication and two-minute final video remain subsequent implementation milestones.
