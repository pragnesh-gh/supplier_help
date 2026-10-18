# Supplier app: local run and review

The active product is the local web app, not a regenerated prototype HTML file. All work is on `main`.

## Start

From the repository root, with Python 3.12 or newer:

```powershell
python -m supplier_app --env-file .env
```

Open **http://127.0.0.1:8878**. No frontend installation or build is needed. The app serves only `web/` and explicit API routes, not the repository or environment files. The OpenRouter credential is read server-side. Without a configured key, supplied-data questions and the explicitly labelled historical example remain available; live web research reports its unavailable state.

## Code map

| Directory | Responsibility |
| --- | --- |
| `web/` | App shell, discovery/comparison, 3D train and exploded part assemblies, Copilot conversation and report UI |
| `supplier_app/` | Local app entry, CSV catalogue, assistant routing, workspace state and HTTP API |
| `research_agent/` | Existing bounded live research pipeline, evidence validation and durable dossiers; legacy standalone UI retained |
| `config/` | Research taxonomy, dossier schema and selected model configuration |
| `docs/` | Source CSV/dictionary, augmented demo assignments, design references and evidence |
| `tests/` | Backend contracts, grounding, persistence and HTTP boundaries |
| `prototype/` | Earlier self-contained HTML designs retained as historical references |
| `.local/` | Ignored local workspace, saved runs and supplier records |

## Journey

1. Select a train system. The radar shows the supplier with the lowest supplied Total Risk Index in the selected system or part, against its system distribution. Counts refer to illustrative component assignments, not the physical train's risk.
2. Open Discovery to see the selected system as an exploded assembly. Click a component or its labelled chip to filter by part, then filter/rank the actual source rows. Select up to 20 and open Compare. Selection survives changing filters.
3. Open the Copilot bubble. Ask the exact financial comparison or a supplied-data question. Inspect the small citation chips and any structured graph.
4. Ask to research a named company. Auto routes recognized dataset identities to source data; Deep requests more extensive research. Resolve ambiguous identities rather than equating anonymized rows with real companies.
5. The same conversation shows actual planning/retrieval/follow-up/synthesis events. Close the drawer to continue exploring; reopen it to inspect progress and cited findings.
6. View/export a research report and add the researched company to the research list. Its numerical CSV scores remain unknown.
7. From Compare, prepare a shortlist of three to five suppliers. Review the optional risk-based suggestion, write trade-offs and negotiation questions, and name the requester and reviewer. Submit to save an immutable request for approval to negotiate. View it under Approvals and Print/Save as PDF. No notification is sent and no approval is implied. See [the shortlist contract](shortlist-approval.md).

## What is and is not measured

The supplied CSV is a single synthetic snapshot. Component assignments and prior-use tags are demo metadata. Example trend lines are explicitly illustrative and never used as evidence. Real telemetry is not implemented. Actual research progress is workflow status, not supplier telemetry. The live pipeline uses retrieved excerpts and source links; it does not claim exhaustive web coverage or independent full-page audits.

## Local-only delivery

The user explicitly selected localhost for this pass. There is no public deployment, authentication or jury account, and no claim that a local URL is remotely accessible. The challenge's public live URL and access-sharing requirements remain submission decisions. The runnable app, source data, tests and demo journey are prepared for local review.


The current 3D review instance uses port 8880: `python -m supplier_app --port 8880 --env-file .env`. Older development instances were stopped. The default command still uses 8878. Use one browser tab for edits; concurrent tab changes are not merged.

Recently viewed lists suppliers actually inspected, most recent first, within the selected system. Used before retains illustrative prior-sourcing history labels. Favorites and lowest-risk ordering are available in Discovery.
