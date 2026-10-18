# Report template: what established supplier-risk reports do, and what we adopt

Researched 2026-10-18. Most vendor samples sit behind a login. The RepRisk and Creditsafe PDFs were read directly. For D&B only the table of contents of the SER guide was seen. The other vendors are described from their own help pages.

| Report | Headline | Per-category | Events / trend | Sources |
|---|---|---|---|---|
| D&B BIR / SER ([sample](https://www.dnb.com/content/dam/english/dnb-solutions/DNB_2019_BIR-Snapshot-Report.pdf), [SER guide](https://docs.dnb.com/static/doc-uploads/supplier/en-US/support/Understanding%20US%20SER%20Rating%2020170330.pdf)) | Page-1 risk block: SER 1–9, credit recommendation, "D&B Thinks" commentary | Several scores side by side | Payment trends, filings | Appendix on data depth and elements |
| Creditsafe ([guide PDF](https://www.creditsafe.com/content/dam/fr/documents/guide-rapport-EN.pdf), pp. 5–6) | Page 1: score, A–E band, credit limit, days beyond terms | Tabs: accounts, judgements, group, directors | Score history, event history | Commentary tagged green / orange / red |
| RapidRatings FHR ([overview](https://intercom.help/rapidratings-helpcenter/en/articles/12550264-fhr-report-overview)) | FHR 0–100, Core Health Score, estimated default probability | Strengths and weaknesses against peers | Historical trend | Financial statements and ratios |
| RepRisk ([sample PDF](https://reprisk.com/media/pages/static/471962852-1721050840/reprisk-company-report-product-sample.pdf)) | Index 0–100 (0–24 low, 25–49 medium, 50–59 high, 60–74 very high, 75–100 extremely high); peak and 30-day change | E / S / G split, heat maps, spider chart of UN Global Compact principles | 2-year trend | Every incident dated and sourced; company self-reports excluded |
| EcoVadis ([methodology 2026](https://ecovadis.com/wp-content/uploads/2026/04/EcoVadis-Sustainability-Rating-Methodology-disclosure-document-for-the-public-rating-users-and-rated-items.pdf)) | Overall 0–100 and medal | 4 weighted theme scores | History | Strengths and improvement areas tied to evidence |
| Prewave ([scoring](https://help.prewave.com/en/articles/237277-how-is-the-prewave-score-generated), [glossary](https://help.prewave.com/en/articles/323732-glossary)) | 360° score from weighted components | Category scores built from event-type scores | Alerts over 24 months, weighted by severity | Each alert links to its article |
| Interos i-Score ([launch](https://www.helpnetsecurity.com/2022/10/07/interos-i-score/), [brief](https://www.interos.ai/wp-content/uploads/2022/12/Interos-for-Procurement-Sept-2022.pdf)) | One 0–100 score | Financial, restrictions, operational, geopolitical, ESG, cyber | Continuous | Not public |
| riskmethods / Sphera ([Supplier 360](https://sphera.com/company/news/sphera-launches-supplier-360-intelligence), [Impact Analyzer](https://sphera.com/impact-analyzer/?lang=de)) | Weighted score plus AI summary | Up to 400 indicators; heat map against criticality | Daily alerts | Not public |
| Moody's / BvD ([Maxsight check](https://help.maxsight.com/en/operational-risk-check), [brochure](https://www.moodys.com/web/en/us/site-assets/brochure-supplier-risk-management.pdf)) | Inputs listed first, then the summary score | 7 risk types | Change in implied rating | Inputs listed |
| S&P issuer reports ([guide](https://insight.spglobal.com/story/credit-reports-guide/page/2)) | Rating and outlook first | "Ratings score snapshot" | Upside and downside scenarios | Strengths, risks, rationale |
| Third-party due diligence ([Red Flag Group](https://legalbusinessonline.com/top-benefits-good-due-diligence-report-brought-you-red-flag-group), [KPMG Astrus](https://assets.kpmg.com/content/dam/kpmg/pdf/2013/09/kpmg-astrus-insights.pdf), [LexisNexis](https://www.lexisnexis.ca/pdf/products/diligence_brochure_canada.pdf)) | Executive summary with a red/amber/green rating | Integrity, sanctions, litigation, adverse media, financial | Red-flag table with severity | Audit trail of sources and dates |
| ISO 31000 §6.7 ([Wolters Kluwer](https://wolterskluwer.com/en/expert-insights/iso-31000-blog-series-recording-and-reporting)) / COSO Principle 20 ([summary](https://op.mahidol.ac.th/rm/wp-content/uploads/2019/01/Info-COSO-Enterprise-Risk-Management-2017-Jan-2019.pdf)) | Guidance only: record the process, report per decision level | – | – | Records support the audit trail |

**Common order:** identity → headline score with band and verdict → category scores → dated events → evidence and sources → method and legend.

## What we adopt and why

- **Page 1 = verdict + score + categories** (D&B, Creditsafe, RepRisk, S&P): a buyer can decide from page 1 alone.
- **0–100 scale, higher = more risk, four bands** (RepRisk and the challenge dataset).
- **Spider (radar) chart** (RepRisk). It also matches the radar in the team app.
- **Colour-tagged commentary that also carries a word**, never colour alone (Creditsafe, due-diligence reports).
- **Dated event list and timeline** (RepRisk, Prewave).
- **Audit trail with dates** (due diligence).
- **Method and legend last** (ISO 31000, D&B appendices).

## What we leave out

- **Peer percentiles.** Real companies are never ranked against the synthetic dataset (see facts-to-scores appendix §A1).
- **Credit limits.** We have no payment data.
- **Score-history chart.** Each run is a single point in time.

## What we add

- **"Not assessed" is drawn as a gap, never as 0.**
- **Every [n] citation opens the exact quoted passage** in its source (NotebookLM-style).

## Final layout

**Page 1:**
- Header: company, legal entity, country, website, research date, sources checked (trusted / 🟨).
- Verdict banner and summary.
- Total score with level, coverage bar, best/worst range and band legend.
- 6-axis radar. Axes that were not assessed are hollow.
- Top 3 red flags, top 3 watch items, top 3 strengths, each with date and citations.
- 3 next steps.

**Page 2:**
- Area table.
- Event timeline.
- What we dug into.
- How the scores work.
- Limits.
- Sources, with trust labels, dates and the quotes used.

Inline SVG only. A4 print. The same input always produces the same output.
