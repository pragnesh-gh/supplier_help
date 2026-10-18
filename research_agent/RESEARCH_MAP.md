# Research map: what the agent searches, where, and why

This page answers four questions for the team:
1. How does the agent plan its research?
2. Which sources count as trusted, and why?
3. What exactly is searched for each risk area?
4. What is still missing, and how do we split the work?

Status labels: ✅ **in config now** · 🟡 **proposed, not added yet** (verify the site first).

---

## 1. How the agent plans and runs research

```
Buyer clicks "Deep research" in the chatbot
        │
        ▼
1. Identity      Who exactly is this company? (legal name, country, website)
                 If several companies match → ask the buyer to pick one.
        │
        ▼
2. Plan          Fixed search slots per risk area (config/settings.yaml).
                 Small model (Haiku) only rewrites the wording of each query,
                 e.g. adds German terms like "Insolvenz", "Bußgeld", "Rückruf".
                 It can NOT add websites or change the list of sources.
        │
        ▼
3. Search        Tavily searches ONLY the allowlisted domains for each slot.
                 Official sources first, then company site, then news.
        │
        ▼
4. Read pages    Up to 12 full pages are extracted.
        │
        ▼
5. Extract       Small model pulls candidate facts, each with an exact quote.
        │
        ▼
6. Check quotes  Code: the quote must really be on the page, or the fact is dropped.
        │
        ▼
7. Verify        Strong model (Opus): right company? supported? relevant?
                 Labels each fact with an event type (e.g. "product_recall").
        │
        ▼
8. Dig deeper    Up to 2 red flags get a narrow follow-up search
                 (e.g. "was the fine appealed?").
        │
        ▼
9. Flags         Rulebook (config/rules.yaml) decides 🔴 / 🟡 / 🟢. Not the AI.
        │
        ▼
10. Report       1-page Markdown report + full data (JSON) for the chatbot.
```

**Why it's built this way:** the AI only *reads and checks*. Choosing sources, colours and the verdict is fixed code and config, so the same evidence always gives the same result.

**How news is found:** Tavily has a `news` mode that favours recent articles with publication dates. The agent uses it for financial, legal, reputation and people searches, limited to the trusted news sites below. It looks back **3 years** normally and **10 years** for legal matters (sanctions, insolvency, court cases).

---

## 2. What counts as a trusted source

A source is trusted only if **all** of these hold:

| Test | Why |
|---|---|
| **Accountable publisher**: a government body, court, regulator, the company itself, or a news outlet with an editorial standard and corrections policy | Someone is responsible for errors |
| **Primary or close to primary**: it reports the fact itself, not a rewrite of a rewrite | Fewer distortions |
| **Dated**: the page shows when it was published | Old news must be recognisable as old |
| **Stable URL** | The buyer can open the link later |

**Not trusted:** blogs, forums, social media, press-release aggregators, AI-written sites, anonymous review sites, leak sites.

**Special case: company's own website.** Used, but always labelled **"company-stated"**. A company describes itself favourably, so its claims are never presented as independent facts.

---

## 3. The trusted sources, by tier

Searched in this order (tier 1 first).

### Tier 1: Official registers, regulators, courts ✅

| Source | What it gives us |
|---|---|
| OpenSanctions (opensanctions.org) | Combined sanctions and watch lists from many countries |
| US Treasury / OFAC | US sanctions list |
| EU Sanctions Map, EUR-Lex, EU Open Data | EU sanctions and legal acts |
| UN Security Council sanctions | UN sanctions list |
| UK Government (gov.uk) | UK sanctions, Companies House, UK rail accident reports (RAIB) |
| Insolvenzbekanntmachungen, Unternehmensregister, Handelsregister (DE) | German insolvencies and company register |
| Bundeskartellamt, BaFin | German cartel fines, financial supervision |
| US SEC, US Department of Justice | US filings, enforcement and criminal cases |
| GLEIF | Legal Entity Identifier: confirms the exact legal company |
| European Commission, Court of Justice of the EU | EU competition fines, court rulings |
| EU Agency for Railways (ERA) | EU rail safety and authorisation information |

### Tier 2: Company's own website ✅

Added automatically at run time from the confirmed website. Annual reports, investor pages, certificates. Always labelled "company-stated".

### Tier 3: Major business press ✅

Reuters, AP News, Bloomberg, Financial Times, Wall Street Journal, The Economist, CNBC, BBC, Deutsche Welle, Handelsblatt, FAZ, Süddeutsche Zeitung, Der Spiegel, WirtschaftsWoche, NZZ, Les Echos, Le Monde, Il Sole 24 Ore, Expansión, Politico Europe.

