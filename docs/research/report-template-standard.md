# Report template: one recognised standard as the backbone

Researched 2026-10-18. This replaces our own mix of vendor layouts in [report-template.md](report-template.md), which stays unchanged for reference. The goal is a report with the same sections in the same order every time, following a template that German procurement and compliance teams already know.

## 1. Candidates

| Template | Publisher, language | Public section list? | Used in Germany? | Fit with our data |
|---|---|---|---|---|
| **"Risiken ermitteln, gewichten und priorisieren"**, the LkSG risk-analysis guide ([PDF](https://www.bafa.de/SharedDocs/Downloads/DE/Lieferketten/handreichung_risikoanalyse.pdf?__blob=publicationFile&v=4)) | BAFA (the federal authority that enforces the LkSG), German, 2022 | Yes. Table of contents on p. 2, step tables on pp. 12–17, criteria on p. 19 | Yes. Every company in LkSG scope must run this analysis, and BAFA enforces it ([PDF](https://www.bafa.de/SharedDocs/Downloads/DE/Lieferketten/handreichung_risikoanalyse.pdf?__blob=publicationFile&v=4) p. 5). Siemens describes the same two stages: country and industry indicators first, then self-assessments and audits ([Siemens](https://www.siemens.com/en-us/company/sustainability/sustainable-supply-chain/detection-module)) | Good. The steps and outputs fit any risk area. Its legal scope is human rights and the environment only |
| **Creditreform Wirtschaftsauskunft** ([product sheet](https://creditreform.de/fileadmin/user_upload/central_files/docs/produkte/produktblaetter/2024-08-01_PB_OE_DE_3017_Wirtschaftsauskunft_vfin.pdf), [annotated sample](https://creditreform.de/fileadmin/user_upload/central_files/docs/produkte/produktblaetter/2024-08-06_PB_OE_DE_Wirtschaftsauskunft_Muster_vfin.pdf)) | Creditreform, German | Yes. Firmenidentifikation, Bonität, Strukturdaten, Beteiligungsverhältnisse, Geschäftstätigkeit, Geschäftszahlen, Zusatzinformationen, Zahlungsinformationen | Yes. It is a standard German credit report and is marketed for "Beobachtung der wirtschaftlichen Entwicklung von Kunden und Lieferanten" (monitoring the business health of customers and suppliers) | Weak. It covers finance only, and it needs payment data and a credit limit that we do not have |
| **EcoVadis scorecard** ([methodology](https://ecovadis.com/wp-content/uploads/2026/04/EcoVadis-Sustainability-Rating-Methodology-disclosure-document-for-the-public-rating-users-and-rated-items.pdf)) | EcoVadis (France), English | Only partly. The layout is described by third parties: overall score, four theme scores, strengths and areas to improve, benchmark ([Greenly](https://help.greenly.earth/en/articles/13160616-scoring-methodology-of-ecovadis)) | Yes, in rail. Railsponsible (founders include Deutsche Bahn and Knorr-Bremse) uses EcoVadis as its standard supplier tool ([EcoVadis](https://resources.ecovadis.com/blog/ecovadis-railsponsible-initiative-sustainability-supply-chain)) | Medium. It covers ESG only, and its benchmark against peers breaks our rule against ranking |
| **D&B Business Information Report** ([sample](https://www.dnb.com/content/dam/english/dnb-solutions/DNB_2019_BIR-Snapshot-Report.pdf)) | Dun & Bradstreet (US), English | Snapshot only | Yes, through D&B Deutschland ([D&B DE](https://www.dnb.com/de-de/loesungen/risiko/lieferantenrisiko.html)) | Weak. It is credit-led |
| **ISO 31000 §6.7, recording and reporting** ([summary](https://wolterskluwer.com/en/expert-insights/iso-31000-blog-series-recording-and-reporting)) | ISO | No. It is guidance with no fixed sections | Widely cited | It gives no fixed order |

## 2. Recommendation: the BAFA guide

**Why this one:**
- **Recognised.** It comes from the German regulator itself, and every LkSG compliance team in Germany works with it, including Siemens's supplier team.
- **Public and stable.** The whole structure is in one free official PDF, so anyone can check the report against it.
- **Fits our data.** It asks for an abstract step (country and sector) and then a concrete step (company-specific findings) (p. 12). Those two steps match our Country & Location score and our dated red flags.
- **Asks for what we already value.** The weighting must be "transparent, nachvollziehbar und nach einer konsistent angewandten Systematik" (transparent, traceable and following a consistently applied system) (p. 12). Scores and traffic lights are allowed as tools ([Cubemos, secondary](https://cubemos.com/en/blog/lksg-risikoanalyse)).
- **Still current.** A draft amendment drops the annual BAFA report. The risk-analysis duty itself stays ([Bundestag Drucksache 21/2474](https://dserver.bundestag.de/btd/21/024/2102474.pdf), [IHK Nord Westfalen](https://www.ihk.de/nordwestfalen/international/lieferketten/aktuelles-zum-lksg-6724308)).

**Caveat:** the LkSG covers human rights and environmental risks only. We use BAFA's structure (steps, criteria and outputs) for all six of our areas. We do not claim that the report is an LkSG risk analysis. The footer should say so.

**What changes compared with our current layout:**

| Change | BAFA basis |
|---|---|
| A supplier profile block with fixed fields | §4.1, p. 11 |
| Country and sector risk ("abstract") is split from company-specific findings ("concrete") | Steps 1 and 2, p. 12 |
| Each red flag is rated for likelihood and severity separately, and a heatmap is added. The radar stays | p. 12: "einzeln zu bewerten … Skala bzw. Heatmap" (to be rated separately … on a scale or heatmap) |
| The top-3 lists become one risk inventory table: description, owner, weighting, measures | p. 12: Risikoinventar minimum fields |
| New fields for influence and contribution. These are buyer-side, so they show "Not assessed" | §3(2) LkSG criteria, pp. 12 and 19 |
| "Next steps" becomes "From priority risks to prevention" | §4.3, p. 18 |
| Strengths are no longer a separate list. They appear as "checked, nothing adverse found" rows | BAFA has no strengths section |

## 3. Fixed section list (always this order)

| # | Section | Our data | When we have no data |
|---|---|---|---|
| 0 | Header: company, legal entity, country, website, research date, sources checked | Identity fields | Each field missing → "Not found" |
| 1 | Summary for decision makers (results go to "maßgebliche Entscheidungsträger", the relevant decision makers ([Heuking](https://www.heuking.de/de/news-events/newsletter-fachbeitraege/artikel/die-risikoanalyse-nach-dem-lieferkettensorgfaltspflichtengesetz-die-erste-handreichung-des-bafa.html))) | TL;DR, total 0–100 with band, coverage, best/worst range | Coverage < 50% → "No total: too little assessed" |
| 2 | Supplier profile (Vorbereitung, §4.1: name, parent company, product or service, sites, employees, employee representation, order volume) | Researched facts with citations | Order volume → "Buyer input, not assessed" |
| 3 | Abstract risk: country and sector (Schritt 1) | Country & Location score with WGI and INFORM inputs. Sector context | Sector without a source → "Not assessed" |
| 4 | Concrete risks found (Schritt 2): dated findings per area, in fixed area order (Operations & Delivery, Financial, People & Safety, Legal & Governance, Country & Location, Reputation & Outside View), plus an event timeline | Red and amber flags with date, source and quote. Clean areas show "checked, nothing adverse found" | Area with no verified fact → "Not assessed" (never 0) |
| 5 | Weighting and prioritisation (Gewichtung und Priorisierung): six area scores with bands, radar, likelihood × severity heatmap | Area scores; radar with hollow axes for "Not assessed"; heatmap per decision 1 | Influence and contribution → "Buyer input, not assessed" |
| 6 | Risk inventory (Risikoinventar): description, owner, weighting, measures | Flag text, area score, suggested measures | Owner → "Assigned by buyer" |
| 7 | From priority risks to prevention (§4.3) | Three suggested next steps, each tied to a flag | – |
| 8 | Documentation: method, limits, sources with trust labels, dates and quotes, per-fact score breakdown | Facts-to-scores method; source list | – |

Rules for every section:
- No peer ranking. Real companies are never compared with the synthetic dataset.
- "Not assessed" is never shown as 0.
- Every claim carries a citation.
- The report never invents values.

## 4. Decisions for the user

1. **Likelihood and severity per flag.** BAFA wants both rated separately (p. 12). Severity has three sub-criteria: degree, number affected, irreversibility (p. 19). We have neither yet. *Option A:* severity comes from the flag colour (red/amber), and likelihood comes from evidence status (verified, "probably", "realistic possibility"). *Option B:* leave the heatmap "Not assessed" and keep only the radar.
2. **Labels:** English only, or English with the German BAFA terms in brackets?
3. **Strengths:** fold them into section 4, or keep them as a separate list?

## 5. Heatmap rule

Decided 2026-10-18 (option A in decision 1). Code places every red flag and watch item in a likelihood × severity grid. No model is asked. The table is in `research_agent/config/report.yaml` (`heatmap`), and the report prints the same table in section 8. Rules are read top to bottom; the first that fits applies.

| Severity: when the fact is … | Result |
|---|---|
| a red flag | High |
| a watch item the verifier rated low severity | Low |
| any other watch item | Medium |

| Likelihood: when the fact is … | Result |
|---|---|
| found only on sites not in our trusted source list (🟨) | Unconfirmed |
| an alleged or unclear claim | Possible |
| confirmed by at least two independent sources, one of them trusted | Likely |
| stated by the authority or the company itself (trusted source) | Likely |
| any other case (one trusted source) | Possible |

Each cell has a priority (1 = top priority … 4 = low priority). The risk register lists risks in priority order, and each heatmap cell links to its risks in the register. Influence on the supplier and our own contribution to the risk are buyer inputs: they show "Buyer input, not assessed".
