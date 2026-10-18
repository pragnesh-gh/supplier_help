# Research agent (first draft)

A bounded "deep research" agent for the Siemens supplier-risk challenge. A buyer names a real company; the agent confirms the legal entity, plans its research, searches trusted public sources first, fills gaps from the open web (clearly marked as unverified), digs deeper on red flags, and returns a short risk report with source links.

**Status:** draft. All tests run offline on invented fixture data. Two live runs so far (Knorr-Bremse, 2026-10-18). Run 1: ok, 63 s, 12 searches, 10 extracts. Run 2: ok, 66 s, 17 searches, 15 extracts, 0 model errors. The problems they showed are fixed offline and have not been tried live yet. Run 1: cut-off dates, keyword-soup queries, empty Operations and People areas, off-target pages, "No issues found" without evidence, a stiff summary. Run 2: an old settled case shown as green, Country not assessed, different facts in each run, no log of why pages were dropped. See [examples/sample_report.md](examples/sample_report.md) for the report layout. It uses a fictional company.

**Start here:** [RESEARCH_MAP.md](RESEARCH_MAP.md) explains which sources are trusted, what is searched per risk area, the gaps, and how the work is split.

## Challenge requirements and where they are met

| Challenge asks | How the agent does it | Where you see it |
| --- | --- | --- |
| A buyer names a real company | `run_research(company, country, website)` resolves the legal entity from trusted sources. If several companies match, it returns `needs_clarification` with candidates and a question. | `result.entity`, `result.clarification` |
| Plans its research | Fixed plan: 6 risk areas, official sources first, then news. The small model only rewrites query wording. | `plan` progress event, `result.plan`, report header |
| Crawls news, public sources, company sites | Tavily search on the trusted allowlist (registers, regulators, sanctions lists, business and rail press, the company's own site) first. Then an open-web search fills areas with too few trusted pages; those pages are kept but labelled `unverified`. Denylisted sites (social media, forums, leak sites, aggregators, content farms) are always dropped. Tavily extract gives full page text. | `result.sources[].trust`, Sources section (✅ / 🟨) |
| Digs deeper on red flags | The verifier picks at most 2 red or watch items. A narrow follow-up search finds corroboration or new facts. | "What we dug into" section, `result.followups` |
| Risk report with source links | `report.md` (page 1 at a glance, page 2 details) and `result.json`. Every finding is numbered [n] and links to its source with publication and access dates. Unverified sources carry 🟨 "not in our trusted source list". | `report.md` |

## Pipeline

```
company, country?, website?
        │
  1 Identity ── Tavily search (official + press) → gatherer lists candidate entities
        │        → code decides: one entity → ok │ several → needs_clarification (stop)
  2 Plan ────── 14 short searches (company + 1–3 terms) straight from config templates, English
        │        and the local language (fixed translations for de/fr/it/es; the gatherer only
        │        translates other languages, cached per day); heavier areas get more (operations 4),
        │        plus a litigation-history search
 2b Country ─── World Bank WGI (Tavily extract of the World Bank API page, parsed by code) and
        │        TI CPI (official file in data/country/) → one structured country fact, no model
  3 Search ──── a) trusted: Tavily /search, include_domains = allowlist tier, start_date = look-back
        │           off-list, denylisted, and news results not naming the company are dropped
        │           stable order: tier, (financial: newest first), score, URL
        │           12 trusted pages split by area weight (ops 4, fin 2, people 2, legal 2,
        │           country 1, reputation 1); unused pages go to other areas, heaviest first
        │        b) open web: areas with fewer trusted pages than their share get one search
        │           with no include_domains (denylist AND allowlist excluded); 1 page per area,
        │           "unverified"; every result not read is logged with a reason
  4 Read ────── Tavily /extract (max 19 pages: 12 trusted + 1 World Bank data page + 2 open web
                + 4 follow-ups); same-day cache: a rerun reuses search, extract and model answers
  5 Extract ─── gatherer (Sonnet 5.5, medium effort) pulls candidate facts + exact quotes
  6 Check ───── code: quote must appear in the page text, otherwise dropped
                verifier (Opus 5.5, medium effort): supported? right entity? relevant?
                → event_type + severity from fixed lists, plus grading signals
  7 Rules ───── config/rules.yaml → red / amber / green / neutral, knock-outs, verdict
                unverified-only facts: red → amber, green → neutral, never a knock-out
  8 Dig deeper ─ verifier picks ≤2 red/amber items → short TRUSTED searches, English + local
                language → steps 4–7 again
                a trusted match upgrades an unverified fact to its full colour
  9 Score ───── scoring.py seam: per-area score placeholders ("not scored yet")
 10 Report ──── verifier writes 2–3 sentence summary from verified facts only
                code renders report.md from result.json (fixed template)
```

Budget (in `config/settings.yaml`): 22 searches, 19 page extracts, 2 follow-ups, 120 s wall clock. When time runs out, the run returns `status: "partial"` with what it has so far. Every network and model call is time-bounded.

How the budget is split, and why:
- **Searches (22):** 1 identity + 14 area searches + 2 open web + 4 follow-up (2 follow-ups × English and local) + 1 spare. The first live run (Knorr-Bremse, 2026-10-18) used one 8–10-term query per area; the operations, people and official-legal queries returned nothing. Short, focused queries recall better, so each topic now gets its own query, and local press is searched in its own language. Area searches follow the area weights: operations (30%) 4, legal 4 (incl. litigation history), financial 2, people 2, reputation 2, country 0 (country figures come from data, not search).
- **Trusted pages (12):** split across areas by their weight in `config/scoring.yaml` (largest remainder, at least 1 each): operations 4, financial 2, people 2, legal 2, country 1, reputation 1. Pages an area cannot fill go to the other areas, heaviest first. The first live run read only 8 of 12 candidate pages and finished in 63 of 120 s, so there was room. Country has no searched pages now, so its share goes to the other areas.
- **Extracts (19):** 12 trusted + 1 World Bank data page + 2 open web + 4 follow-up pages. Trusted pages cannot use the open-web share, and open-web pages cannot use the trusted or follow-up share.
- **Paid cost grows.** Tavily: up to 21 advanced searches (2 credits each) instead of 12, so about 42 credits instead of 24; extracts are cheap (1 credit per 5 pages). Models: up to 15 main-pass pages instead of 10, so roughly 50% more gatherer and verifier tokens, which is most of the run's cost. The reason: the area with the highest weight (operations) came back "Not assessed", and four of the ten pages read were off-target. With the off-topic filter, more of the pages read are useful. To get back to the old cost, set `max_trusted_pages: 8` and drop the `lang: local` searches; operations still gets the largest share.
- **Time:** the open-web wave runs after the trusted wave (it needs to know where the gaps are), which adds one search round trip. 15 pages at 6 parallel workers is 3 waves instead of 2. Expected run time is about 80–100 s; the 120 s cap is unchanged and returns `partial` if reached.

## Running it

```sh
pip install --break-system-packages -r research_agent/requirements.txt
cp research_agent/.env.example research_agent/.env      # add ANTHROPIC_API_KEY, TAVILY_API_KEY

python -m research_agent --check                         # validates config and keys; no paid calls
python -m research_agent --fixture                       # offline demo on invented data
python -m research_agent "Knorr-Bremse" --country DE --website knorr-bremse.com
```

Output goes to `research_agent/output/<slug>-<date>/report.md` and `result.json`. The folder is git-ignored. Progress lines print to stderr.

Report layout. `report.md` and `report.html` follow BAFA's risk-analysis guide (the German Supply Chain Act authority), used for all six risk areas; see [docs/research/report-template-standard.md](../docs/research/report-template-standard.md). The sections are always present, in this order: 0 header (legal entity, country, website, research date, sources checked); 1 summary for decision makers (verdict, total, six area scores, overrides, 3–5 key points, areas not assessed); 2 supplier profile (missing fields say "Not found", order volume is buyer input); 3 country and sector risk (WGI and CPI figures); 4 company-specific risks found, by area in a fixed order (Operations & Delivery, Financial, People & Safety, Legal & Governance, Country & Location, Reputation & Outside View), with strengths as "Checked, nothing adverse found" rows and an event timeline; 5 weighting and prioritisation (area scores with bands, radar with hollow axes for "Not assessed", likelihood × severity heatmap); 6 risk register (description, owner "Assigned by buyer", weighting, suggested measures); 7 from priority risks to prevention (next steps tied to register codes); 8 documentation (method, heatmap rule, per-fact score breakdown with override lines, follow-ups, limits, sources with trust labels, dates and quotes). A footer says the report is not a legal LkSG risk analysis.

`report_data.report_sections(result)` returns the same sections as a list of plain dicts (JSON-ready, every citation with its quote and link), so the web app can render the same order. The heatmap rule lives in `config/report.yaml`. The chat TL;DR (`tldr.py`) uses the same total line and the same key points as section 1. Same input gives a byte-identical report; nothing is trimmed from section 4. `report.md` never mentions `result.json`.

Source marks. A citation of an unverified site reads `[7]🟨 not in our trusted source list`, and the flag says "unverified source only". In the Sources list every line starts with `✅ trusted` (or `✅ trusted, company-stated`) or `🟨 not in our trusted source list`. Why 🟨 and not 🟡: the circles already mean flag colours (🟡 = watch item), so a yellow square avoids reading a source mark as a flag colour.

From Python (chatbot / UI):

```python
from research_agent import run_research

result = run_research("Knorr-Bremse", country="DE", website="knorr-bremse.com",
                      on_progress=lambda ev: ui.push(ev.kind, ev.message, ev.data))
if result.status == "needs_clarification":
    ask_user(result.clarification.question, result.clarification.candidates)  # then call again with country/website
```

Status values: `ok`, `partial` (time limit), `needs_clarification`, `error` (missing keys or bad config; see `warnings`).

Tests and type checks:

```sh
pytest -q research_agent/tests
mypy --config-file research_agent/mypy.ini research_agent
```

## Config files (edit without code changes)

- `config/sources.yaml`: the trusted-source allowlist, grouped in tiers: official, company_own (filled at run time), major_news, rail_trade, country_data. To add a source, add one line: `domain: Publisher`. Its `denylist` section lists sites that are never used (social media, forums, leak sites, aggregators, content farms). A domain on both lists is a config error. Any other site can only come in through the open-web pass, labelled unverified.
- `config/rules.yaml`: maps each event type to a colour and risk area. It also sets the staleness window, knock-outs, verdict wording and next-step wording.
- `config/settings.yaml`: model IDs and effort, budget, look-back years, the search templates for each risk area, and the `open_web` gap-fill settings.
- `config/scoring.yaml`: score level bands and the (unconfirmed) mapping from the agent's 6 risk areas to the dataset's 6 umbrellas, weights and 18 score columns. No scoring method.
- `prompts/*.md`: model instructions as plain text.
- `data/country/`: the official TI CPI results file (unmodified, CC BY-ND 4.0) and an ISO2→ISO3 table built from the World Bank country list.

## How flags are decided

1. The gatherer extracts a candidate fact with a quote of at most 25 words copied from the page.
2. Code checks that the quote is really in the text Tavily returned. Case, whitespace and minor punctuation are ignored. If the quote is missing, the fact is dropped.
3. The verifier checks the quote supports the claim, confirms the fact is about the confirmed entity or its group (not a namesake), and confirms it matters for supplier risk. Then it labels the fact with an `event_type` and `severity` from fixed lists.
4. `rules.yaml` decides the colour. Examples: `regulatory_fine` → red; `product_recall` → amber; `iris_certified` → green; low severity turns red into amber; events older than the staleness window step down one level.
5. A `sanctions_listing` or `insolvency_filing` → **"Knock-out risk found — do not proceed without escalation"**.
6. The verdict is text chosen by code: knock-out › red flags › watch items only › "No red flags found in the sources checked". If no trusted page was read, the verdict is "Not enough evidence". The report never says "no risk".

Facts from the company's own website are labelled *company-stated*.

### Country data (structured, no model)

| Input | How it is read | Why |
| --- | --- | --- |
| World Bank WGI 2025 (source id 3): Political Stability `GOV_WGI_PV.SC`, Control of Corruption `GOV_WGI_CC.SC`, Rule of Law `GOV_WGI_RL.SC` (0–100, higher = better governed) | Default: Tavily `/extract` of `https://api.worldbank.org/v2/country/{ISO2}/indicator/...?format=json&source=3&mrv=1` (trusted worldbank.org), values parsed by code. Switch `country_data.wgi_source: worldbank_api` fetches the same URL directly (free, no key), off by default, for comparison. | Retrieval stays on Tavily, the paid dependency, and works the same whichever LLM is used. Run 2's Transparency International page scrape failed (snippet only), so Country was not assessed. A data endpoint gives the number itself. |
| TI CPI 2025 | The official results file `data/country/CPI2025_Results.xlsx`, unmodified (downloaded 2026-10-18 from images.transparencycdn.org, published 2026-02-10, licence CC BY-ND 4.0, attribution Transparency International), read with the standard library | TI has no API. The file changes once a year. |
| INFORM | Not used yet. It has an API on drmkc.jrc.ec.europa.eu (needs workflow IDs); later, through Tavily extract like WGI. | Natural-hazard risk for Environmental_Exposure. |

The figures become one fact: value, year and source URL each, trusted, `text_origin: "data"`, the exact JSON or table text as the quote (checked like any quote), and `flag.data` with the numbers for the scoring step. Bands on the 0–100 scales, in thirds (`country_data` in settings.yaml): below 33.3 → `country_risk_elevated` (amber), 66.7 and above on every indicator → `country_risk_low` (green), otherwise neutral context. The worst indicator decides. Thirds of the scale rather than fitted cut-offs, so no index-specific threshold is invented; the scoring step will replace them. The old WGI percentile codes (`PV.PER.RNK`) are archived since the 2025 revision; the 0–100 score replaces them. Country figures do not count as evidence about the company for the "Not enough evidence" verdict.

### Reproducibility

Run 1 and run 2 on the same company found different legal matters and different financial periods. Measures:

| Measure | Why |
| --- | --- |
| Queries come straight from the templates; the local language uses fixed translations (de, fr, it, es). The planner model only translates other languages, and its answer is cached for the day. | The planner reworded queries differently each run. |
| Results are ordered by tier, then (Financial) newest first, then score, then URL. | Ties broke differently between runs; the URL makes the order total. |
| Same-day cache (`output/.cache/<day>/`) of Tavily search and extract responses and model answers, keyed by the exact request. Failures are not cached. | Tavily results and model answers both vary; these models accept no temperature setting. A same-day rerun is then identical and free. A new day starts fresh. |
| Litigation-history search (`legal-4`: lawsuit, settlement, court ruling; 10-year look-back; official + major press). | Known legal matters were found by chance (Thiele in run 1, the DOJ case in run 2). |
| Financial area: newest pages first (`prefer_recent`). | Run 2 read H1 2025 figures although H1 2026 reports existed. |
| `result.fingerprint`: config and prompt hash, models and effort, cache day, country-data source, and every query. `python -m research_agent.diff_runs OLD/result.json NEW/result.json` lists facts gained and lost, colour changes, area changes and source changes. | So two runs can be compared and the cause of a difference found. |

Not reproducible across days: Tavily's index changes, and new model answers can differ.

### Why results were not read

Every search result that is not read is logged in `result.plan[].dropped` (URL, title, reason) and counted in `result.stats.drop_reasons`. One trail line gives the counts. Reasons: `denylisted`, `not_allowlisted` (trusted search, site not on its tiers), `off_topic` (news result does not name the company), `trusted_site_in_open_web`, `duplicate` (already chosen), `area_cap` (the area had its share), `page_budget`, `extract_failed` (no text and no snippet). Run 2's open-web searches returned only knorr-bremse.com pages (allowlisted, company_own), so no unverified page was read. The open web now excludes all allowlisted domains as well as the denylist, since those were already searched with the same query.

The name filter now also accepts the company name in the URL (news URLs carry the headline) and spacing variants ("Knorr Bremse", "KnorrBremse"). Run 2 dropped 29 results as off-topic, but their titles were not saved, so how strict the filter is can only be measured on the next run, from the new drop log. A ticker is not matched yet: no trusted source for tickers is wired in.

### Area status: context

An area whose only facts are neutral or older (stale) shows "⚪ Context only", or "⚪ Context: older or resolved matter" with the year when the top fact is stale. It is not "No issues found": an old settled case or a company-disclosed risk is not evidence that there are no issues. "🟢 No issues found" now needs a current green fact (a strength or low country risk). Run 2 showed the 2018 DOJ no-poach consent judgment as "🟢 No issues found".

New event type `antitrust_settlement` (rules.yaml): a settlement, consent decree or consent judgment with an authority, without an admission or court finding. Amber, not red: unlike `regulatory_fine`, no violation was found, but the company accepted obligations, so the buyer should ask about compliance with them. It goes stale after 5 years like other legal matters, and is then shown as context.

### Area coverage

An area shows "🟢 No issues found" only if at least one trusted page gave a verified fact for it (any colour, including neutral context). Pages that were read but gave nothing, or only facts about a namesake, do not count. Then the area is "⚪ Not assessed" and says how many pages were read. In the first live run, Reputation and Country showed "No issues found" although their only pages were about another company or a methodology page. The table's score column ends with the number of pages that backed the area, e.g. "2 trusted pages + 🟨 1 unverified page".

### Dates

Tavily returns `published_date` in ISO or RFC 2822 ("Wed, 29 Jul 2026 00:00:00 GMT"). `dates.py` turns every date into ISO (`YYYY`, `YYYY-MM` or `YYYY-MM-DD`) when a page is read, so the report, the staleness rule and the same-event check all compare the same thing. The first live run showed cut-off dates like "Wed, 29 Ju".

### Summary

The verifier writes the summary. It starts with the verdict in plain words ("No red flags were found, but there is one item to watch: ..."), attributes company-stated figures to the company, says which areas were not assessed, and never writes "rated as" or "no risk". If it does, the template summary is used instead.

### Trusted vs unverified sources

Every source has `trust`: `trusted` (on the allowlist, including company_own) or `unverified` (any other site, found by the open-web pass). Denylisted sites are dropped before any model sees them.

| Decision | Reason |
| --- | --- |
| Trusted sources are searched first; the open web only runs for areas whose trusted searches found fewer pages than the area may read (3). | Trusted sources stay the backbone. The open web is for gaps, mainly Reputation and People & Safety, which official sources rarely cover. |
| A gap is an area whose trusted searches found fewer usable pages than its share. Areas with no trusted page at all go first, then the biggest shortfall, ties by `open_web.umbrellas` order (reputation, people, operations, legal, financial). Country & Location never uses the open web. | Spend the 2 searches where the gap is biggest. Country risk should come from the index publishers only. |
| The open-web search reuses the area's first English search query. | No new queries for the model to invent; the planner's rewrite is reused. English reaches the widest open web. |
| One page per area, 2 per run. | Trusted pages stay the large majority of what is read. |
| In a trusted search, an off-list result is still dropped (not kept as unverified). | A trusted search means "trusted only"; it also keeps the gap count honest. Unknown sites come in only through the open-web pass. |
| Unverified facts go through the same exact-quote check and Opus verification. The verifier is told the source is unverified. | Same bar for every fact; anything resting on unnamed sources should be marked "alleged". |
| An unverified-only fact: red → amber (watch item), green → neutral, never a knock-out. | An unknown site cannot by itself put a supplier on the stop list, and cannot reassure a buyer either (self-promotion and paid placements look like strengths). |
| If a trusted source reports the same event (same event type and month), the fact is re-rated as trusted: full colour, knock-out possible, trusted source cited first, its quote shown. | Corroboration by an accountable publisher is what makes the fact usable. |
| Follow-ups and identity use trusted sources only. The follow-up picker is told which flags are unverified "capped from red". | A follow-up exists to confirm or refute a flag, and only a trusted page can upgrade one. Identity decides which company every fact is about. |
| An area with only unverified pages and no watch item is "Not assessed". "Not enough evidence" means no trusted page was read. | Silence on unknown sites says nothing about the supplier. |
| News, trade-press and open-web results must name the company (first word of the legal name, or first two if the first is generic like "Deutsche"; or the website name) in the title or snippet before a page extract is spent on them. Registers, the company site and country data are exempt. | The first live run spent 3 of 10 pages on two Reuters articles about another company and an unrelated PDF. |
| `publicnow.com` is denylisted (aggregators). | It redistributes releases and reports of many companies. From the domain we cannot tell whose document it is, and the original is on the company's own site or a register, which we already search. |

### Grading signals (for the scoring step)

Each flag carries `signals`, which never change colours. From the verifier, for the fact's primary (first-cited) source: `publisher_named`, `dated`, `claim_specific_checkable`, `cites_primary_document`, `attribution` (`firsthand_official` · `named_source` · `anonymous_or_rumour` · `unclear`). Computed by code:
- `independent_domains`: distinct sources after merging same-domain pages, near-identical pages (80% of the shorter page's 5-word phrases appear in the other) and pages that share a passage of 25 or more consecutive words. The 25-word rule is appendix §A4 guard 4: 25 is the agent's maximum quote length, so a longer overlap means copying.
- `corroborated_by_trusted`: at least 2 independent sources, at least one of them trusted.
- `contradicted_by_trusted` (gate E7): a trusted follow-up page explicitly states the opposite of an unverified claim. The verifier is given the claim and answers `contradicts_claim_under_check`. The fact stays on record as neutral and can no longer knock out.
- `excluded_site_type` (gate E6): always empty, because denylisted site types are dropped before reading.

Each unverified source gets `reliability` (appendix §A4 step 2), set by code from the page text. It is C when the page shows a corrections policy, editorial standards or an ethics code, a masthead or legal notice naming the editors (Impressum, editor-in-chief, directeur de la publication), or IFCN; otherwise D. B (an official domain) is decided by the scoring step.

## Scores

The method is in `scoring.py` and `config/scoring_method.yaml`, owned by the scoring workstream; see `docs/research/facts-to-scores.md` and its appendix. The orchestrator calls `score_detailed(flags, areas, cfg, inputs=..., rules=..., as_of=today, sources=...)`. `as_of` keeps scores reproducible, and `sources` lets official domains count as reliability B. The result keeps:
- `scores`, the card: per-area score, level, coverage and pages used, plus the total and `coverage`, `range_low` and `range_high` (for the report renderers);
- `scoring_detail`: the full `ScoringReport`; `ScoringReport.model_validate(...)` with `explain_text` gives the "How was this scored?" text;
- `scoring_inputs`: the numbers below;
- `numeric_facts`: every number read, accepted or rejected, with its quote.

Rules that hold whatever the method: an area without evidence is never scored (and never 0), and real-company scores are never ranked or charted against the anonymized dataset suppliers. `config.ScoringConfig` has an optional `method` field, so `scoring_method.yaml` can later merge into `scoring.yaml`; the files are separate for now.

### Numbers for scoring (`scoring_inputs`)

The gatherer lists numbers on each page with an exact quote: credit rating (agency, outlook), annual-accounts lines (revenue, current assets and liabilities, retained earnings, EBIT, total equity, total liabilities, total assets), fine amount, injury rate (TRIR, DART, LTIFR) and EcoVadis score. Code accepts a number only if all of these hold:
1. The quote is on the page (same check as facts).
2. The value, exactly as written, is in the quote as a whole number ("9,523" does not match "9,523.4"). A rating's agency must be named in the quote.
3. The page gave a verified fact about this company. This reuses the verifier's entity check, so a namesake's accounts are never used and no extra model call is needed.
4. It parses. Thousand separators and the decimal comma are handled. A single "." is a decimal point except in German figures ("7.887 Mio. EUR" = 7,887 million). "million", "bn", "Mio.", "Mrd." and the currency are read from the unit or the quote.

Assembly:
- **Ratings:** one per agency.
- **Altman Z″:** all lines from one page, one fiscal year and one currency, latest complete year. Total liabilities = total assets − total equity when not stated. The evidence quote joins the line quotes in page order.
- **Fines:** amount from the fine flag's own source page, divided by the latest revenue in the same currency.
- **Injury rate:** against the BLS 2024 NAICS 3365 benchmark from settings (TRIR 2.4, DART 1.7, per the appendix). LTIFR has no benchmark, so it is recorded but not scored.
- **EcoVadis:** the score only, never a medal alone.
- **Country:** WGI Political Stability from the country data, basis "hq" (supplying sites are not known yet).

Unverified numbers are kept but marked; the scorer ignores them.

### New event types (rules.yaml, with reasons there)

| Event type | Colour | Area | Stale after |
| --- | --- | --- | --- |
| `safety_fatality` | red | people | 5 years |
| `environmental_violation` | amber | people | 5 years |
| `data_breach` | amber | operations | default (3) |
| `contract_penalty_or_cancellation` | amber | operations | default (3) |
| `audit_or_accounting_issue` | red | financial | 5 years |
| `supply_chain_forced_labour_listing` | red, knock-out | people | never |
| `antitrust_settlement` (round 3) | amber | legal | 5 years |
| `country_risk_low` (round 3, set by code) | green | country | default |

### Report outputs

The CLI writes `report.md`, `result.json` and `report.html` (from `report_html.py`, owned by the report workstream). Page texts go to the HTML renderer for citation context but are not stored in result.json. Each flag stores `quote_context`: the quote with about 200 characters of page text on each side. Area labels are the dataset umbrella names from `scoring.yaml` (Operations & Delivery, Legal & Governance, Reputation & Outside View, ...), so every output names the areas the same way. `load_all` refuses a settings label that differs. The ids are unchanged.

## Safety of fetched content

Web pages are untrusted data. Each page is wrapped in an `<untrusted_source>` block that the page cannot close or forge. Every system prompt says that content is data, never instructions. Models can only return typed fields. They cannot choose URLs, sources, tools or budget. Retrieval only goes through Tavily searches built from config: allowlisted searches, plus at most 2 open-web searches that reuse a configured query and exclude the denylist. Models never choose which sites are searched. A test runs a prompt-injection page: the model's fake fact is dropped by the quote check, and the verdict, budget and sources stay the same.

## Deviations from the repo docs

- **Claude instead of Nemotron for this draft.** The repo docs name Nemotron via OpenRouter. The team chose Claude (Sonnet 5.5 gatherer at medium effort, Opus 5.5 verifier at medium effort) for the research agent draft. `llm.py` is a small adapter interface, so an OpenRouter/Nemotron class can replace it later.
- **Gatherer is Sonnet 5.5, not Haiku 5.5.** Extraction quality decides what the verifier ever sees. Cost: list prices are $2 / $10 per million input / output tokens for Sonnet 5.5 against $0.10 / $0.50 for Haiku 5.5, so gatherer cost per run goes up about 20 times. Model IDs and effort are in `config/settings.yaml` (`RESEARCH_*_MODEL` / `RESEARCH_*_EFFORT` env vars override).
- **Rule-based colours.** `docs/research/company-fixture.md` asks for neutral tags and "no invented red/yellow/green company rating". The team decided on red/amber/green **flags per sourced fact**, set by a published rulebook, not by the model. There is still no company score; the score fields are placeholders. The other display rules are kept: source date separate from access date, "company-stated" label, "no issues found in sources checked" wording, and no mapping to `SUPP_*` IDs.
- **Budget:** 120 s wall clock, not the 90 s in the delivery plan, as agreed for this draft. 14 searches / 14 extracts instead of 12 / 12 for the open-web pass (reasons above).
- **Open web.** The earlier draft never used pages outside the allowlist. The team asked for open-web gap filling with clear marking; the sites RESEARCH_MAP.md used to call "not trusted" are now either denylisted or allowed only as unverified (blogs, for example, are unverified, not denylisted).

## Verified vs not verified (checked 2026-10-18)

- Verified on platform.claude.com: model IDs `claude-haiku-5-5` and `claude-opus-5-5`. Structured outputs via `client.messages.parse(output_format=<pydantic model>)`, which sends `output_config.format`; both models are listed as supported.
- Verified in the Claude API reference bundled with Claude Code (model table cached 2026-10-06): model ID `claude-sonnet-5-5` exists. Effort is set as `output_config: {"effort": "low"|"medium"|"high"|"xhigh"|"max"}` (GA, no beta header). Sonnet 5.5 defaults to `high` with recalibrated levels; Opus 5.5 defaults to `medium`. On both, omitting `thinking` means adaptive thinking and disabling it is rejected, so the adapter sends no `thinking` field.
- Verified against the SDK 1.15.0 source and a mock-transport test: `messages.parse(output_format=..., output_config={"effort": ...})` merges both into one `output_config` with `effort` and `format`.
- Verified on docs.tavily.com (2026-10-18): `exclude_domains` (max 150); `include_domains_mode` without `include_domains` returns a 400, so the open-web request sends neither.
- Verified against the anthropic SDK 1.15.0 source: the adapter was smoke-tested against the real SDK over a mocked HTTP transport. The SDK now depends on `httpx2`.
- Verified on docs.tavily.com: `/search` parameters (`include_domains`, `include_domains_mode`, `topic`, `start_date`, `search_depth`, `max_results`, `include_published_date`) and `/extract` (`urls`, `extract_depth`, `format`, `timeout`). The current API has **no `days` parameter**, so the agent uses `start_date`.
- Verified by the first live run (2026-10-18): `effort: medium` with structured outputs works on `claude-sonnet-5-5` and `claude-opus-5-5`; no call hit `max_output_tokens: 16000` or the 60 s timeout; Tavily returns `published_date` in RFC 2822.
- Verified 2026-10-18 with free GETs: World Bank API source 3 is the WGI 2025 revision (last updated 2026-09-25); codes `GOV_WGI_{PV,CC,RL,...}.EST/.SC`; `PV.PER.RNK` is archived; several indicators in one call (`;`) with `mrv=1` work; the response is saved in `tests/fixtures/country/`. TI's CPI 2025 file is linked from transparency.org/en/cpi/2025 (CC BY-ND 4.0). Germany: PV 69.3, CC 81.9, RL 85.1 (2025), CPI 77, rank 10 of 182.
- **Not verified:** whether Tavily `/extract` returns the World Bank API JSON as text (if not, the country fact is missing and a warning says so; switch to `worldbank_api` to compare); the third-round fixes live (templates, cache, litigation slot, drop log, open-web exclusions); how strict the name filter is on real results; real cost and latency of the larger budget; model output quality beyond one company. The server-side refusal fallback (beta) is not used; a refusal still drops that page's facts. The server-side refusal fallback (beta) is not used; a refusal still drops that page's facts.

## Known limitations

- Identity relies on what trusted sources say. Small private firms may need country and website from the buyer.
- `published_date` from Tavily can be missing or later than the original date. Event dates come from the page text when stated.
- Duplicate events are merged only when type and month match. Syndicated copies on different domains may still appear as separate sources.
- Sanctions lists are searched through Tavily, not through the official list APIs. A missing hit is not proof of "not sanctioned".
- The denylist is a list of domains, not a classifier. A new content farm or an AI-written site will come in as unverified until someone adds it.
- Corroboration matching uses event type and month. Two different events of the same type in the same month would be merged, and an unverified fact with no date is never matched.
- Paywalled news (FT, WSJ, Bloomberg) may give only snippets. The agent then uses the search snippet, recorded as `text_origin: "search_snippet"`.
- The country area uses general country-risk pages. It is not a structured INFORM or CPI lookup.

## Next steps

1. Get keys, run `--check`, then do live runs on 3 real companies, including one ambiguous name and one small supplier. Check every cited quote by hand.
2. Tune the allowlist and query templates using observed Tavily results. Add direct OpenSanctions and GLEIF API lookups for identity and sanctions.
3. Add an evaluation set (namesakes, stale news, allegations vs confirmed facts) to measure verifier precision.
4. Wire `run_research` into the chatbot "deep research" button and stream `on_progress` events to the UI.