**Note:** Bloomberg, FT and WSJ are often paywalled, so Tavily may return only part of the article. Reuters and AP are usually fully readable.

### Tier 4: Rail trade press ✅

Railway Gazette International, International Railway Journal, Railway Technology, Railway Age, Global Railway Review, UNIFE (European rail industry association).

**Why this tier matters:** recalls, delivery delays and quality problems at rail suppliers often appear **only** in trade press, not in general news.

### Tier 5: Country risk data ✅

| Source | What it gives us |
|---|---|
| EU JRC INFORM risk index | Natural-hazard and crisis risk per country |
| World Bank | Governance indicators, e.g. political stability |
| Transparency International | Corruption Perceptions Index |
| OECD | Country economic and governance data |

---

## 4. What is searched for each risk area

| Risk area | Sources searched | What we look for | Typical 🔴 / 🟡 / 🟢 |
|---|---|---|---|
| **Financial** | Official + company site; then major news | Annual results, credit ratings, losses, profit warnings, insolvency | 🔴 insolvency · 🟡 profit warning, downgrade · 🟢 strong results |
| **Legal & Compliance** | Official; then major news (10-year look-back) | Sanctions, insolvency, fines, lawsuits, corruption, investigations | 🔴 sanctions (knock-out), fine, fraud · 🟡 lawsuit |
| **Country & Location** | Country data | Country corruption, stability and hazard indices | 🟡 elevated country risk |
| **People & Safety** | Major news + rail trade | Strikes, accidents, injuries, labour disputes, human rights | 🔴 fatal accident, forced labour · 🟡 strike |
| **Operations & Quality** | Rail trade + news + company site | Recalls, defects, delivery delays, cyber attacks, plant outages, IRIS certificate | 🟡 recall, cyber incident · 🟢 IRIS / ISO certified |
| **Reputation** | Major news | Scandals, controversies, governance problems | 🟡 leadership scandal · 🟢 major award or contract |

The exact queries are in `config/settings.yaml` under `umbrellas`. The colour rules are in `config/rules.yaml`.

---

## 5. Gaps, and sources to add next 🟡

Each of these needs a quick check: does the site have public, dated pages that Tavily can reach?

| Gap | Proposed source | Why |
|---|---|---|
| German company accounts | **Bundesanzeiger** (bundesanzeiger.de) | German companies must publish their annual accounts here. Best public source for German suppliers' finances. |
| **IRIS certificates** | IRIS certification body pages, or certificates on the supplier's own site | The rail quality standard. Check whether a public certificate lookup exists. |
| German rail safety | **Eisenbahn-Bundesamt** (eba.bund.de) | German federal railway authority |
| US rail safety | **Federal Railroad Administration** (railroads.dot.gov) | US rail safety enforcement |
| EU product recalls | **EU Safety Gate** (on ec.europa.eu, already covered) | Add a recall-specific search slot |
| Human rights | **Business & Human Rights Resource Centre** (business-humanrights.org) | Tracks allegations and company responses |
| Labour data | **ILO** (ilo.org) | Country-level labour rights context |
| Cyber incidents | National cyber agencies (e.g. BSI in Germany, bsi.bund.de) | Official advisories; avoid leak sites |
| Other countries' registers | France (Infogreffe, BODACC), Italy, Spain, India (MCA) | Needed when researching non-German suppliers |
| Credit ratings | S&P, Moody's, Fitch press releases | Only free press releases; the full ratings are paid |

**Known weak spots today:**
- **Reputation** has only one search, so it is often "Not assessed".
- **People & Safety** relies on news; free official data at company level is rare.
- **Non-European companies** have few official registers on the list yet.

---

## 6. How to split the work (parallel workstreams)

Each workstream can run in its own thread and touches mostly separate files:

| # | Workstream | Main files | Done when |
|---|---|---|---|
| A | **First live run and tuning**: run on 3 known rail suppliers, review results | `config/settings.yaml`, `prompts/` | Reports look right for all 3 |
| B | **Source coverage**: check the 🟡 sources above, add the good ones | `config/sources.yaml` | Each new domain returns real, dated pages |
| C | **Search slots**: add slots for the gaps (recalls, IRIS, Bundesanzeiger) | `config/settings.yaml` | Every risk area is assessed in most runs |
| D | **Rulebook review**: check colours and look-back years with the team | `config/rules.yaml` | Team agrees on every rule |
| E | **Chatbot connection**: Deep Research button calls `run_research(...)`, shows progress and the clarification question | the chatbot code (outside this folder) | Button works end to end |
| F | **Reality check**: test on companies with known trouble vs. stable companies | `tests/`, a small results note | Troubled companies get 🔴, stable ones don't |
