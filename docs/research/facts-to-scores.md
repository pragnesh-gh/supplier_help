# Facts → 0–100 risk scores: decision sheet

Proposal, 2026-10-18, not implemented. Detail, derivations and the source check are in the [appendix](facts-to-scores-appendix.md) (§A1–A7).

## Method in six lines

1. **Siemens's total is an exact weighted average.** `round_half_to_even(Σ wᵢ·scoreᵢ)` with round weights from 3% to 10% reproduces all 10,000 rows. The Level bands are 0–24 / 25–49 / 50–74 / 75–100 (§A1).
2. **Published scales where they exist:** default rates, Altman Z″, World Bank WGI, INFORM, EcoVadis (§A2).
3. **An event rubric everywhere else.** Each verified fact gets its colour from `rules.yaml`. The rules: "nothing adverse found" = 12, one fresh red event = 50, one fresh amber event = 25. Events combine by `100 − (100 − base)·Π(1 − p/100)` and fade so that at the staleness date a red counts as an amber (§A3).
4. **Unverified (non-allowlist) sources** are graded with the NATO "Admiralty Code". Anonymous claims and rumour score 0. Eligible facts count at 0.55 or 0.40, the lower bounds of the UK Defence Intelligence "probably" and "realistic possibility" ranges. They never cause a knock-out and move a score by at most one band (§A4).
5. **Missing areas are "Not assessed", never 0.** The total is renormalised over what was assessed, with coverage and best/worst range shown. No total below 50% coverage (§A5).
6. **Real-company scores are absolute** and are kept separate from the synthetic, relative dataset. They are never ranked against it (§A1).

## Score → method → source

| Score (weight) | Method | Source |
|---|---|---|
| Financial Health (10%) | Altman Z″ → rating equivalent → default-rate scale | [Altman](https://www.systemicrisk.ac.uk/sites/default/files/images/Evolution%20of%20Altman%20Z-Score.lse.pdf) |
| Credit Rating (6%) | Agency rating → S&P 3-year default rate → log scale | [S&P 2024 study, T26](https://maalot.co.il/Publications/FTS20250331162126.pdf), [EU 2016/1799](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R1799) |
| Political Stability (4%) | 100 − WGI score | [WGI 2025](https://data.worldbank.org/indicator/GOV_WGI_PV_SC) |
| Geopolitical (5%) / Environmental (4%) | 10 × INFORM human / natural hazard | [INFORM 2017](https://drmkc.jrc.ec.europa.eu/inform-index/Portals/0/InfoRM/INFORM%20Concept%20and%20Methodology%20Version%202017%20Pdf%20FINAL.pdf) |
| ESG (5%) | 100 − EcoVadis score; otherwise events | [EcoVadis 2026](https://ecovadis.com/wp-content/uploads/2026/06/EcoVadis-Sustainability-Rating-Methodology-disclosure-document-for-the-public-rating-users-and-rated-items.pdf) |
| Safety (6%) | Injury rate vs industry (BLS), plus events | [BLS SOII 2024](https://www.bls.gov/web/osh/table-1-industry-rates-national.htm) |
| Quality, Operational Resilience (10% each), Compliance (8%), Governance (5%), Labor, Digital (4% each), Media, Market (3% each) | Event rubric | [RepRisk](https://www.reprisk.com/media/pages/static/471962852-1721050840/reprisk-company-report-product-sample.pdf) structure; [JDP 2-00](https://assets.publishing.service.gov.uk/media/653a4b0780884d0013f71bb0/JDP_2_00_Ed_4_web.pdf) grading |
| Sub-Tier (6%), Industry Benchmark (4%), External Intelligence (3%) | Usually Not assessed (max coverage ≈ 87%) | – |

## Open decisions (3)

1. **Accept the three anchor rules** (nothing adverse = 12, fresh red = 50, fresh amber = 25). Almost every other rubric number is derived from these. *Recommendation:* accept, then check them once on 10 labelled companies (§A6). Only four calibration parameters remain open (§A3).
2. **Licensed data.** The terms of MSCI and Sustainalytics forbid commercial use of their ratings without a licence, and MSCI's free lookup is now client-only. *Recommendation:* use EcoVadis scorecards that suppliers share through Siemens's procurement process. Add MSCI, Sustainalytics or SecurityScorecard only if Siemens already licenses them.
3. **Country used for country scores.** *Recommendation:* the supplying sites if the buyer names them, otherwise the HQ country, labelled as such. This needs one extra optional input in the chatbot.

Everything else is a documented default in the appendix (for example: an unrated company's credit score is Not assessed; a knock-out keeps the computed total).
