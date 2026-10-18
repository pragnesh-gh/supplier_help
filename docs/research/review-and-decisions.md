# Research review and prototype brief

Reviewed 2026-10-18. Research was split between a buyer/workflow agent and a model/speech/agent researcher, then reviewed by the parent before implementation.

## Checks and resulting decisions

- Reopened Siemens' live supplier cockpit: it explicitly lists SCM STAR, Keelvar, SCM CART and Teamcenter in some divisions. Accept these as Siemens-wide evidence, not proof of the target team's licences or API access. [Source](https://www.siemens.com/de-de/company/about/supply-chain-management/supplier-cockpit/)
- Opened the July 2024 Siemens procurement brochure. Preserve its version/date; use its roles and processes as background, not a current internal system inventory. [Source](https://static.sw.cdn.siemens.com/siemens-disw-assets/public/5rxr5cj9Eqa104a1vsli5B/en-US/siemens-sustainable-procurement.pdf)
- The parent could not reopen one Mobility job URL (browser tool internal error). Its researcher evidence remains scoped to a specific posting; it does not establish workforce-wide SAP/Excel adoption. No quantitative demographic claim is accepted.
- Reopened TypeSafe's documentation: Jev is a typed decision service. An optional evidence-triage adapter is a sensible later experiment; it is not a UI library or speech recognizer. [Source](https://docs.typesafe.ai/introduction)
- Reopened official OpenAI Decisions documentation: the endpoint is real, currently described as public beta. Treat it as an optional alternative to Jev, not another mandatory service. Vendor speed claims are not application benchmarks. [Source](https://developers.openai.com/api/docs/guides/decisions)
- Reopened the proposed OpenRouter model page and reviewed the researcher's public catalog response. Configure `nvidia/nemotron-3.5-lightning` provisionally; “Nemo run” still requires user confirmation. No credentialed inference or provider entitlement has been verified. [Source](https://openrouter.ai/nvidia/nemotron-3.5-lightning)
- Independently parsed all 10,000 CSV rows: 46 columns, unique supplier IDs, no empty cells, all 19 numeric risk indices/scores in range. Preserve the original CSV byte-for-byte. `data-audit.json` records the hash and examples.

## What this prototype should answer

Can a buyer move from 10,000 risk records to a defensible, reviewable shortlist without losing the evidence or confusing risk with qualification? Which workspace layout best supports that journey?

Three materially different layouts on one self-contained HTML route: A workbench (data with contextual assistant), B guided decision flow (one stage at a time), C comparison-first review (risk matrix and compact controls). Share state and underlying data, not an identical layout with recolored cards. Switch through `?variant=A/B/C` and a floating bottom control. No existing application route exists.

The primary demo is a resettable buyer journey; free exploration remains possible. Real data powers search, filtering, ranking, max-20 selection, comparisons and exact numeric answers. All model/research/speech steps are explicitly simulated. A user-entered component brief must not pretend the dataset establishes component capability. No supplier awards or real-system writes.

Required journey: context → candidate exploration → comparison → grounded questions → separate real-company research → buyer recommendation → actual downloadable memo/CSV. The research example must not fabricate misconduct or map real companies to anonymized suppliers. Prefer a neutral sourced corporate identity example plus clearly hypothetical follow-up states.

Qualification, source freshness, component suitability and total-risk weights stay unknown. Show data evidence, lower-is-lower risk direction, source-level labels, and the differences between risk scores and operational percentages. Explain high observed categories without inventing causal contributions.

## Scope and verdict

Research is sufficient to prototype this direction. User/buyer validation remains pending; no design winner or production readiness is claimed. Keep the throwaway HTML on `prototype/supplier-workbench`; `main` retains setup and research. Production implementation should be designed after the user selects a layout and reviews the workflow.
