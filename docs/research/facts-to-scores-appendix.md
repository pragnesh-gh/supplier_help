# Facts → scores: appendix

Supports [facts-to-scores.md](facts-to-scores.md). Every number below is one of:

- **[S]** taken from a cited source;
- **[D]** derived, with the arithmetic shown, from an anchor rule or a cited source;
- **[C]** a calibration parameter: a starting value plus a fitting rule (§A6).

✅ = checked in the primary document (most via Tavily extract on 2026-10-18; see §A7).

---

## A1. What the dataset says

Script: [`scripts/fit_total_risk_weights.py`](../../scripts/fit_total_risk_weights.py).

**The fit.**
- OLS on the 18 sub-scores: R² **0.9996** (the "0.996" quoted earlier is a typo). 5-fold CV R² 0.9996, MAE 0.25, intercept −0.017, coefficients sum to 1.0002.
- With the round weights below, `round_half_to_even(Σ w·s)` reproduces **100%** of rows (round-half-up gets 99.53%).
- The 6 operational columns add nothing once the scores are in. On their own they reach R² 0.67, because they come from the same latent risk. Delivery Rating correlates −0.71 with the total and −0.78 / −0.77 with Quality / Operational Resilience.

**Weights [S: exact fit].**

| Weight | Scores |
|---|---|
| 0.10 each | Financial_Health, Quality_Risk, Operational_Resilience |
| 0.08 | Compliance_Risk |
| 0.06 each | Credit_Rating, Safety_Incident, Sub_Tier_Visibility |
| 0.05 each | Geopolitical_Risk, Governance_Risk, ESG_Performance |
| 0.04 each | Environmental_Exposure, Labor_Stability, Digital_Security, Political_Stability, Industry_Benchmark |
| 0.03 each | Market_Sentiment, Media_Sentiment, External_Intelligence |

**Levels [S].** Every column uses Low 0–24, Medium 25–49, High 50–74, Critical 75–100, with no overlaps.

**Umbrellas [S].** Average-linkage clustering reproduces the team's six umbrellas exactly. Mean correlation within umbrellas is 0.68, between umbrellas 0.39. Country & Location is the loose one (0.52).

| Umbrella | Scores | Weight |
|---|---|---|
| Operations & Delivery | Operational Resilience, Quality, Sub-Tier, Digital | 0.30 |
| Financial | Financial Health, Credit | 0.16 |
| People & Safety | Labor, Safety, ESG | 0.15 |
| Legal & Governance | Compliance, Governance | 0.13 |
| Country & Location | Geopolitical, Political, Environmental | 0.13 |
| Reputation & Outside View | Media, Market, External Intelligence, Industry Benchmark | 0.13 |

**Calibration.** Each score in the dataset has mean ≈ 50 and SD ≈ 20 (≈ 16 for the country scores), and 48% of suppliers are "High". The dataset is synthetic and relative, while our scores are absolute. We reuse only its weights and bands. Real companies are never ranked or charted against `SUPP_*` suppliers (settled).

**Agent areas → umbrellas.** financial → Financial; legal → Legal & Governance; country → Country; people → People & Safety; operations → Operations; reputation → Reputation. Two fixes are needed:
- `leadership_scandal` feeds Governance.
- The dataset's Environmental_Exposure means geographic hazards (floods, earthquakes), not pollution.

New event types the agent would need: `safety_fatality`, `environmental_violation`, `data_breach`, `contract_penalty_or_cancellation`, `audit_or_accounting_issue`, `supply_chain_forced_labour_listing`, plus number fields (rating, accounts, fine amount, injury rate).

---

## A2. Index-based scores

