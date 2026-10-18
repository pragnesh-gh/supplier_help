# Demo video

## [▶ Watch the 2-minute demo video](https://github.com/pragnesh-gh/supplier_help/releases/download/demo-knorr-2026-10-18/supplier-help-demo.mp4)

**Start here, reviewers:** a complete narrated walkthrough in 1080p, with background music and captions. No installation or API keys are needed to watch. If your browser downloads the MP4, open it in your video player. [View the GitHub release](https://github.com/pragnesh-gh/supplier_help/releases/tag/demo-knorr-2026-10-18).

> **Prefer a human-led walkthrough?** [Watch the companion demo](https://cap.so/s/2dbjdb7ns5eqg63).

## Judge's checklist

Mapped to the [Siemens challenge brief](docs/siemens-challenge-brief.md). The timestamps below point to evidence in the demo.

- [x] **UI — explore, filter, rank and compare suppliers.** Browse the 10,000-row catalogue by train system and component, compare up to 20 suppliers side by side (16 shown in the demo), inspect risk profiles and build a five-candidate shortlist. **See 0:42–1:06 and 1:16–1:37.**
- [x] **Chatbot — answer questions grounded in the supplied data.** Ask Gretel a plain-language financial-risk question, inspect the generated chart, and follow its citations to the exact dataset values behind the answer. **See 1:06–1:16.**
- [x] **AI research agent — investigate a real company and return sourced evidence.** Give the agent Knorr-Bremse AG; follow its research progress, review the six-area risk report and source links, then save the company as a candidate. The pipeline plans searches, gathers public-source evidence and follows up on potential red flags. **See 0:08–0:42; recorded research waiting time is shortened.**

**Creativity — start with the train, finish with a decision.** An interactive 3D train turns a large supplier catalogue into a component-led exploration: select Bogies and watch the assembly unfold. Gretel turns questions into charts with inspectable evidence, while the shortlist carries research gaps and trade-offs into an exportable approval request. The creative thread is one connected buyer journey, from *which part?* to *why these suppliers?*

**Submission deliverables:** source code and challenge data are in this repository; the two-minute demo is linked above. The app is runnable locally using the instructions below. **A deployed live-app URL and jury login are not yet provided**, so that challenge deliverable remains outstanding.

### Demo chapters

| Time | What the demo shows |
| --- | --- |
| 0:00 | Select Bogies in the train overview |
| 0:08 | Research **Knorr-Bremse AG**, inspect findings and sources, and add the candidate |
| 0:42 | Explore the animated Discovery assembly and supplier catalogue |
| 0:54 | Compare **16 catalogue suppliers** side by side |
| 1:06 | Ask the chatbot a financial-risk question and inspect its chart and source data |
| 1:16 | Build and review a **five-candidate shortlist** |
| 1:37 | Prepare a **three-candidate approval request** and export its evidence |

# Supplier Help — Siemens Supplier Risk Intelligence

Supplier Help brings catalogue comparison, evidence-grounded chat and public company research into one sourcing workspace. Buyers can move from a train system to a defensible shortlist, keeping source evidence and unanswered questions attached to the decision.

The current deliverable is a **working, single-user local web app**. The video records the actual app, including real company research; research waiting time is shortened in the edit. It is not a hosted service or a supplier qualification decision.

## What you can do

- **Explore the catalogue:** browse 10,000 anonymized challenge suppliers through a train-system overview and animated component assemblies; filter and rank candidates.
- **Compare candidates:** inspect up to 20 suppliers side by side across supplied risk, delivery and operational measures, with profiles and exact source cells.
- **Ask Gretel:** query supplied data in an expandable conversation, view charts and follow citations to the underlying values.
- **Research a real company:** follow the agent's progress, inspect a six-area risk report and its public sources, then save the researched candidate.
- **Build a shortlist:** review candidates, select three to five and save a request for approval to negotiate with frozen evidence. Export through Print / Save as PDF.
- **Keep your workspace:** revisit suppliers, manage favorites and reopen saved reports and approval requests.

## Quick start

Requires **Python 3.12+**. No Node.js, frontend installation or frontend build is needed.

```sh
git clone https://github.com/pragnesh-gh/supplier_help.git
cd supplier_help
python -m supplier_app --offline-fixture
```

Open **http://127.0.0.1:8878**.

This is the simplest review mode: catalogue exploration and data questions work locally, and every company-research request uses a clearly labelled, invented offline example. **It does not reproduce the live Knorr-Bremse investigation.** Workspace changes persist under the ignored `.local/` directory.

### Enable live company research

In a Python virtual environment, install the research dependencies:

```sh
python -m pip install -r research_agent/requirements.txt
```

Copy [`.env.example`](.env.example) to `.env` and set `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`. Stop the offline server, then start:

```sh
python -m supplier_app --env-file .env
```

Keys stay on the local server and are never read by the browser. Live research uses paid provider APIs. ElevenLabs is used for demo narration, not required to run the app. Without research credentials, catalogue/data answers and the offline example remain available; live research reports that it is not configured.

## Suggested reviewer journey

1. Select **Bogies** in Overview and open Gretel. In live mode, ask: `Research Knorr-Bremse AG in Germany for bogie-mounted braking equipment. What risks and evidence should we investigate?`
2. Inspect the completed report and a source, save the researched company, and add it to the shortlist.
3. Open **Discovery**, watch the assembly unfold, and filter/rank catalogue suppliers. Select candidates across pages and open **Compare**.
4. Ask Gretel: `Which of SUPP_04741, SUPP_02570 and SUPP_06655 has the lowest financial risk? Show a bar chart.` Open a citation to inspect the source value.
5. Add four catalogue candidates to make five shortlist options. Review the differences, pick three, and record the rationale and remaining questions.
6. Save the approval request, reopen it under **Approvals**, and use **Print / Save as PDF**.

See the [local app guide](docs/local-app.md) and [shortlist approval workflow](docs/shortlist-approval.md) for details.

## Evidence and scope

The original [challenge dataset](docs/supplier_risk_dataset.csv) contains 10,000 anonymized supplier rows. The [risk criteria](docs/risk_criteria_description.md) define the supplied scores: risk runs from **0 (no risk) to 100 (maximum risk)**, including positively named score fields. The [challenge brief](docs/siemens-challenge-brief.md) provides the original context.

- Train-system and part assignments, prior-use tags and example trends are **illustrative demo metadata**, not verified product-fit claims or historical measurements.
- Real-company research stays separate from anonymized catalogue rows. Research-added candidates retain **unknown catalogue scores**; missing values are not treated as zero risk.
- The research pipeline uses Tavily search, Claude gathering and verification, exact-quote checks, scoring and HTML/Markdown reports. Public-source findings are bounded evidence, not exhaustive due diligence.
- An approval request is a saved **request to negotiate**. Saving it sends no notification and does not authorize an award or qualify a supplier.
- The app is loopback-only and single-user, with no hosted deployment or authentication. A local URL is not accessible to remote reviewers; use the video or run the app locally.

Read the [research method](docs/research/deep-research-method.md), [score patterns and limits](docs/research/score-patterns.md), and [research verification notes](docs/research-agent.md).

## Technical overview

| Area | Implementation |
| --- | --- |
| Web interface | Local HTML, CSS and JavaScript; 3D train and exploded assemblies; vendored icons and assets |
| App backend | Python local HTTP app, CSV catalogue, assistant routing and durable workspace storage |
| Public research | Tavily + Anthropic Claude, evidence validation and saved dossiers |
| Reports | HTML/Markdown research reports and printable approval requests |
| Demo production | HyperFrames, ElevenLabs narration, music and synchronized captions |

| Directory | Contents |
| --- | --- |
| `web/` | Current app UI, comparison, chat and report views |
| `supplier_app/` | Local server, catalogue, APIs and workspace state |
| `research_agent/` | Research pipeline and app adapter |
| `config/` | Research taxonomy, schemas and model configuration |
| `docs/` | Challenge inputs, design decisions and verification records |
| `tests/` | Backend, grounding, persistence and HTTP tests |
| `prototype/` | Historical standalone HTML prototypes |

## Verification and development

```sh
python scripts/audit_dataset.py
python -m unittest discover -s tests
python -m pytest research_agent/tests
```

The automated tests do not require paid API calls. Research tests require their Python dependencies, including pytest. `python -m research_agent --check` checks research configuration without paid calls. See the [implementation contract](docs/web-app-implementation.md) for app boundaries.

Development is on `main`. Earlier HTML prototypes remain in `prototype/` as historical design references; use `python -m supplier_app` to review the current product. The [v2 brief](docs/prototype-v2-brief.md), [reviewed design decisions](docs/research/review-and-decisions.md), and [Gretel visual design notes](docs/research/gretel-chat-ui.md) preserve the design history.

## Challenge inputs

The supplied dataset and challenge documents retain their original ownership. No redistribution licence over those inputs is asserted by this repository.
