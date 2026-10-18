# Research agent (first draft)

A bounded "deep research" agent for the Siemens supplier-risk challenge. A buyer names a real company; the agent confirms the legal entity, plans its research, searches trusted public sources, digs deeper on red flags, and returns a short risk report with source links.

**Status:** draft. All tests run offline on invented fixture data. **No live run has happened yet** (no API keys in the dev environment). See [examples/sample_report.md](examples/sample_report.md) for the report layout. It uses a fictional company.

**Start here:** [RESEARCH_MAP.md](RESEARCH_MAP.md) explains which sources are trusted, what is searched per risk area, the gaps, and how the work is split.

## Challenge requirements and where they are met

| Challenge asks | How the agent does it | Where you see it |
| --- | --- | --- |
| A buyer names a real company | `run_research(company, country, website)` resolves the legal entity from trusted sources. If several companies match, it returns `needs_clarification` with candidates and a question. | `result.entity`, `result.clarification` |
| Plans its research | Fixed plan: 6 risk areas, official sources first, then news. The small model only rewrites query wording. | `plan` progress event, `result.plan`, report header |
| Crawls news, public sources, company sites | Tavily search, restricted to an allowlist (registers, regulators, sanctions lists, business and rail press, the company's own site), plus Tavily extract for full page text. | `result.sources`, Sources section |
| Digs deeper on red flags | The verifier picks at most 2 red or watch items. A narrow follow-up search finds corroboration or new facts. | "What we dug into" section, `result.followups` |
| Risk report with source links | `report.md` (one page) and `result.json`. Every finding is numbered [n] and links to its source with publication and access dates. | `report.md` |

## Pipeline

```
company, country?, website?
        │
  1 Identity ── Tavily search (official + press) → gatherer lists candidate entities
        │        → code decides: one entity → ok │ several → needs_clarification (stop)
  2 Plan ────── 6 risk areas × config search templates (official first, then news)
        │        gatherer may rephrase queries; it cannot add sources, tiers or steps
  3 Search ──── Tavily /search, include_domains = allowlist tier, start_date = look-back
        │        results not on the allowlist are dropped; up to 3 pages per area
  4 Read ────── Tavily /extract (max 12 pages per run, 4 kept back for follow-ups)
  5 Extract ─── gatherer (Haiku) pulls candidate facts + exact quotes from each page
  6 Check ───── code: quote must appear in the page text, otherwise dropped
                verifier (Opus): supported? right entity (not a namesake)? relevant?
                → event_type + severity from fixed lists
  7 Rules ───── config/rules.yaml → red / amber / green / neutral, knock-outs, verdict
  8 Dig deeper ─ verifier picks ≤2 red/amber items → narrow search → steps 4–7 again
  9 Report ──── verifier writes 2–3 sentence summary from verified facts only
                code renders report.md from result.json (fixed template)
```

Budget (in `config/settings.yaml`): 12 searches, 12 page extracts, 2 follow-ups, 120 s wall clock. When time runs out, the run returns `status: "partial"` with what it has so far. Every network and model call is time-bounded.

## Running it

```sh
pip install --break-system-packages -r research_agent/requirements.txt
cp research_agent/.env.example research_agent/.env      # add ANTHROPIC_API_KEY, TAVILY_API_KEY

python -m research_agent --check                         # validates config and keys; no paid calls
python -m research_agent --fixture                       # offline demo on invented data
python -m research_agent "Knorr-Bremse" --country DE --website knorr-bremse.com
```

Output goes to `research_agent/output/<slug>-<date>/report.md` and `result.json`. The folder is git-ignored. Progress lines print to stderr.

The report always lists every red flag (up to 5), every watch item (up to 5) and every strength (up to 3). If a list would be longer, it says how many lower-priority items are not shown. If the report runs past about 600 words, the risk-area rows that repeat a listed flag are shortened to a pointer; the flag lists themselves are never cut. `report.md` never mentions `result.json`.

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

- `config/sources.yaml`: the trusted-source allowlist, grouped in tiers: official, company_own (filled at run time), major_news, rail_trade, country_data. To add a source, add one line: `domain: Publisher`. Pages from other sites are never used.
- `config/rules.yaml`: maps each event type to a colour and risk area. It also sets the staleness window, knock-outs, verdict wording and next-step wording.
- `config/settings.yaml`: model IDs, budget, look-back years, and the search templates for each risk area.
- `prompts/*.md`: model instructions as plain text.

## How flags are decided

1. The gatherer extracts a candidate fact with a quote of at most 25 words copied from the page.
2. Code checks that the quote is really in the text Tavily returned. Case, whitespace and minor punctuation are ignored. If the quote is missing, the fact is dropped.
3. The verifier checks the quote supports the claim, confirms the fact is about the confirmed entity or its group (not a namesake), and confirms it matters for supplier risk. Then it labels the fact with an `event_type` and `severity` from fixed lists.
4. `rules.yaml` decides the colour. Examples: `regulatory_fine` → red; `product_recall` → amber; `iris_certified` → green; low severity turns red into amber; events older than the staleness window step down one level.
5. A `sanctions_listing` or `insolvency_filing` → **"Knock-out risk found — do not proceed without escalation"**.
6. The verdict is text chosen by code: knock-out › red flags › watch items only › "No red flags found in the sources checked". If no trusted page was read, the verdict is "Not enough evidence". There are no numeric scores, and the report never says "no risk".

Facts from the company's own website are labelled *company-stated*.

## Safety of fetched content

Web pages are untrusted data. Each page is wrapped in an `<untrusted_source>` block that the page cannot close or forge. Every system prompt says that content is data, never instructions. Models can only return typed fields. They cannot choose URLs, sources, tools or budget. Retrieval only goes through allowlisted Tavily searches built from config. A test runs a prompt-injection page: the model's fake fact is dropped by the quote check, and the verdict, budget and sources stay the same.

## Deviations from the repo docs

- **Claude instead of Nemotron for this draft.** The repo docs name Nemotron via OpenRouter. The team chose Claude (Haiku 5.5 gatherer, Opus 5.5 verifier) for the research agent draft. `llm.py` is a small adapter interface, so an OpenRouter/Nemotron class can replace it later.
- **Rule-based colours.** `docs/research/company-fixture.md` asks for neutral tags and "no invented red/yellow/green company rating". The team decided on red/amber/green **flags per sourced fact**, set by a published rulebook, not by the model. There is still no company score. The other display rules are kept: source date separate from access date, "company-stated" label, "no issues found in sources checked" wording, and no mapping to `SUPP_*` IDs.
- **Budget:** 120 s wall clock, not the 90 s in the delivery plan, as agreed for this draft.

## Verified vs not verified (checked 2026-10-18)

- Verified on platform.claude.com: model IDs `claude-haiku-5-5` and `claude-opus-5-5`. Structured outputs via `client.messages.parse(output_format=<pydantic model>)`, which sends `output_config.format`; both models are listed as supported.
- Verified against the anthropic SDK 1.15.0 source: the adapter was smoke-tested against the real SDK over a mocked HTTP transport. The SDK now depends on `httpx2`.
- Verified on docs.tavily.com: `/search` parameters (`include_domains`, `include_domains_mode`, `topic`, `start_date`, `search_depth`, `max_results`, `include_published_date`) and `/extract` (`urls`, `extract_depth`, `format`, `timeout`). The current API has **no `days` parameter**, so the agent uses `start_date`.
- **Not verified:** real API calls (no keys), real model output quality, Tavily coverage for these domains, cost and latency. `anthropic` could not be pip-installed in the dev container (PyPI blocked), so live behaviour still needs a first real run.

## Known limitations

- Identity relies on what trusted sources say. Small private firms may need country and website from the buyer.
- `published_date` from Tavily can be missing or later than the original date. Event dates come from the page text when stated.
- Duplicate events are merged only when type and month match. Syndicated copies on different domains may still appear as separate sources.
- Sanctions lists are searched through Tavily, not through the official list APIs. A missing hit is not proof of "not sanctioned".
- Paywalled news (FT, WSJ, Bloomberg) may give only snippets. The agent then uses the search snippet, recorded as `text_origin: "search_snippet"`.
- The country area uses general country-risk pages. It is not a structured INFORM or CPI lookup.

## Next steps

1. Get keys, run `--check`, then do live runs on 3 real companies, including one ambiguous name and one small supplier. Check every cited quote by hand.
2. Tune the allowlist and query templates using observed Tavily results. Add direct OpenSanctions and GLEIF API lookups for identity and sanctions.
3. Add an evaluation set (namesakes, stale news, allegations vs confirmed facts) to measure verifier precision.
4. Wire `run_research` into the chatbot "deep research" button and stream `on_progress` events to the UI.