**Credit_Rating.**
- **Default-rate table [S ✅].** S&P *2024 Annual Global Corporate Default and Rating Transition Study*, Table 26, 1981–2024 cumulative default rates ([PDF via S&P Maalot](https://maalot.co.il/Publications/FTS20250331162126.pdf); the spglobal.com page is paywalled).
- **Formula [D].** Score = 100·(log₁₀ PD₃ − log₁₀ 0.13) / (log₁₀ 100 − log₁₀ 0.13).
  - We use the **3-year** rate (PD₃) because that is the horizon of the EU regulator's rating-to-credit-quality-step benchmarks ([Reg. (EU) 2016/1799, Annex I](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R1799) ✅), and it equals the agent's default look-back.
  - 0.13% is the AAA rate, used as the floor (→ 0). Default (PD 100%) → 100.
  - The scale is logarithmic because default rates span three orders of magnitude.
  - A running maximum keeps the scale monotone (AA+ 0.04 is below AAA 0.13 in the table).
- **Result:**

  | Rating | AAA–AA | A+/A/A− | BBB+/BBB | BBB−/BB+/BB | BB−/B+/B/B− | CCC/C | D |
  |---|---|---|---|---|---|---|---|
  | Score | 0–2 | 3/6/8 | 17/21 | 33/37/46 | 54/62/65/72 | 87 | 100 |

  Investment grade down to BBB lands in Low, the BB range in Medium, the B range in High, and CCC and below in Critical.
- **Moody's and Fitch [S ✅].** They map to S&P by category ([EU 2016/1799 Annex III](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R1799): Aaa/Aa ≙ AAA/AA … Caa ≙ CCC). Moody's modifiers 1/2/3 ≙ +/flat/− ([Moody's Rating Symbols](https://ratings.moodys.com/api/rmc-documents/53954), via search).
- **Several ratings [S ✅].** Two different ratings → use the worse. Three or more → use the worse of the two best. This is the rule in [CRR Art. 138(e)–(f)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32013R0575).
- **Outlook.** Shown, not scored: we found no published rule for converting an outlook into notches.
- **Unrated companies.** Not assessed (default). Using the Z″-implied rating instead would count the same accounts twice.

**Financial_Health [S ✅].**
- Z″ = 3.25 + 6.56·(working capital/TA) + 3.26·(retained earnings/TA) + 6.72·(EBIT/TA) + 1.05·(book equity/total liabilities) ([Altman slides 25–26](https://www.systemicrisk.ac.uk/sites/default/files/images/Evolution%20of%20Altman%20Z-Score.lse.pdf)).
- Take the rating whose 2013 median Z″ is nearest. Medians: AAA/AA+ 8.80, AA/AA− 8.40, A+ 8.22, A 6.94, A− 6.12, BBB+ 5.80, BBB 5.75, BBB− 5.70, BB+ 5.65, BB 5.52, BB− 5.07, B+ 4.81, B 4.03, B− 3.74, CCC+ 2.84, CCC 2.57, CCC− 1.72, CC/D 0.05. On a tie, take the worse rating.
- Then score it with the Credit scale above.
- Insolvency filing → 100 [D: default = PD 100%]. Rubric events are then added (§A3).
- BBB+ to BB+ medians lie only 0.15 apart, so the report always shows Z″ next to the score.

**Political_Stability = 100 − WGI Political Stability score [S ✅].**
- The 2025 WGI revision maps each country linearly between a constructed best case (100) and worst case (0), with 90% confidence intervals ([methodology §3.3](https://www.worldbank.org/content/dam/sites/govindicators/doc/The%20Worldwide%20Governance%20Indicators%202025%20Methodology%20Revision.pdf); [data, CC BY 4.0](https://data.worldbank.org/indicator/GOV_WGI_PV_SC)).
- The CI is carried over as [100 − upper, 100 − lower].

**Geopolitical = 10 × INFORM Human Hazard; Environmental = 10 × INFORM Natural Hazard [S ✅].**
- INFORM gives "an overall risk score out of 10 for each country, and for each of the dimensions, categories and components". Risk = (Hazard & Exposure × Vulnerability × Lack of Coping Capacity)^⅓ ([INFORM Concept & Methodology 2017](https://drmkc.jrc.ec.europa.eu/inform-index/Portals/0/InfoRM/INFORM%20Concept%20and%20Methodology%20Version%202017%20Pdf%20FINAL.pdf), [methodology page](https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Risk/Methodology)).
- We use the hazard categories rather than full INFORM Risk, so natural hazards are not counted twice.
- Licence: the report says reuse "is authorised, provided the source is acknowledged". INFORM calls itself "open-source". ⚠️ No separate data licence was found, so attribute the data the same way.

**Not used: Transparency International CPI.** It is published under CC BY-ND ⚠️ ([TI](https://www.transparency.org/en/news/how-cpi-scores-are-calculated)), and "no derivatives" conflicts with rescaling it. If a country corruption input is wanted, WGI Control of Corruption (CC BY 4.0) is the alternative.

**ESG = 100 − EcoVadis score [S ✅].**
- EcoVadis scores 0–100 in bands: Insufficient 0–24, Partial 25–44, Good 45–64, Advanced 65–84, Outstanding 85–100.
- Medals are percentile-based (Platinum top 1%, Gold 5%, Silver 15%, Bronze 35%) ([EcoVadis methodology 2026](https://ecovadis.com/wp-content/uploads/2026/06/EcoVadis-Sustainability-Rating-Methodology-disclosure-document-for-the-public-rating-users-and-rated-items.pdf)). A medal without its score is therefore shown but not scored.
- Only if licensed:
  - **Sustainalytics** (Negligible < 10, Low 10–20, Medium 20–30, High 30–40, Severe ≥ 40 ✅ [FAQ](https://connect.sustainalytics.com/hubfs/SFS/Sustainalytics%20ESG%20Risk%20Rating%20-%20FAQs%20for%20Corporations.pdf)) [D]: 0–20 → 0–24; 20–30 → 25–49; 30–40 → 50–74; ≥ 40 → 75 + 2.5·(x − 40), capped at 100. The slope of 2.5 points per Sustainalytics point is the same as in the High band.
  - **MSCI** (Leader AAA/AA, Average A/BBB/BB, Laggard B/CCC ✅ [MSCI symbols](https://www.msci.com/downloads/web/msci-com/legal/sustainability-and-climate-resources-and-disclosures/msci-sustainability-and-climate-methodologies/msci-sustainability-and-climate-symbols-and-definitions.pdf)) [D, even split inside each group]: AAA 6, AA 18, A 29, BBB 38, BB 46, B 62, CCC 87.
- **Why licensed only [S ✅]:** Sustainalytics information is "intended for internal, non-commercial use only and may not be copied, distributed or used in any other way, including via citation" without written agreement ([legal disclaimers](https://www.sustainalytics.com/legal-disclaimers)). MSCI information "may not be used for commercial purposes without prior written permission" ([How to reference an MSCI ESG Rating, 2026](https://www.msci.com/documents/1296102/15233886/How-to-Reference-an-MSCI-ESG-Rating-Final.pdf)). MSCI's search tool is now offered to clients through MSCI ONE ([MSCI](https://www.msci.com/data-and-analytics/sustainability-solutions/esg-ratings-climate-search-tool)).
- ESG ratings from different providers correlate only 0.38–0.71 ([Berg, Kölbel & Rigobon, *Review of Finance* 2022](https://revfin.org/aggregate-confusion-the-divergence-of-esg-ratings) ✅). So we use one provider at a time, never an average.

**Safety: base = clamp(12 + 13·log₂ r, 0, 100)**, where r = company injury rate ÷ industry rate on the same metric.
- [D] r = 1 (industry average) is set equal to the rubric's "nothing adverse" level of 12.
- [C] r = 2 is set to count as one amber watch item (25). That gives the slope 25 − 12 = 13 per doubling.
- Benchmark [S ✅]: BLS 2024, NAICS 3365 railroad rolling stock, TRIR **2.4**, DART 1.7; all manufacturing TRIR 2.7. Rate = cases × 200,000 / hours ([BLS Table 1](https://www.bls.gov/web/osh/table-1-industry-rates-national.htm)).
- EU benchmark: Eurostat ESAW ([Eurostat](https://ec.europa.eu/eurostat/statistics-explained/index.php/Accidents_at_work_statistics)), but only where the metric definition matches. Otherwise use events only.

**Digital.**
- A SEC Form 8-K Item 1.05 filing (a material cybersecurity incident, disclosed within 4 business days, in force since 18 Dec 2023) is a red event that can never be graded "low" ([summary](https://huntonak.com/privacy-and-information-security-law/sec-adopts-final-public-company-cybersecurity-disclosure-rules) ⚠️).
- CVSS is used only to grade the supplier's own product vulnerabilities (Critical/High = not low) ([CVSS v4.0](https://www.first.org/cvss/v4-0/cvss-v40-specification.pdf), via search; FIRST: Base score "is not risk").
- SecurityScorecard: only if licensed ([methodology](https://securityscorecard.com/white-paper/securityscorecards-scoring-methodology)).

---

## A3. Event rubric

**Formula:** `score = 100 − (100 − B) · Π (1 − pₑ/100)`, where `pₑ = P_colour × D_age × S_source`, then clamped to 0–100.

The product form is order-independent and can never exceed 100. Each new event takes a share of the remaining headroom.

**Rules applied before the formula.**
- A score is produced only if its area has ≥ 1 verified fact; otherwise it is "Not assessed".
- **Positive facts are shown, not scored.** RepRisk's index likewise quantifies risk incidents only ✅ ([sample report](https://reprisk.com/media/pages/static/471962852-1721050840/reprisk-company-report-product-sample.pdf)). This avoids rewarding self-published claims.
- **Event → score.** An event feeds the score(s) whose dataset definition names it ([`risk_criteria_description.md`](../risk_criteria_description.md)), at full weight. It also always feeds Media_Sentiment, and feeds Market_Sentiment if its area is reputation.
  - Compliance ("lawsuits, regulatory fines, legal disputes"): fines, lawsuits, fraud/corruption cases, sanctions.
  - Governance ("leadership, ethics, internal controls"): fraud/corruption, leadership scandals, accounting issues.
  - Labor: strikes. Safety: accidents. Quality: recalls/defects. Operational Resilience: plant disruption, delivery failure. Digital: cyber incidents. Financial: insolvency, profit warning. Sub-Tier: supply-chain listings.
  - ESG (a composite) takes only events no specific score names: human rights cases, environmental violations.
- **Knock-outs [D].** Sanctions → Compliance 100. Insolvency → Financial and Credit 100 (default = PD 100%).

**Every constant.**

| Constant | Value | Basis |
|---|---|---|
| B, default base | **12** | [D] With no adverse finding, all we know is "Low" (0–24). The midpoint keeps the error at most ±12 (minimax). If an index gives a base (§A2), that value replaces 12. |
| Anchor: one fresh trusted red event | → **50** | [D] `rules.yaml` red = "serious red flag — review before shortlisting". That matches the dataset's High band, which starts at 50. *Decision 1.* |
| Anchor: one fresh trusted amber event | → **25** | [D] Amber = "watch item", which matches the start of Medium. *Decision 1.* |
| P_red | **43.2** | [D] 50 = 100 − 88·(1 − P/100) → P = 100·(1 − 50/88) |
| P_amber | **14.8** | [D] P = 100·(1 − 75/88) |
| Severity | none of its own | [D] Severity acts only through the existing `rules.yaml` rule "low severity turns red into amber". This removes the earlier 45/25/10 points and the 1.0/0.6 type factors. |
| Consequences (not parameters) | 2 reds → 71.6; 3 reds → 83.9 (Critical); 2 ambers → 36.1 | Critical needs several serious events or a knock-out. |
| D_age | 0.5^(age/h), with **h = 0.646 × stale_after_years** | [D] `rules.yaml` steps a stale fact down one colour. So at age = stale, a red must equal an amber: D = 14.8/43.2 = 0.342 → h = ln 2 / ln(1/0.342) × stale. Check: an amber at its stale date scores 16.4, which stays Low ("neutral"). |
| Drop age | 2 × stale_after_years | [D] The second step down (amber → neutral for a red). |
| h by type | 3 y default → **1.94 y**; 5 y → 3.23 y; 10 y → 6.46 y; `never` → no decay | [D] From `stale_after_years` in `rules.yaml`. |
| Media/Market stale | **1 y** (h = 0.65 y, drop at 2 y) | [S ✅] "The RRI decays to zero over a maximum period of two years" ([RepRisk Bloomberg dictionary](https://www.reprisk.com/media/pages/partners/bloomberg/3957378584-1747979546/reprisk-data-bloomberg-terminal.pdf)). Drop at 2 y = 2 × stale. |
| S, trusted allowlist | **1.0**, all tiers | [D] The allowlist test (RESEARCH_MAP §2) is the vetting step. There is no evidence for ranking tiers, so the earlier 0.85 is removed. |
| S, company-stated adverse fact | **1.0** | [S ✅] A statement against one's own interest is presumed reliable ([FRE 804(b)(3)](https://www.law.cornell.edu/rules/fre/rule_804)). |
| S, unverified | **0.55 / 0.40 / 0** | [S ✅ + C] §A4 |
| "Low" fine or lawsuit | < **0.1%** of revenue | [C] Anchor: [Reg. 1/2003 Art. 23](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32003R0001) ✅ caps procedural fines at 1% and substantive ones at 10% of turnover. 0.1% is one decade below the procedural cap. |
| Other "low" severities | definitions, no numbers | Recall: Safety Gate "less than serious risk" ([2019/417](https://www.legislation.gov.uk/eudn/2019/417/annex/division/2/division/5)). Cyber: no outage and no data loss. Strike: no reported production loss. Accident: no recordable injury. |
| Removed | ×1.2 repeat factor, mitigants ×0.9, negative-outlook notch, 50%/25% secondary feeds | Repeats already accumulate through the product formula. The others are covered by the rules above. |

**Example.** A fresh red fine (trusted) gives Compliance 50. The same fine 4 months old (h = 3.23 y, D = 0.93) gives 47.4. The same fine from an eligible unverified source graded C2 (S = 0.55) gives 31.5.

---

## A4. Unverified (non-allowlist) sources

This applies to facts that have already passed the agent's checks: the quote is on the page, it is the right company, and the quote supports the claim.

**Framework [S ✅]: the NATO Intelligence Grading System ("Admiralty Code").**

| Source reliability | Information credibility |
|---|---|
| A Completely reliable | 1 Confirmed by other sources |
| B Usually reliable | 2 Probably true |
| C Fairly reliable | 3 Possibly true |
| D Not usually reliable | 4 Doubtful |
| E Unreliable | 5 Improbable |
| F Cannot be judged | 6 Truth cannot be judged |

Sources:
- UK MoD [JDP 2-00 (4th ed., 2023) Table 3.1](https://assets.publishing.service.gov.uk/media/653a4b0780884d0013f71bb0/JDP_2_00_Ed_4_web.pdf): reliability and credibility "must be evaluated separately". It warns of circular reporting: material that "has just come from one source" but is repeated, so it looks like corroboration.
- US Army [FM 2-22.3 App. B](https://irp.fas.org/doddir/army/fm2-22-3.pdf): credibility 2 = "Not confirmed; logical in itself; consistent with other information".
- [ATP 2-22.9 (OSINT) Tables 2-1/2-2, §4-12](https://irp.fas.org/doddir/army/atp2-22-9.pdf): "A first-time source … is given a source rating of F", and "hearsay" and "uncorroborated e-mail" are listed as non-authoritative sources.
- UK [College of Policing 3×5×2](https://www.college.police.uk/app/intelligence-management/completing-intelligence-report): an anonymous source is Grade D, "no means of assessing", and corroboration must be "independent and not from the same original source".

The language model only records signals. Code assigns the grade.

**Step 1. Eligibility gate (any "no" → S = 0; the fact is listed as an unconfirmed lead).**

| Gate | Source of the rule |
|---|---|
| E1 On-record attribution: named person, organisation or document. Not "sources say", "insiders", "reportedly", rumour | Police 3×5×2: anonymous = D. ATP 2-22.9: hearsay is non-authoritative. [AP](https://www.ap.org/wp-content/uploads/2024/02/ap-news-values-and-principles-1.pdf) ✅ allows anonymous material only when it is "information and not opinion or speculation" and the source has "direct knowledge", with a manager vetting it. We cannot do that vetting. |
| E2 A fact, not opinion or forecast | AP ✅. [Reuters Handbook](https://www.mediareform.org.uk/wp-content/uploads/2015/12/Reuters_Handbook_of_Journalism.pdf) ✅: "Reuters aims to report the facts, not rumours". |
| E3 Accountable publisher: named legal entity, named author or institutional statement | RESEARCH_MAP §2; JDP 2-00 (reliability of organisational sources) |
| E4 Publication date and event date | RESEARCH_MAP §2 |
| E5 Specific: names the company plus at least one of amount, place, case/file number, named authority | FM 2-22.3 credibility 2–3 requires the claim to be "logical in itself"; a checkable detail makes that testable. |
| E6 Not social media, forum, review site, leak site, aggregator or content farm | RESEARCH_MAP "Not trusted"; ATP 2-22.9 §4-12 (blogs, self-published) |
| E7 Not contradicted by a trusted source | Credibility 4–5 |

**Step 2. Source reliability.**
- **B** = official domain of any country (checked by code).
- **C** = passes E3 and shows an editorial-accountability signal: a published corrections policy, IFCN signatory ([commitments](https://ifcncodeofprinciples.poynter.org/the-commitments)), or an established newspaper, trade journal or NGO.
- **D** = passes E3 only.
- E/F = ineligible.

**Step 3. Information credibility.**
- **1** = an independent trusted source confirms it → it becomes a trusted fact with S = 1.0.
- **2** = cites a primary document with an identifier, **or** is confirmed by an independent eligible source.
- **3** = a single eligible source.
- A **D** source reaches at most 3, and only with a primary document. JDP 2-00 allows credible information from weak sources; this coupling makes such information traceable.

**Step 4. Discount factor.**
- [S ✅] [JDP 2-00 Table 3.2](https://assets.publishing.service.gov.uk/media/653a4b0780884d0013f71bb0/JDP_2_00_Ed_4_web.pdf), the PHIA Probability Yardstick that UK Defence mandates: "Likely or Probably" ≈ 55–75%, "Realistic possibility" ≈ 40–<50%.
- **Credibility 2 → S = 0.55, credibility 3 → S = 0.40.**
- [D] We take the lower bound because a false positive harms a supplier, and both Reuters and AP treat single unconfirmed sources as the exception.
- [C] S is meant as the probability that the fact is true, so it can be measured (§A6).

**Step 5. Guards.**
1. **Never a knock-out.** An unverified-only sanctions listing or insolvency scores 0 and triggers a search of the official register. Those registers exist precisely for these facts.
2. **At most +25 points from unverified-only events** [D: one Level band is 25 points wide]. The Level can never move by more than one step on unverified material alone.
3. **One event, one count.** Merge by type, month and specific detail, and keep the highest S.
4. **Independence.** Corroborating sources must have:
   - different publishers and owners;
   - no citation or credit of the other source, and no shared wire credit;
   - no shared passage of **≥ 25 consecutive words** [D: the agent's maximum quote length, so a longer overlap means copying];
   - at least one detail of their own.

   This catches syndication: one story on 10 sites is one source. Reuters requires pickups to "name the source" ✅, so a pickup that names its origin is not independent.
5. **Trusted evidence wins.** Trusted confirmation → S = 1.0. Trusted contradiction → S = 0.
6. **Labelling.** Such a score is labelled "includes unverified sources" with Low confidence. Coverage shows the unverified-only share.
7. **Injection guard.** Page text claiming to be "verified" or "official" changes nothing.

---

## A5. Combining and reporting

- **Total** = round_half_to_even(Σ_assessed w·s / Σ_assessed w). **Coverage c** = Σ_assessed w.
- **Range** = [Σ_assessed w·s, Σ_assessed w·s + 100·(1 − c)]: the total if every missing score were 0 or 100.
- **Minimum coverage 50% [D].** The range is 100·(1 − c) wide. Requiring it to be ≤ 50 keeps the true total within ±25 points (one band) of the range's midpoint, so c ≥ 0.5. With maximum coverage at 0.87, missing both Financial and Operations (0.46) already fails this test, so no separate rule is needed.
- **Umbrella scores** use the same formula inside each umbrella. Umbrella coverage = assessed weight / umbrella weight.
- **Confidence per score.**
  - High: agency rating, index value, or accounts for the latest or previous fiscal year.
  - Medium: at least one trusted adverse event, or a fact corroborated by a second source (JDP 2-00 §3.28: "at least one other source" ✅).
  - Low: everything else.
  - The total's confidence = share of assessed weight at each level.
- **Knock-out (default).** The total is computed as usual; the verdict says "Knock-out".
- **Report (settled).**
  - Page 1: the total and the six umbrellas, each with score, Level, coverage and confidence; one line with the range; the separation note.
  - Page 2: a note of 150 words or less with the weights, bands, the "missing ≠ 0" rule, index vs event scores, and one line on unverified sources.
  - Per-score detail goes in `result.json`.

---

## A6. Calibration and sanity checks

**Labelled set (10 companies, scored at a fixed date, method frozen first).**
- Troubled: Leoni AG as of mid-2023 (StaRUG restructuring, share capital cut to zero, delisted; [Gleiss Lutz](https://www.gleisslutz.com/en/mandates-firm-news/restructuring-plan-legally-binding-gleiss-lutz-advises-leoni-ag-starug-procedure)); Northvolt (Chapter 11 Nov 2024, Swedish bankruptcy 12 Mar 2025; [ESS News](https://ess-news.com/2025/03/12/northvolt-files-for-bankruptcy-in-sweden)); Talgo (DB ICE L delays and order cut ⚠️ trade press; [Railmarket](https://railmarket.com/news/rolling-stock/33961-db-may-cut-talgo-230-order-to-60-trains-due-to-delays-might-pull-these-trains-by-vectrons)); plus two more chosen at run time.
- Stable: Knorr-Bremse (S&P A− stable, Moody's A3 stable ✅ [Knorr-Bremse IR](https://ir.knorr-bremse.com/en/corporate-bonds)); plus four more A/BBB-rated rail or industrial suppliers with no known major incidents, chosen before scoring.

**Pass rule.**
- Every troubled company is ≥ High on its affected umbrella, or is a knock-out.
- Every stable company is ≤ Medium on every umbrella, with a total of Low or Medium.
- Two hand reviewers recompute two scores per company and get the same result.

**The four [C] parameters, and what would change each.**

| Parameter | Start | Change it if … |
|---|---|---|
| "Low" fine threshold | 0.1% of revenue | Hand reviewers disagree with the low/not-low call on ≥ 2 fines → move it one half-decade (0.03% or 0.3%) towards their calls |
| Safety doubling anchor | 2× industry rate = one amber | A stable company with a published rate lands ≥ High, or a company with a known fatal record lands Low |
| S for credibility 2 | 0.55 | After 20 or more eligible unverified events: set S to the share later confirmed by trusted sources, clamped to the PHIA range of that grade |
| S for credibility 3 | 0.40 | Same rule |

**If an anchor fails.** If the pass rule fails while these four are in range, the anchors themselves (Decision 1) go back to the team. We never fit the anchors to the synthetic dataset.

**Other checks.**
- Determinism: same input, same output.
- Table tests: BBB → 21; Z″ 5.70 → BBB− → 33; WGI 70 → 30; one fresh red → 50.
- Time travel: Leoni scored at 2021, 2023 and 2025.
- Leave-one-source-out: no score moves by more than one band.
- Fixtures: one story syndicated to 10 sites counts once at ≤ 0.55; an "insiders say" claim scores 0; an unverified-only insolvency produces no knock-out.

---

## A7. Verification log (Tavily, 2026-10-18, 16 calls)

| Item | Result |
|---|---|
| INFORM scale | ✅ "risk score out of 10 … for each of the dimensions, categories" (2017 methodology) |
| INFORM licence | ⚠️ Only the report's reuse notice (attribution) was found; no separate data licence on the methodology page or home page. Handling: attribute; treat as reuse-with-attribution. |
| EcoVadis bands and medals | ✅ 2026 methodology PDF |
| MSCI letter groups | ✅ Symbols & Definitions, Mar 2026 |
| MSCI terms | ✅ No commercial use without permission; the search tool is client-only |
| Sustainalytics bands | ✅ FAQ (2020 edition) |
| Sustainalytics terms | ✅ "internal, non-commercial use only" |
| RepRisk decay | ✅ "decays to zero over a maximum period of two years" (Bloomberg dictionary) |
| RepRisk "less sensitive" wording | ❌ Not in RepRisk documents read; Wikipedia only. No longer used. |
| EU 2016/1799 mapping and benchmarks | ✅ Annex I (3-year benchmarks), Annex III |
| Reg. 1/2003 Art. 23 | ✅ 1% procedural cap, 10% substantive cap |
| CRR Art. 138 | ✅ |
| FRE 804(b)(3) | ✅ |
| BLS NAICS 3365 | ✅ 2024 TRIR 2.4 |
| FM 2-22.3 App. B, ATP 2-22.9 | ✅ via Tavily (direct curl and WebFetch had returned empty files) |
| College of Policing 3×5×2 | ✅ `college.police.uk` page via Tavily (the `app.` host returns "Access denied") |
| AP sourcing rules | ✅ AP News Values PDF |
| Reuters sourcing rules | ✅ Handbook PDF (2015 mirror) |
| Berg et al. | ✅ Review of Finance summary page, 38–71% |
| Knorr-Bremse rating | ✅ IR page: S&P A− stable / Moody's A3 stable (company-stated) |
| Still ⚠️ (search summaries only) | Moody's modifier wording; SEC Item 1.05 details; CVSS bands; SecurityScorecard bands; Safety Gate 2024 update; TI CPI licence |
| Not re-checked | Talgo's current status |

Unchanged and already checked earlier: S&P Table 26, Altman Z″ table, WGI 2025 method, JDP 2-00 tables.
