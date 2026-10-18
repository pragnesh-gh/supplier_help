# Buyers, existing tools, and a defensible supplier-selection workflow

Research date: 2026-10-18. Scope: Siemens Mobility challenge, with Siemens-wide evidence explicitly distinguished from Mobility evidence. Primary sources only; public evidence does not establish a team's actual internal configuration.

## Findings that should drive the prototype

**Build for procurement professionals making an explainable shortlist, with engineering, quality, finance and project stakeholders reviewing the result. Do not invent an age profile.** A quiet, information-dense interface is a product recommendation based on the work, not an inference that railway buyers are old.

The strongest Siemens-wide source explicitly identifies Buyers, Commodity Managers, Project Procurement Managers, Controllers and Purchasing Councils as consumers of procurement information. It identifies SCM STAR for supplier management, sourcing and contracts and SCM CoRe for procurement reporting. The document is version 1.3, July 2024, not a current inventory of every Mobility installation. [Siemens Sustainable Procurement, pp. 6–7](https://static.sw.cdn.siemens.com/siemens-disw-assets/public/5rxr5cj9Eqa104a1vsli5B/en-US/siemens-sustainable-procurement.pdf)

**Evidence confidence:** high for the named roles and published applications; medium for applying the Siemens-wide workflow to a particular Mobility buying team; unknown for demographic distribution.

## Demographics: what we know and what we do not

No credible primary-source distribution of age, gender, or digital proficiency for Siemens Mobility buyers was found in this research. This is an evidence gap, not evidence that the population is young or old. Broad railway workforce statistics mix drivers, maintenance, infrastructure, operations and many other jobs; they cannot answer the buyer-specific question.

Official Mobility postings demonstrate varied responsibility and experience levels. A production-order planner posting requires at least three years of relevant experience and describes supplier follow-up and cross-functional purchasing. A senior materials leadership posting requires at least ten years. Neither establishes employees' ages or the composition of procurement teams. [Siemens Mobility production-order planner, job 480508](https://jobs.siemens.com/en_US/externaljobs/JobDetail/480508), [Siemens Mobility materials leadership, job 499613](https://jobs.siemens.com/de_DE/externaljobs/JobDetail/499613)

**Design implication — recommendation:** support both a frequent spreadsheet user and an occasional reviewer. Offer visible labels, keyboard navigation, clear focus, comfortable text, restrained motion and color-independent risk labels. These are useful accessibility choices without an age stereotype. W3C finds that existing accessibility standards cover most older users' needs as well. [W3C older users and accessibility](https://www.w3.org/WAI/older-users/)

**Validation needed:** interview one buyer/commodity manager, one project procurement manager, and one quality or engineering reviewer. Ask them to bring a redacted recent sourcing comparison. Observe the actual comparison, approval, export and follow-up work; ask about age only if it serves a legitimate research need. Validate preferred languages and whether speaking company names in an office is acceptable.

## Existing software: evidence and integration priority

| Application | What the primary evidence actually establishes | Confidence and product implication |
| --- | --- | --- |
| SCM STAR / SCM CoRe | Siemens describes its sourcing/supplier/contract cockpit and centralized procurement reporting. The brochure names supplier identifiers, commodity codes and purchasing volume. | High at Siemens-wide level; prioritize a future structured import/export adapter and source-record link. Actual APIs/access remain unknown. |
| JAGGAER | The live Siemens supplier portal's SCM STAR login points to an `app.jaggaer.com` host. | High for that observed login relationship only. Do not assume every JAGGAER API or module is licensed. |
| SAP and Excel | Mobility's production-order planner explicitly requires Excel and SAP experience. A Mobility demand-planner posting names SAP MRP and advanced Excel analysis. | High for those roles, not a company-wide usage percentage. CSV export is an appropriate first bridge; SAP integration is later work. |
| Keelvar / SCM CART | Siemens' public supplier portal lists them among additional eSourcing applications. | High that Siemens names them; unknown for the target team. Keep as possible later integrations. |
| Teamcenter | The same portal says some Siemens business units use Teamcenter PLM. | High with that qualification. Do not claim every buyer uses it. Engineering/BOM context is a possible later connection. |
| SAP Ariba | SAP documents an S/4HANA-to-Ariba sourcing workflow, including requests for quotation and bid awards. This establishes product capability, not target-team adoption. | Do not present “Connected to Ariba” or prioritize it ahead of verified Siemens tools without user evidence. |
| Teams, Outlook, Power BI, SharePoint | Not established here as the target buyers' actual collaboration stack. | Generic document/CSV download first; named connectors require confirmation. |

Sources: [Siemens supplier cockpit](https://www.siemens.com/de-de/company/about/supply-chain-management/supplier-cockpit/); [Siemens procurement brochure, p. 6](https://static.sw.cdn.siemens.com/siemens-disw-assets/public/5rxr5cj9Eqa104a1vsli5B/en-US/siemens-sustainable-procurement.pdf); [Mobility planner job 480508](https://jobs.siemens.com/en_US/externaljobs/JobDetail/480508); [Mobility demand planner job 513483](https://jobs.siemens.com/zh_TW/externaljobs/JobDetail/513483); [SAP official integration documentation](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/754a46a305c642559f21625ca2744170/705e158a91894e758565840b0e0100d8.html).

## Workflow boundaries that matter

Siemens' published supplier process distinguishes preselection from registration and qualification: a supplier only receives Ready-for-Business status after completing those steps. Risk assessments can trigger corrective action and, ultimately, blocking or termination. A low score in the challenge file therefore cannot establish procurement eligibility. [Siemens Sustainable Procurement, pp. 7, 12](https://static.sw.cdn.siemens.com/siemens-disw-assets/public/5rxr5cj9Eqa104a1vsli5B/en-US/siemens-sustainable-procurement.pdf)

For rail cybersecurity specifically, Siemens Mobility distinguishes low, medium and high supplier criticality, with increasing requirements from declarations to questionnaires to evidence. It also describes contractual controls and validation. This is a useful reason to add an evidence/checks section later, but **cybersecurity criticality must not be relabeled as the CSV's general Total Risk Index**. [Siemens Mobility cybersecurity supplier assessment](https://www.mobility.siemens.com/global/en/portfolio/digital-solutions-software/cybersecurity/certification-standards.html)

Mobility's supply-chain planner responsibilities include purchase requisitions/orders, delivery confirmation, shortage mitigation, engineering drawings, and coordination with strategic procurement and project management. This demonstrates how a risk shortlist can feed a wider operational process. [Siemens Mobility supply-chain planner, job 477517](https://jobs.siemens.com/es_ES/externaljobs/JobDetail/477517)

**Scope recommendation:** the prototype ends at a documented sourcing recommendation, with next actions and export. It should not imply that it awards a contract, qualifies a supplier, creates a purchase order, or synchronizes an ERP.

## Dataset constraints verified locally

Inspected `docs/risk_criteria_description.md` and the CSV header/sample supplied in the repository.

- The dictionary says every risk score runs from 0 (no risk) to 100 (maximum risk). “Financial Health” and “Credit Rating” are therefore risk-oriented despite their reassuring names. Display an explicit “Lower = lower risk” legend.
- Operational percentage fields are separately described; do not silently turn delivery rating into a risk score or invert the source data.
- The dictionary calls Total Risk Index a weighted average but supplies no weights. Explanations may identify high category values; they cannot truthfully attribute a precise percentage of total risk to each category.
- The file has anonymized supplier IDs/names and risk/operational metrics. Its header does not provide verified real legal entities, geography, actual supplied components, certification status, Ready-for-Business status, or technical suitability.
- A project brief such as “door-system sourcing” may be editable scenario context. It cannot be a factual filter over component capability until matching data is added.
- External real-company research must be a separate record. Do not attach a public company's red flags to a fictional-looking dataset supplier merely because names look similar.
- Neither source freshness nor longitudinal history can be inferred from one CSV snapshot. Avoid invented “up 12% this month” deltas.

## Recommended click-through journey (design proposal, not Siemens policy)

1. **Set decision context.** Enter a sourcing purpose and review date. Show the loaded dataset, row count and metric definitions. Label project context as user-entered.
2. **Explore candidates.** Search IDs/names; filter only supported fields; choose an explicit ranking criterion. Show source risk labels, raw numbers, exposure and delivery metrics. Persist selected suppliers across filters.
3. **Compare up to 20.** Provide a risk heatmap with values and labels, pinned supplier identities and category rows. Add a simple ranked bar view for the currently selected criterion. Let users focus on 3–5 without silently removing the rest. Do not make a 20-series radar chart the core comparison.
4. **Ask a grounded question.** Example: “Which of these has the lowest financial risk?” Display selected IDs, metric, values and a view-data action. A second answer can show highest category risks with the limitation that source weights are unavailable.
5. **Investigate a real company.** A separate research page asks for legal name and website/country to resolve identity, previews a research plan and presents dated findings with direct sources and uncertainty. In the prototype, use a clearly marked prerecorded research example.
6. **Record a recommendation.** Choose preferred and alternate suppliers, capture a trade-off, note unknowns, and add a next action such as “Request evidence of qualification.” Scores support the human decision.
7. **Export a shortlist memo.** Include IDs, selected metrics, data snapshot identity, ranking criterion, rationale, alternatives, limitations and external references. Demonstrate an actual download. A real integration/approval action belongs to a later phase.

**UI recommendation:** neutral light workspace; restrained teal/navy accent; amber/red reserved for risk and errors; visible “Explore / Compare / Research / Decision” navigation; a compact selection tray; descriptive buttons. Put a contextual assistant beside the data, with evidence expandable in place. Avoid a chat-only landing page that hides the dataset.

**Speech recommendation:** an optional microphone beside the same question composer. Use push-to-talk, visible recording state, editable transcript, cancel and explicit Send. The prototype can simulate a transcript deterministically with a “Demo dictation” label; it must not claim live transcription. Keep typed input equally capable and answers textual. This is a proposed interaction, not evidence that the demographic wants voice.

## Useful additions, ranked

**Prototype now:** persistent shortlist, evidence-linked answers, explainable rank selection, missing-data labels, compare-limit feedback, deterministic demo/reset, memo export.

**Next real implementation:** validated CSV ingestion, server-side deterministic queries, query-plan validation, model-generated prose tied to returned rows, source-cited company research, decision provenance, saved workspaces.

**Later, after user validation:** read-only SCM/SAP imports, component/BOM context, qualification gates, supplier evidence requests, monitored risk changes, multilingual dictation and review collaboration. Do not advertise live integrations in the prototype.

**Research limitations:** public postings describe selected locations/roles, not representative workforce samples. The main procurement brochure is from July 2024. Public documents establish published processes, not the exact challenge team's current implementation. No target-team interviews, internal system access or buyer demographic dataset was available.

