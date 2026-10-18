# Supplier research method and report contract

Prepared 18 October 2026. This is the methodology for a supplier investigation, not a report about a particular company. The executable question bank is [research-taxonomy.json](../../config/research-taxonomy.json).

## Which brief governs this work

The original repository's `docs/` contains [the Siemens challenge](../siemens-challenge-brief.md), [the v2 prototype brief](../prototype-v2-brief.md), the [risk criteria](../risk_criteria_description.md), CSVs and existing research notes. No file with “session brief” in its name was found there. The Siemens challenge is the primary product brief: a buyer names a real company; the agent plans, searches public/company/news sources, follows red flags and produces a source-linked risk report. The current user's request makes this an actual working investigation interface.

The v2 brief describes the previous, explicitly simulated frontend. Its useful inherited rules are separate research records, explicit unknown scores, duplicate protection, selected train-system context and separate risk-report versus approval-request templates. Its simulation-only scope does not satisfy the new request for a working research agent. Its final decisions supersede the preliminary weighted radar proposal: `radar-v1-equal` is a disclosed equal-weight grouping of CSV columns, not recovered source mathematics.

## Two deliverables from one evidence set

1. **Understand the research:** show the user's scope, identity match, question plan, searches attempted, sources actually read, dated evidence cards, contradictory evidence, follow-up branches and gaps. Show process events and concise explanations, not hidden model reasoning or an invented activity log.
2. **Make a risk report:** generate a dated, source-linked decision-support snapshot from that same evidence. Every material conclusion references evidence IDs; every gap becomes a specific next action. Do not turn a confident writing style into a stronger evidence claim.

The investigation structure follows a risk-based diligence loop: establish scope, identify and assess impacts, decide mitigations, track results and communicate limitations. OECD describes these steps as part of responsible-business due diligence; its guidance does not validate this app's categories or a numeric supplier rating. [OECD responsible business conduct](https://www.oecd.org/en/topics/responsible-business-conduct.html).

## What to investigate in the six categories

| Category | Specific checks | Procurement question |
| --- | --- | --- |
| Financial | Latest available entity-level accounts; operating cash flow; liquidity; debt maturities; going concern; insolvency; rating changes; concentration | Can this legal entity support the proposed order and payment terms? |
| Legal & governance | Identity and ownership; relevant sanctions/export restrictions/debarment; proceedings and final findings; case status; remediation | Is there a transaction-specific restriction or unresolved compliance issue requiring review? |
| Country exposure | Production and sub-tier sites; logistics routes; conflict and trade restrictions; natural hazards; energy/infrastructure continuity | Which locations can interrupt this actual supply chain? |
| People & safety | Serious incidents; safety enforcement; worker rights; industrial disputes; audit scope; corrective actions | Are workers exposed to unresolved harm and can the relevant facility operate responsibly? |
| Operations | Part/site capability; quality and recalls; capacity and lead time; delivery evidence; sub-tier concentration; cyber resilience; qualification | Can the proposed component be delivered and qualified with an evidenced recovery plan? |
| Reputation | Original adverse-event evidence; independent coverage; supplier response; later resolution; demonstrated stakeholder impact | Does credible, current evidence change the buyer's diligence priorities? |

