> Superseded (2026-10-18): the OpenRouter/Nemotron/Exa research engine and its standalone UI were removed. Research now runs through `research_agent/` (Tavily + Claude); see `research_agent/README.md` and `docs/integration-plan.md`. The text below is kept as history.

# Running the supplier research agent

The primary requirement is the [Siemens challenge brief](siemens-challenge-brief.md): plan a real-company investigation, search public sources and company material, follow red flags and deliver a linked risk report. The [previous v2 brief](prototype-v2-brief.md) supplies UX context and data separation rules. This is a new local application in `research_agent/`; the existing prototype files are preserved.

## Start

From the primary `supplier_help` checkout on `main`:

```powershell
python -m research_agent --env-file .env
```

Open http://127.0.0.1:8877. Python 3.12+ is sufficient; there is no package installation or frontend build. The server serves only `research_agent/web`, not the repository or its credentials. The key stays server-side. Using `--env-file` is optional when the process environment or local ignored `.env` already contains configuration. `OPENROUTER_MODEL` defaults to the repo's selected `nvidia/nemotron-3.5-lightning`.

Without a key, use the explicit historical Siemens example to inspect the complete workflow. Live research never silently substitutes that example after a provider error. Public search and inference require a working OpenRouter account, provider availability, and connectivity and incur charges.

## What to try

1. Enter the exact legal name, country and website when known. Add a sourcing scope, such as a particular part and production site. A parent-group report is contextual until the contracting entity is verified.
2. Choose Basic or Deep and start. Inspect the category plan and real progress events. All six categories remain visible even when the sources cannot support a conclusion.
3. Read findings beside their source links and supporting excerpts. Check source dates, evidence status, coverage and limitations before relying on a conclusion.
4. Ask the chat what a finding means or what evidence is still needed. Answers use the current dossier; an unanswered question is a prompt for further diligence, not an invitation to invent facts.
5. Open the report, export Markdown/JSON or print/save PDF. The export is a dated research snapshot, not procurement approval.
6. Save the company to the research list. Assign and complete follow-up checks there. The record has its own provenance and unknown numeric scores; it is not matched to a synthetic `SUPP_*` row.

## Two outputs, one evidence set

The investigation view explains the work: scope, plan, events, sources, linked findings and gaps. The risk report organizes the same evidence for a reviewer: executive summary, six category assessments, unresolved questions and recommended diligence. Saved supplier records and their action queue formalize the output for subsequent work.

The detailed intended evidence contract, category question bank and report template are in [the research method](research/deep-research-method.md). Some parts of that target contract, such as automatic registration-ID resolution, independent corroboration and action-resolution evidence review, require subsequent implementation and validation. Do not read a documented target as a completed check.

JSON exports have a versioned, machine-readable [dossier schema](../config/research-dossier.schema.json). Source IDs join findings to the source register, and finding IDs join actions to observations. The schema describes structure; the backend separately checks that live supporting quotations occur in retrieved excerpts. Neither check proves that an interpretation is correct. Historical example summaries are explicitly distinguished from live source quotations.

## Current research budget

Basic performs six category searches and one structured extraction request. Deep performs those six searches, an initial extraction, up to three adaptive searches and a reconciliation extraction. Each extraction may retry once after an output/JSON limit, so the maximum is eight provider requests for Basic and thirteen for Deep. At most three category searches run concurrently. Each search requests up to five Exa results. Requests time out after 150 seconds; total latency can be several minutes and depends on the provider. A request may return fewer results or no useful evidence. Configured limits are visible in the UI; they are engineering budgets rather than a guarantee of comprehensive research. Chat selects from existing findings and does not trigger new searches.

## Scoring policy

The original dataset is synthetic and lacks raw evidence, dates and a published weighting formula. [The reproducible pattern analysis](research/score-patterns.md) finds consistent level bands and correlated scores, but cannot establish a real-world scoring model. The application uses qualitative triage with source support and explicit gaps. It leaves research-derived numerical scores unknown. Neither missing evidence nor completed diligence automatically reduces risk.

## Operating limits

This is a loopback-only development application, not the deployed authenticated jury app. There are no supplier contacts, automated approvals, certification verification guarantees, scheduled monitoring or production procurement writes. Source material is untrusted evidence. Public search does not provide sanctions clearance or legal advice. Exact company, site, component and transaction scope still require buyer review.

Search excerpts and cited URLs are not equivalent to auditing complete source documents. The report must retain the retrieval limitation; assess the original source before a high-consequence decision. Model extraction can still misread relevant evidence even when the URL is real. A failed or incomplete search is recorded as a gap.

Local runs and saved records persist in ignored `.local/research-agent/`. Keep that directory private when it contains sensitive sourcing notes. The provided CSV stays byte-for-byte unchanged.

## Verification on 18 October 2026

- Fifteen automated tests pass. They exercise basic/deep request budgets, bounded extraction retries, citation/quotation rejection, partial search and reconciliation failures, unknown scores, historical-example identity boundaries, evidence-status preservation in chat, saved-record deduplication, restart persistence, independent action updates, and HTTP/static-file boundaries.
- A live deep investigation of Knorr-Bremse AG completed using the configured Nemotron model and Exa search. It retained 40 source URLs and six exact-quotation-checked observations across five of the six categories, and performed three adaptive follow-up searches. The sixth category remained an evidence gap. This verifies the execution path, not the truth of every extracted interpretation or current supplier qualification.
- The first live attempt hit an output limit after retrieval. Disabling optional model reasoning for these bounded structured tasks and adding one bounded extraction retry corrected that failure. Retrieved sources were reused to verify the extraction correction before repeating the full journey.
- Browser checks covered live launch, progress, evidence, six report category sections, chat, saved historical/live records, action owner/status edits, reload, and Markdown/JSON export. A 390-pixel viewport had no document-level horizontal overflow. The original CSV audit still passes and its source hash is unchanged.

The completed live dossier and report are available in the local workspace. Generated exports are ignored at `output/knorr-bremse-research.json` and `output/knorr-bremse-research.md`. They contain machine-extracted public-source allegations and disclosures requiring review; their presence is not an independent verification of those claims.
