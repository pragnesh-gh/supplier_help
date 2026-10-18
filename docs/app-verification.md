# Unified app verification

Baseline: aaf5b7a on main. Implementation:798584f plus reviewed fixes.

## Acceptance record

- Original source audit:10,000 rows,46 columns, original SHA preserved. Augmented assignments and derived axes have separate provenance.
- Backend suite:26 passing tests covering catalog types, exact cells/charts, identity precedence, ranking direction, context isolation, bounded workspace recovery, persistence and HTTP host/origin/static boundaries. Provider tests use fakes.
- Browser1440x790 and1366x640: compact selectable2D train, floating assistant, separate discovery,20-column comparison retained after reload.390x844 chat has no horizontal overflow.
- Data chat: financial source values54/65/53, interactive bars, citation opens SUPP_00731 physical row732 and Financial_Health_Score53.
- Research: explicit historical example remains labelled. One actual basic Siemens AG run completed through UI on2026-10-18:27 source links,4 retained observations across3/6 categories. All6 retrieval categories emitted real events. Follow-up evidence-gap question used the same dossier without new search. This is an integration test, not independent validation of company findings.
- Report: source URLs and historical-paraphrase labels present. Adding a researched company produces a separate unscored record; reload retains it without changing original numeric rows.
- Workspace:20 comparison IDs, research record and memo fields restored after immediate reload. Saves serialized, pending recovery retained locally. History bounded by encoded size.
- Print: approval preview exports an A4 PDF with original46 fields separated from14 augmented fields and their hashes. Browser print remains a draft review handoff.

## Review rounds

Opus preflight: `docs/research/unified-app-preflight.md`.
Opus final code review: `docs/research/unified-app-final-review.md`.
Independent spec review: `docs/research/unified-app-spec-review.md`.

Review findings prompted fixes to metric direction, explicit identity precedence, actual checklist stages, reset generation guards, PDF provenance, history budgets, workspace recovery and async save ordering. Final follow-up review and recording are recorded below when complete.

## Scope

Localhost only, as requested; no public hosting or jury credentials. Example trends are synthetic, and real telemetry is absent. Research retrieves provider excerpts and links, with bounded searches and explicit evidence gaps; it is not exhaustive crawling or independently audited source text. Earlier prototypes are retained as references; the active app is `web/` + `supplier_app/`.

## Final review resolution

Opus follow-up is in `docs/research/unified-app-review-followup.md`. Its remaining JSON-size blocker was fixed by measuring compact UTF-8 JSON on both sides; the HTTP regression saves an exactly95,000-byte rich conversation. Normal saves no longer use browser keepalive quotas and consume their responses before the next queued write. Research workspace entries store compact record references. A single-browser recovery snapshot protects interrupted saves; concurrent edits from multiple tabs are not conflict-merged.

Final checks:26 backend tests pass; all four frontend modules pass syntax checks. Four-page PDF verification confirms the draft header on every page. Final checked app instance runs at http://127.0.0.1:8879 (default CLI port remains8878).

Local walkthrough: `output/demo/supplier-app-demo.mp4` (120seconds, silent, historical example labelled). Final browser run ended with `Saved locally`. Output media remains ignored; share the local artifact separately from Git.