These are product-design questions, not an exhaustive legal or railway qualification checklist. Financial statements describe different dimensions and periods: balance-sheet position, earnings and cash movement should be read together. [SEC guide to financial statements](https://www.sec.gov/about/reports-publications/beginners-guide-financial-statements). Labour checks include association, forced and child labour, discrimination and workplace safety, reflecting the ILO's fundamental-rights framework. [ILO fundamental principles and rights at work](https://www.ilo.org/topics-and-sectors/fundamental-principles-and-rights-work).

Official EU resources link sanctions regimes, legal acts and the consolidated financial-sanctions list. The list is one research input; the app must not claim legal clearance from a general web search or a similar-name match. [European Commission sanctions resources](https://finance.ec.europa.eu/eu-and-world/sanctions-restrictive-measures/overview-sanctions-and-related-resources_en). Governance indicators are country context: the World Bank cautions against over-interpreting small differences and changes, and does not combine its dimensions into a single governance score. They do not establish a supplier site's exposure. [World Bank WGI FAQ](https://www.worldbank.org/en/publication/worldwide-governance-indicators/frequently-asked-questions).

Cyber and supply-chain checks draw inspiration from provenance, resilience, foundational cyber practices and supply tiers. NIST SP 1326 is scoped to ICT suppliers; applying those themes to rail procurement here is an explicit product-design inference, not a claim of NIST rail certification. [NIST due diligence assessment quick-start guide](https://csrc.nist.gov/pubs/sp/1326/final).

## Investigation loop

1. **Resolve identity first.** Capture legal name, user-supplied domain/country, registration ID when available, parent/subsidiary relationship and relevant site/component. If the name is ambiguous, present candidate entities or mark identity provisional. Do not silently inherit parent-company findings or the saved Siemens fixture.
2. **Publish the plan.** Use all six category question sets. Include company aliases, relevant jurisdictions, proposed order context, lookback period and dated-source goals. A pragmatic initial lookback is 24 months plus the most recent available accounts and older unresolved matters; label this an app default, not a standard.
3. **Search and read.** Prefer official registries, filings, courts, regulators and original company disclosures for claims they own. Use original independent reporting for corroboration and discovery. Search results are leads: record whether the full source was read, only a snippet was available, or access failed. Company policy is evidence of a stated policy, not of implementation.
4. **Extract evidence before assessing.** Attach every finding to a source and exact scope. Record contradictory facts and later case status. An annual report's generic risk factor is a disclosed exposure, not a confirmed incident. A lawsuit allegation is not a final finding. A source repeating another outlet is not an additional independent origin.
5. **Follow red flags with a bounded branch.** State trigger, question, sources needed, budget and outcome. For example: a recall notice triggers a search for affected product/site, regulator status, corrective action and relevance to the proposed part. If unresolved, preserve the gap and add a diligence action; do not write “resolved” because a mitigation policy exists.
6. **Synthesize with an evidence check.** Confirm correct entity, dates, claim support and procurement relevance. Review adverse and reassuring evidence. Flag unsupported conclusions and contradictions. Stop with a partial report if budgets, access or model failures prevent completion.
7. **Keep the report conversational.** Follow-up questions use the current dossier, identify what they can answer from it, and state when new research is needed. A requested refresh creates a new dated version rather than silently overwriting history.

Suggested default budgets are product choices: basic mode targets one useful source per category, a small shared search budget and explicit gaps; deep mode allows more independent source origins, jurisdiction/site-specific checks and bounded red-flag follow-ups. Neither label guarantees comprehensive coverage. Show actual configured limits and actual completed work. Budget exhaustion, unavailable credentials and failed requests must remain visible.

## Evidence and assessment fields

An evidence record should preserve:

- Stable `evidenceId`, `reportId`, `categoryId`, claim text and procurement relevance.
- Entity/site/product scope; whether parent-level facts are being used only as context.
- Source URL, title, publisher, source class and page/section locator or short supporting excerpt.
- Publication date, event date, reporting period and access time as separate fields; unknown dates are null.
- Access status (`full_text`, `snippet_only`, `unavailable`) and the specific limitation.
- Evidence stance (`confirmed_event`, `allegation`, `disclosed_exposure`, `company_stated_control`, `context`, `evidence_gap`). “Confirmed” describes what the cited record establishes, not independent proof of every allegation it contains.
- Origin group for deduplicating syndicated reports, corroborating IDs, contradictory IDs and latest known status.
- Analyst assessment separated from source facts; concise rationale and follow-up action.

Assess each category along three separate dimensions. **Concern** describes evidence of a relevant adverse exposure; **coverage** describes how much of the planned work was completed; **confidence** describes support for the specific conclusion. Suggested concern values are `attention_required`, `watch`, `no_material_finding_in_review`, `unknown`; coverage values are `not_started`, `partial`, `reviewed`; confidence values are `low`, `medium`, `high` with a stated basis. These are app judgments, not calibrated probabilities or inherited CSV levels.

`no_material_finding_in_review` always means no material finding in the disclosed sources and time scope. It is never “safe” or “zero risk.” A single strong regulator decision may establish an event with high confidence while the category remains only partially researched. Missing sources can produce high-priority diligence actions without pretending to establish adverse facts.

## Risk report template

1. **Identity, scope and timestamp:** contracting entity, identity match status, site/part/system, jurisdictions, period, user question, mode and research budget used.
2. **Executive assessment:** what the evidence supports; material concerns; prerequisites to a sourcing decision; explicit partial/complete research status. Supplier qualification remains a separate buyer process.
3. **Six category sections:** concern, coverage, confidence; dated findings; source/evidence IDs; contradictions; implications; unknowns; next actions. Include a section even when no useful evidence was found.
4. **Priority actions:** question to resolve, reason/trigger, evidence needed, priority rationale, proposed owner and review status. Distinguish urgent review from a proven adverse finding.
5. **Source register:** URLs, titles, publication/access dates, source class, access quality and source-to-claim links.
6. **Research log and limits:** searches attempted, successful retrievals, failed retrievals, follow-up branches, unsearched scopes, costs/budget if available and version. Plain-language report conclusions should be understandable without replaying the chat.

The source-of-truth dossier should be machine-readable JSON. HTML and Markdown reports render the same snapshot, enabling export and later comparison without reparsing prose.

## Formalizing “add to list”

Support both meanings of the user's request:

**Saved research suppliers.** Save a separate research-derived supplier record with an ID such as `RESEARCH_<uuid>`, resolved identity, selected train system, provenance `public_research`, report ID/version, saved timestamp and six nullable numeric scores. Preserve evidence links and the original report snapshot. Deduplicate by reliable registration ID/jurisdiction when available; otherwise use an explicit normalized-name/domain candidate match requiring inspection. Do not merge distinct subsidiaries just because they share a domain. Saving a dossier does not qualify the supplier or claim a mapping to any anonymized `SUPP_*` ID.

**Actionable diligence queue.** Save each important unresolved question as an action with ID, report/supplier/category/evidence references, trigger, required evidence, priority rationale, owner, optional due date, status (`open`, `in_progress`, `blocked`, `done`) and resolution evidence. Suggested actions remain editable. Completing an action requires a resolution note/evidence; it does not automatically reduce a score. The report preserves its original unknowns until refreshed.

A useful future object is `ResearchDossier { id, version, entity, scope, plan, events, sources, evidence, categories, actions, limitations, numericScores }`; `numericScores` initially contains null for all six categories and overall risk. Store the synthetic catalog and research-derived records separately. A saved record can appear alongside the catalog with a visible provenance badge and “unscored,” while remaining excluded from numeric averages/rankings. Exporting a saved-list CSV should include identity, provenance, report date/link and blank numeric fields; JSON export preserves the evidence graph.

## What existing scores can and cannot contribute

Use the CSV and descriptions as vocabulary and workflow inspiration. The exact existing source columns corresponding to each category are in the taxonomy config. These mappings are semantic groupings, not a rule for assigning research scores. The criteria define all supplied score fields as 0 = no risk and 100 = maximum risk, even positively named `Financial_Health_Score` and `Credit_Rating_Score`. Delivery/confirmation percentages are performance measures and must not be inverted or converted without a separate rule. [Local criteria](../risk_criteria_description.md).

Original scoring weights, raw observations, observation dates, calibration and outcomes are absent. The user confirms these numbers are fake. Correlations or apparent cutoffs in synthetic scores may describe the fixture; they cannot establish real-world risk severity, causality, a supplier's country, or an independently validated model. Preserve `Total_Risk_Index` as supplied and never claim the six categories explain its unknown formula. Broad `ESG_Performance_Score`, `External_Intelligence_Score` and `Industry_Benchmark_Score` may be shown as original fixture context but are not independently measured research facts.

If numeric ratings become necessary, first define measurable indicators and units, evidence recency/quality rules, explicit unknown handling, component/site exposure, proposed severity and likelihood rubrics, reviewer policy and versioned aggregation. Then collect labelled real outcomes or expert assessments and validate reliability before claiming predictive calibration. Until then, structured evidence, concern labels, transparent coverage and diligence actions meet the risk-report goal without manufacturing precision.

## Review checklist

- A company name never receives another company's saved findings.
- Every category appears and unsupported findings remain gaps.
- Every material report claim resolves to a retrieved source or a clearly labelled access limitation.
- Source publication, event, financial period and access dates remain distinct.
- Red-flag branches show what triggered them and what remains unresolved.
- Saved records retain report provenance and null numeric scores.
- Queue actions retain evidence requirements and remain separate from supplier qualification.
- CSV catalog bytes and original score values remain unchanged.

This note records the intended methodology. The application's README and visible mode/coverage labels must state which of these capabilities the shipped basic implementation actually executes; a contract is not evidence that a live run completed every step.
