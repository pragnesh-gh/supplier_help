"""End-to-end pipeline tests with fake Tavily + fake LLM (no network, no keys)."""

import json
from datetime import date

import pytest

from research_agent.config import load_all
from research_agent.fakes import FakeLLM, FakeSearch, load_fixture
from research_agent.models import ProgressEvent
from research_agent.orchestrator import run_research
from research_agent.report import render_markdown, report_word_count

TODAY = date(2026, 10, 18)


@pytest.fixture
def fx():
    return load_fixture()


def _run(fx, *, company="Veltrava", country="DE", website="veltrava-rail.example", llm=None, search=None, cfg=None,
         clock=None, events=None):
    return run_research(company, country, website, on_progress=(events.append if events is not None else None),
                        llm=llm or FakeLLM(fx), search=search or FakeSearch(fx), config=cfg or load_all(),
                        today=TODAY, clock=clock)


def test_full_run_ok_with_expected_flags(fx):
    events: list[ProgressEvent] = []
    r = _run(fx, events=events)
    assert r.status == "ok", r.warnings
    assert r.entity.legal_name == "Veltrava Rail Components GmbH"
    reds = [f for f in r.flags if f.colour == "red"]
    ambers = [f for f in r.flags if f.colour == "amber"]
    greens = [f for f in r.flags if f.colour == "green"]
    assert [f.event_type for f in reds] == ["regulatory_fine"]
    assert {f.event_type for f in ambers} >= {"profit_warning", "strike_or_labour_dispute", "product_recall"}
    assert {f.event_type for f in greens} >= {"iris_certified", "credit_upgrade_or_strong_results"}
    assert r.verdict == "Red flags — review before shortlisting"


def test_every_flag_has_full_citation_data(fx):
    r = _run(fx)
    by_id = {s.id: s for s in r.sources}
    for f in r.flags:
        assert f.summary and f.quote and len(f.quote.split()) <= 26
        assert f.source_ids
        for sid in f.source_ids:
            s = by_id[sid]
            assert s.url.startswith("https://") and s.title and s.publisher and s.retrieved_at


def test_old_fatal_accident_is_downgraded_by_rules_not_model(fx):
    r = _run(fx)
    acc = next(f for f in r.flags if f.event_type == "safety_accident")
    assert acc.colour == "amber" and acc.stale
    assert "older than 3 years" in acc.rule_note


def test_namesake_rejected(fx):
    r = _run(fx)
    assert not any("Foods" in f.summary for f in r.flags)
    assert any("Different company" in x.reason for x in r.rejected)
    assert r.stats.rejected_namesake_or_unclear_entity >= 1


def test_prompt_injection_page_cannot_change_outcome(fx):
    llm = FakeLLM(fx)
    search = FakeSearch(fx)
    r = _run(fx, llm=llm, search=search)
    # The naive fake gatherer 'obeyed' the injection and invented a fact; the quote check dropped it.
    assert any(x.reason == "Quote not found in source text" and "cleared of all charges" in x.claim for x in r.rejected)
    assert not any("cleared" in f.summary.lower() or "risk-free" in f.summary.lower() for f in r.flags)
    # Verdict, budget and sources unchanged by the page.
    assert r.verdict.startswith("Red flags")
    assert r.stats.searches_used <= load_all().settings.budget.max_searches
    assert all("trusted-partner.example" not in d for req in search.requests for d in req.include_domains)
    # The page reached the model only inside the untrusted delimiter, with exactly one closing tag.
    inj_calls = [u for (_, _, _, u) in llm.calls if "admin mode" in u]
    assert inj_calls
    for u in inj_calls:
        assert u.count("</untrusted_source>") == 1
        assert u.index("Ignore all previous instructions") < u.index("</untrusted_source>")
    # System prompts always carry the data-not-instructions notice.
    assert all("never instructions" in system for (_, _, system, _) in llm.calls)


def test_non_allowlisted_results_are_dropped_from_trusted_searches(fx):
    r = _run(fx)
    trusted_pass = next(p for p in r.plan if p.id == "reputation-1")
    assert trusted_pass.results_dropped_not_allowlisted >= 1  # the blog leaked into a trusted search
    assert r.stats.results_dropped_not_allowlisted >= 1
    # The blog is used only via the open-web pass, and then labelled unverified.
    blog = [s for s in r.sources if "random-blog.example" in s.url]
    assert len(blog) == 1 and blog[0].found_by == "reputation-web"


def test_unverified_source_kept_and_labelled(fx):
    r = _run(fx)
    blog = next(s for s in r.sources if "random-blog.example" in s.url)
    assert blog.trust == "unverified" and blog.tier == "open_web" and blog.publisher == "random-blog.example"
    assert all(s.trust == "trusted" for s in r.sources if s is not blog)
    assert r.stats.unverified_pages_read == 1 and r.stats.trusted_pages_read == r.stats.pages_read - 1
    web = [p for p in r.plan if p.open_web]
    assert web and all(p.tiers == [] for p in web)
    assert len(web) <= load_all().settings.open_web.max_searches


def test_open_web_runs_after_trusted_and_only_for_gaps(fx):
    search = FakeSearch(fx)
    r = _run(fx, search=search)
    kinds = [req.open_web for req in search.requests]
    first_web = kinds.index(True)
    assert not any(kinds[:first_web]) and first_web >= 8  # identity + all 8 trusted searches first
    web_areas = [p.umbrella for p in r.plan if p.open_web]
    assert web_areas == ["reputation", "operations"]  # no trusted page first, then biggest shortfall; never country
    open_reqs = [req for req in search.requests if req.open_web]
    assert all(req.include_domains == [] and "reddit.com" in req.exclude_domains for req in open_reqs)


def test_denylisted_source_dropped(fx):
    r = _run(fx)
    assert all("reddit.com" not in s.url for s in r.sources)
    assert r.stats.results_dropped_denylisted >= 1
    assert not any(f.event_type == "insolvency_filing" for f in r.flags)
    assert not r.verdict.startswith("Knock-out")


def test_unverified_only_fact_is_capped_and_marked(fx):
    r = _run(fx)
    f = next(f for f in r.flags if f.event_type == "fraud_or_corruption_case")
    assert f.trust == "unverified" and f.capped_unverified
    assert f.colour == "amber" and not f.knockout
    assert "unverified source only: red → amber" in f.rule_note
    assert r.verdict == "Red flags — review before shortlisting"  # driven by the trusted fine, not the blog


def _with_unverified_sanctions(fx):
    fx2 = json.loads(json.dumps(fx))
    fx2["documents"].append({
        "url": "https://sanctions-watch.example/veltrava", "title": "Veltrava on sanctions list?",
        "published_date": "2026-09-01", "keywords": ["recall defect"], "score": 0.9,  # found by the operations open-web search
        "raw_content": "Sanctions Watch reports that Veltrava Rail Components was added to a sanctions list in September 2026.",
        "facts": [{"claim": "Veltrava Rail Components was added to a sanctions list in September 2026.",
                   "quote": "Veltrava Rail Components was added to a sanctions list in September 2026",
                   "entity_named": "Veltrava Rail Components", "event_date": "2026-09",
                   "verdict": {"supported": True, "entity_match": "exact", "relevant": True,
                               "event_type": "sanctions_listing", "severity": "high", "claim_status": "confirmed",
                               "event_date": "2026-09", "summary": "Reported added to a sanctions list in September 2026.",
                               "reject_reason": ""}}]})
    return fx2


def test_unverified_only_fact_cannot_knock_out(fx):
    fx2 = _with_unverified_sanctions(fx)
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    f = next(f for f in r.flags if f.event_type == "sanctions_listing")
    assert f.trust == "unverified" and f.colour == "amber" and not f.knockout
    assert not r.verdict.startswith("Knock-out")


def test_unverified_fact_upgraded_when_trusted_source_confirms(fx):
    fx2 = _with_unverified_sanctions(fx)
    fx2["followup_queries"] = {"sanctions list": {"question": "Is the listing on an official list?",
                                                  "query": "Veltrava Rail Components sanctions listing official"}}
    fx2["documents"].append({
        "url": "https://www.opensanctions.org/fixture/veltrava", "title": "Veltrava Rail Components GmbH — OpenSanctions",
        "published_date": "2026-09-03", "keywords": ["sanctions listing official"], "score": 0.9,
        "raw_content": "Entity: Veltrava Rail Components GmbH. Listed on the EU sanctions list on 2026-09-02.",
        "facts": [{"claim": "Veltrava Rail Components GmbH was listed on the EU sanctions list on 2026-09-02.",
                   "quote": "Veltrava Rail Components GmbH. Listed on the EU sanctions list on 2026-09-02",
                   "entity_named": "Veltrava Rail Components GmbH", "event_date": "2026-09-02",
                   "verdict": {"supported": True, "entity_match": "exact", "relevant": True,
                               "event_type": "sanctions_listing", "severity": "high", "claim_status": "confirmed",
                               "event_date": "2026-09-02", "summary": "Listed on the EU sanctions list (2 Sep 2026).",
                               "reject_reason": "", "attribution": "firsthand_official", "cites_primary_document": True}}]})
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    f = next(f for f in r.flags if f.event_type == "sanctions_listing")
    assert f.trust == "trusted" and f.colour == "red" and f.knockout and not f.capped_unverified
    assert r.sources[[s.id for s in r.sources].index(f.source_ids[0])].trust == "trusted"  # trusted source cited first
    assert f.signals.attribution == "firsthand_official"  # signals follow the trusted primary source
    assert f.signals.corroborated_by_trusted and f.signals.independent_domains == 2
    assert r.verdict.startswith("Knock-out")
    fu = next(x for x in r.followups if x.flag_id == f.id)
    assert fu.outcome.startswith("Re-rated from watch item to red flag.")


def test_grading_signals_recorded(fx):
    r = _run(fx)
    blog = next(f for f in r.flags if f.event_type == "fraud_or_corruption_case")
    assert blog.signals.attribution == "anonymous_or_rumour" and blog.signals.publisher_named is False
    assert blog.signals.corroborated_by_trusted is False and blog.signals.independent_domains == 1
    fine = next(f for f in r.flags if f.event_type == "regulatory_fine")
    assert fine.signals.independent_domains == 2 and fine.signals.corroborated_by_trusted


def test_syndicated_copies_count_once(fx):
    fx2 = json.loads(json.dumps(fx))
    orig = next(d for d in fx2["documents"] if "railway-technology.com" in d["url"])
    copy = json.loads(json.dumps(orig))
    copy["url"] = "https://www.globalrailwayreview.com/fixture/veltrava-recall-copy"
    copy["raw_content"] = "Global Railway Review | News\n" + orig["raw_content"]  # same story, extra header
    copy["score"] = 0.1
    fx2["documents"].append(copy)
    cfg = load_all()
    cfg.settings.budget.max_extracts = 20  # room for the extra copy
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2), cfg=cfg)
    recall = next(f for f in r.flags if f.event_type == "product_recall")
    assert len(recall.source_ids) == 2  # both pages cited ...
    assert recall.signals.independent_domains == 1  # ... but they are one story
    assert recall.signals.corroborated_by_trusted is False


def test_official_tier_searched_before_news_for_legal(fx):
    r = _run(fx)
    legal = [p for p in r.plan if p.umbrella == "legal" and not p.id.startswith("followup")]
    assert legal[0].tiers == ["official"]
    assert legal[1].tiers == ["major_news"]


def test_red_flag_triggers_followup_that_finds_more(fx):
    events: list[ProgressEvent] = []
    r = _run(fx, events=events)
    assert 1 <= len(r.followups) <= 2
    fu = r.followups[0]
    fine = next(f for f in r.flags if f.event_type == "regulatory_fine")
    assert fu.flag_id == fine.id
    assert fu.pages_checked >= 1
    assert fu.corroborating_source_ids, "appeal article should corroborate the fine"
    assert len(fine.source_ids) >= 2
    assert fu.new_flag_ids, "appeal pending should be a new watch item"
    assert any(e.kind == "followup" and "Digging deeper" in e.message for e in events)
    assert any(f.found_in_followup for f in r.flags)


def test_progress_events_show_plan_and_steps(fx):
    events: list[ProgressEvent] = []
    _run(fx, events=events)
    kinds = [e.kind for e in events]
    for k in ("identity", "plan", "search", "extract", "verify", "followup", "report", "done"):
        assert k in kinds, k
    plan = next(e for e in events if e.kind == "plan")
    assert len(plan.data["steps"]) >= 6
    assert kinds.index("plan") < kinds.index("extract")


def test_ambiguous_name_needs_clarification(fx):
    llm = FakeLLM(fx)
    r = _run(fx, country=None, website=None, llm=llm)
    assert r.status == "needs_clarification"
    assert r.clarification is not None and len(r.clarification.candidates) == 2
    assert r.flags == [] and r.entity is None
    assert not any(schema == "ExtractOutput" for (_, schema, _, _) in llm.calls), "no research before identity is clear"
    md = render_markdown(r)
    assert "Veltrava Holdings Pty Ltd" in md


def test_clarified_by_country_continues(fx):
    r = _run(fx, country="Germany", website=None)
    assert r.status == "ok" and r.entity.country_code == "DE"


def test_budget_caps_respected(fx):
    search = FakeSearch(fx)
    r = _run(fx, search=search)
    b = load_all().settings.budget
    assert r.stats.searches_used <= b.max_searches
    assert r.stats.extracts_used <= b.max_extracts
    assert len(search.extracted) <= b.max_extracts
    assert len(r.followups) <= b.max_followups


def test_small_extract_budget(fx):
    cfg = load_all()
    cfg.settings.budget.max_extracts = 5
    cfg.settings.budget.extracts_reserved_for_followups = 1
    search = FakeSearch(fx)
    r = _run(fx, cfg=cfg, search=search)
    assert len(search.extracted) <= 5
    assert r.status == "ok"


def test_timeout_returns_partial(fx):
    t = {"now": 0.0}

    def clock():
        t["now"] += 7.0  # every clock read advances 7 s → budget of 120 s runs out mid-run
        return t["now"]

    r = _run(fx, clock=clock)
    assert r.status == "partial"
    assert any("Time limit" in w for w in r.warnings)
    md = render_markdown(r)
    assert "Partial result" in md
    assert r.areas, "partial results still produce a risk-area table"


def test_real_wall_clock_timeout(fx):
    cfg = load_all()
    cfg.settings.budget.wall_clock_seconds = 0.5
    import time
    start = time.monotonic()
    r = _run(fx, cfg=cfg, search=FakeSearch(fx, delay_s=2.0))
    assert time.monotonic() - start < 1.5
    assert r.status == "partial"


def test_verifier_failure_drops_facts_not_invents(fx):
    r = _run(fx, llm=FakeLLM(fx, fail_roles={"VerifyOutput"}))
    assert [f.event_type for f in r.flags] == ["country_risk_low"]  # only the code-read country data
    assert r.stats.llm_errors > 0
    assert "No red flags" in r.verdict or "Not enough evidence" in r.verdict
    assert any(x.reason == "Verifier unavailable" for x in r.rejected)


def test_no_evidence_result(fx):
    fx2 = dict(fx)
    fx2["documents"] = [d for d in fx["documents"] if "gleif" in d["url"] or "railwaygazette" in d["url"]]
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    assert r.status == "ok"
    assert [f.area for f in r.flags] == ["country"]  # the country figures come from data, not pages
    assert all(a.status == "not_assessed" for a in r.areas if a.area != "country")
    assert all(a.score is None and a.coverage == "not_assessed" for a in r.scores.areas if a.area != "country")
    assert r.verdict.startswith("Not enough evidence")
    assert "no risk" not in render_markdown(r).lower()


def test_report_from_run_is_short_and_complete(fx):
    r = _run(fx)
    md = render_markdown(r)
    assert report_word_count(md) > 0
    for h in ("Summary for decision makers", "Company-specific risks found", "Risk register",
              "From priority risks to prevention", "Follow-up checks", "Limits of this report", "Sources"):
        assert h in md
    assert "legal statement" in md  # rule-based next step for a legal red flag


def test_missing_keys_give_error_status(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    r = run_research("Veltrava", "DE")
    assert r.status == "error"
    assert r.warnings


def test_every_flag_in_table_or_summary_is_in_the_lists(fx):
    r = _run(fx)
    md = render_markdown(r)
    lists = md.split("## 4. Company-specific risks found", 1)[1].split("## 5. ", 1)[0]
    for f in r.flags:
        if f.area == "country" and f.data:
            continue  # country index figures are shown in section 3
        assert f.summary in lists, f"{f.id} {f.summary!r} missing from section 4"
    assert "not shown" not in lists.split("**Event timeline**")[0]  # nothing is trimmed


def test_followup_and_limits_text_pluralised(fx):
    r = _run(fx)
    text = " ".join([fu.outcome for fu in r.followups] + r.limits + [r.summary])
    assert "(s)" not in text
    assert "Confirmed by a second source" in r.followups[0].outcome or "more sources" in r.followups[0].outcome
    assert "1 results" not in text


# --- second live-run fixes ---------------------------------------------------------------


def test_source_dates_are_normalized(fx):
    r = _run(fx)
    hb = next(s for s in r.sources if "handelsblatt.com" in s.url)
    assert hb.published_date == "2026-07-14"  # fixture gives RFC 2822
    assert all(s.published_date is None or len(s.published_date) in (4, 7, 10) for s in r.sources)


def test_news_result_not_naming_the_company_is_not_read(fx):
    search = FakeSearch(fx)
    r = _run(fx, search=search)
    assert all("gerresheimer" not in s.url for s in r.sources)
    assert "https://www.reuters.com/fixture/gerresheimer-probe" not in search.extracted
    assert r.stats.results_dropped_off_topic >= 1


def test_country_data_is_a_structured_trusted_fact(fx):
    llm = FakeLLM(fx)
    r = _run(fx, llm=llm)
    f = next(x for x in r.flags if x.area == "country")
    assert f.event_type == "country_risk_low" and f.colour == "green" and f.trust == "trusted"
    inds = {d["indicator"]: d for d in f.data["figures"]}
    assert set(inds) == {"GOV_WGI_PV.SC", "GOV_WGI_CC.SC", "GOV_WGI_RL.SC", "CPI"}
    assert round(inds["GOV_WGI_PV.SC"]["value"], 1) == 69.3 and inds["GOV_WGI_PV.SC"]["year"] == 2025
    assert inds["CPI"]["value"] == 77 and inds["CPI"]["rank"] == 10
    srcs = [s for s in r.sources if s.id in f.source_ids]
    assert {s.text_origin for s in srcs} == {"data"} and all(s.tier == "country_data" for s in srcs)
    assert any(s.url.startswith("https://api.worldbank.org/v2/country/DE/indicator/") for s in srcs)
    # No model saw the country data.
    assert not any("api.worldbank.org" in u for (_, _, _, u) in llm.calls)
    country = next(a for a in r.areas if a.area == "country")
    assert country.status == "green" and country.trusted_pages_used == 2


def test_country_data_counts_one_extract(fx):
    search = FakeSearch(fx)
    _run(fx, search=search)
    assert sum(1 for u in search.extracted if "api.worldbank.org" in u) == 1


def test_pages_split_by_area_weight(fx):
    from research_agent.budget import split_by_weight
    from research_agent.config import load_scoring
    w: dict[str, float] = {a: m.weight for a, m in load_scoring().areas.items()}
    shares = split_by_weight(load_all().settings.budget.max_trusted_pages, w, ["financial", "legal", "country",
                                                                                "people", "operations", "reputation"])
    assert shares == {"financial": 2, "legal": 2, "country": 2, "people": 2, "operations": 4, "reputation": 2}
    r = _run(fx)
    b = load_all().settings.budget
    assert r.stats.extracts_used <= b.max_extracts and r.stats.searches_used <= b.max_searches
    ops_searches = [p for p in r.plan if p.umbrella == "operations" and not p.open_web and "-direct" not in p.id
                    and not p.id.startswith("followup")]
    assert len(ops_searches) == max(len(load_all().settings.umbrellas[u].searches) for u in w)  # most searches


def test_queries_are_short_and_bilingual(fx):
    r = _run(fx)
    area = [p for p in r.plan if p.umbrella and not p.id.startswith(("followup", "identity")) and not p.open_web
            and "-direct" not in p.id]
    assert {p.lang for p in area} == {"en", "local"}
    assert all(_extra_words(p.query) <= load_all().settings.max_query_extra_words for p in area)


def test_keyword_soup_rewrite_is_rejected(fx):
    class SoupLLM(FakeLLM):
        def structured(self, *, role, system, user, schema):
            from research_agent.models import PlanOutput, PlannedQuery
            if schema is PlanOutput:
                import re
                ids = re.findall(r"^- slot_id=(\S+)", user, re.MULTILINE)
                return PlanOutput(queries=[PlannedQuery(slot_id=i, query="Veltrava Rückruf Mängel Lieferverzögerung "
                                                       "Cyberangriff Werk Produktionsstopp IRIS Zertifizierung Streik")
                                           for i in ids])
            return super().structured(role=role, system=system, user=user, schema=schema)

    r = _run(fx, llm=SoupLLM(fx))
    ops = next(p for p in r.plan if p.id == "operations-1")
    assert ops.query == "Veltrava Rail Components GmbH recall defect quality"  # draft kept


def test_local_slots_skipped_for_english_speaking_country(fx):
    cfg = load_all()
    cfg.settings.english_speaking_countries = ["DE"]
    r = _run(fx, cfg=cfg)
    local = [p for p in r.plan if p.lang == "local"]
    assert local and all(p.status == "skipped" for p in local)
    assert not any(p.id.endswith("-local") for p in r.plan)  # follow-up also English only


def test_followup_searches_english_and_local(fx):
    r = _run(fx)
    fu = r.followups[0]
    assert fu.query_local == "Veltrava Rail Components Bußgeld Beschwerde"
    ids = [p.id for p in r.plan]
    assert "followup-1" in ids and "followup-1-local" in ids
    assert all(_extra_words(p.query) <= load_all().settings.max_query_extra_words
               for p in r.plan if p.id.startswith("followup"))


def _extra_words(q):
    return len([w for w in q.split() if w.lower() not in {"veltrava", "rail", "components", "gmbh"}])


def test_template_summary_leads_with_plain_verdict_and_gaps(fx):
    r = _run(fx, llm=FakeLLM(fx, fail_roles={"SummaryOutput"}))
    assert r.summary.startswith("A red flag was found.")
    assert "Not assessed, so nothing is known yet about: Reputation" in r.summary


def test_summary_saying_rated_as_is_replaced(fx):
    fx2 = dict(fx)
    fx2["summary_text"] = "Veltrava Rail Components GmbH is rated as red flags."
    r = _run(fx2, llm=FakeLLM(fx2))
    assert "rated as" not in r.summary and r.summary.startswith("A red flag was found.")


# --- third round: reproducibility, drop reasons, context ---------------------------------


def test_queries_come_from_templates_without_planner_for_known_language(fx):
    llm = FakeLLM(fx)
    r = _run(fx, llm=llm)
    assert not any(schema == "PlanOutput" for (_, schema, _, _) in llm.calls)  # DE translations are fixed
    q = {p.id: p.query for p in r.plan}
    assert q["legal-3"] == "Veltrava Rail Components GmbH Bußgeld Klage Korruption"
    assert q["legal-4"] == "Veltrava Rail Components GmbH lawsuit settlement court ruling"  # litigation history slot


def test_planner_only_translates_missing_languages(fx):
    cfg = load_all()
    cfg.settings.country_languages = {}
    llm = FakeLLM(fx)
    _run(fx, llm=llm, cfg=cfg)
    plan_calls = [u for (_, schema, _, u) in llm.calls if schema == "PlanOutput"]
    assert len(plan_calls) == 1 and "lang=local" in plan_calls[0] and "lang=en" not in plan_calls[0]


def test_same_inputs_same_plan_and_pages(fx):
    a, b = _run(fx), _run(fx)
    assert [(p.id, p.query) for p in a.plan] == [(p.id, p.query) for p in b.plan]
    assert [s.url for s in a.sources] == [s.url for s in b.sources]
    assert a.fingerprint["config_hash"] == b.fingerprint["config_hash"]
    assert {x["id"] for x in a.fingerprint["queries"]} >= {"legal-4", "operations-1"}


def test_drop_reasons_recorded_per_result(fx):
    r = _run(fx)
    reasons = r.stats.drop_reasons
    assert reasons.get("denylisted", 0) >= 1 and reasons.get("off_topic", 0) >= 1
    rep = next(p for p in r.plan if p.id == "reputation-1")
    assert {(d.url, d.reason) for d in rep.dropped} >= {
        ("https://www.reuters.com/fixture/gerresheimer-probe", "off_topic"),
        ("https://random-blog.example/veltrava-scandal", "not_allowlisted")}
    assert any(e.kind == "report" and "Results not read, by reason" in e.message for e in r.trail)
    assert sum(reasons.values()) == sum(len(p.dropped) for p in r.plan)


def test_open_web_excludes_trusted_and_denied_domains(fx):
    search = FakeSearch(fx)
    _run(fx, search=search)
    web = [q for q in search.requests if q.open_web]
    assert web and all("reuters.com" in q.exclude_domains and "reddit.com" in q.exclude_domains
                       and "veltrava-rail.example" in q.exclude_domains for q in web)


def test_name_filter_accepts_spacing_variants_and_url():
    from research_agent.models import ConfirmedEntity
    from research_agent.orchestrator import _mentions_company
    from research_agent.search import SearchHit
    kb = ConfirmedEntity(legal_name="Knorr-Bremse AG", website="knorr-bremse.com")
    for title, url in [("Knorr Bremse wins order", "https://x/a"), ("KnorrBremse profit", "https://x/b"),
                       ("Stiftung nimmt Arbeit auf", "https://www.handelsblatt.com/knorr-bremse-thiele-stiftung/1.html")]:
        assert _mentions_company(kb, SearchHit(url=url, title=title, content=""))
    assert not _mentions_company(kb, SearchHit(url="https://x/g", title="BaFin probes Gerresheimer", content="accounting"))


def test_financial_prefers_newest_pages(fx):
    fx2 = json.loads(json.dumps(fx))
    old = next(d for d in fx2["documents"] if "annual-report-2025" in d["url"])
    old2 = json.loads(json.dumps(old))
    old2["url"] = "https://veltrava-rail.example/investors/annual-report-2023"
    old2["published_date"], old2["score"], old2["facts"] = "2024-03-20", 0.99, []
    fx2["documents"].append(old2)
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    fin = [s for s in r.sources if s.umbrella == "financial" and "veltrava-rail.example" in s.url]
    assert fin and fin[0].url.endswith("annual-report-2025")  # newer first despite the lower score


def test_stale_legal_matter_shows_as_context_not_green(fx):
    fx2 = json.loads(json.dumps(fx))
    fx2["documents"].append({
        "url": "https://www.justice.gov/fixture/veltrava-consent", "title": "Final Judgment: U.S. v. Veltrava Rail Components",
        "published_date": "2018-07-11", "keywords": ["lawsuit settlement"], "score": 0.9,
        "raw_content": "The consent judgment bars Veltrava Rail Components from entering no-poach agreements.",
        "facts": [{"claim": "A 2018 US consent judgment bars Veltrava from no-poach agreements.",
                   "quote": "The consent judgment bars Veltrava Rail Components from entering no-poach agreements",
                   "entity_named": "Veltrava Rail Components", "event_date": "2018-07-11",
                   "verdict": {"supported": True, "entity_match": "exact", "relevant": True,
                               "event_type": "antitrust_settlement", "severity": "medium", "claim_status": "confirmed",
                               "event_date": "2018-07-11", "summary": "2018 US consent judgment bars no-poach agreements.",
                               "reject_reason": ""}}]})
    fx2["documents"] = [d for d in fx2["documents"] if not any(k in d["url"] for k in ("bundeskartellamt", "appeal", "random-blog"))]
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    f = next(x for x in r.flags if x.event_type == "antitrust_settlement")
    assert f.colour == "neutral" and f.stale
    legal = next(a for a in r.areas if a.area == "legal")
    assert legal.status == "context"
    md = render_markdown(r)
    head = next(ln for ln in md.splitlines() if ln.startswith("### ") and "Legal & Governance" in ln)
    assert "Context only" in head and "nothing adverse" not in head
    row = next(ln for ln in md.splitlines() if "2018 US consent judgment" in ln and ln.startswith("- "))
    assert "**Context:**" in row and "(2018-07-11)" in row and "older event" in row


def test_trusted_followup_contradicting_unverified_claim(fx):
    fx2 = _with_unverified_sanctions(fx)
    fx2["followup_queries"] = {"sanctions list": {"question": "Is the listing on an official list?",
                                                  "query": "Veltrava Rail Components sanctions listing official"}}
    fx2["documents"].append({
        "url": "https://www.opensanctions.org/fixture/veltrava-none", "title": "Veltrava Rail Components GmbH — OpenSanctions",
        "published_date": "2026-09-03", "keywords": ["sanctions listing official"], "score": 0.9,
        "raw_content": "Veltrava Rail Components GmbH is not on any sanctions list we track. Checked 2026-09-03.",
        "contradicts": True,
        "facts": [{"claim": "Veltrava Rail Components GmbH is not on any tracked sanctions list.",
                   "quote": "Veltrava Rail Components GmbH is not on any sanctions list we track",
                   "entity_named": "Veltrava Rail Components GmbH", "event_date": "2026-09-03",
                   "verdict": {"supported": True, "entity_match": "exact", "relevant": True,
                               "event_type": "other_neutral", "severity": "low", "claim_status": "confirmed",
                               "event_date": "2026-09-03", "summary": "Not on any tracked sanctions list.",
                               "reject_reason": ""}}]})
    llm = FakeLLM(fx2)
    r = _run(fx2, llm=llm, search=FakeSearch(fx2))
    f = next(x for x in r.flags if x.event_type == "sanctions_listing")
    assert f.signals.contradicted_by_trusted and f.colour == "neutral" and not f.knockout
    assert any("Claim under check" in u for (_, schema, _, u) in llm.calls if schema == "VerifyOutput")
    fu = next(x for x in r.followups if x.flag_id == f.id)
    assert fu.outcome.startswith("A trusted source states the opposite")


def test_scoring_detail_round_trips_to_explain_text(fx):
    from research_agent.scoring import ScoringReport, explain_text
    r = _run(fx)
    rep = ScoringReport.model_validate(r.scoring_detail)
    text = explain_text(rep)
    assert text.startswith("How was this scored?") and rep.as_of == TODAY.isoformat()
    assert r.scores.total == rep.total


def test_scoring_config_has_room_for_method():
    from research_agent.config import load_scoring
    assert load_scoring().method is None


def test_report_hooks_quote_context_and_score_coverage(fx):
    texts: dict[str, str] = {}
    r = run_research("Veltrava", "DE", "veltrava-rail.example", llm=FakeLLM(fx), search=FakeSearch(fx), config=load_all(),
                     today=TODAY, page_texts_out=texts)
    fine = next(f for f in r.flags if f.event_type == "regulatory_fine")
    assert fine.quote_context and "was fined EUR 4.2 million" in fine.quote_context
    assert r.scores.coverage is not None and 0 < r.scores.coverage <= 1
    assert r.scores.range_low is not None and r.scores.range_high is not None
    assert r.scores.range_low <= (r.scores.total or 0) <= r.scores.range_high
    assert set(texts) == {s.id for s in r.sources}
    from research_agent.models import ResearchResult
    again = ResearchResult.model_validate_json(r.model_dump_json())
    assert again.flags[0].quote_context == r.flags[0].quote_context


def test_area_labels_match_dataset_umbrellas(fx):
    from research_agent.config import load_scoring
    r = _run(fx)
    want = {a: m.dataset_umbrella for a, m in load_scoring().areas.items()}
    assert {a.area: a.label for a in r.areas} == want
    md = render_markdown(r)
    assert "| Operations & Delivery |" in md and "Operations & Quality" not in md


def test_cli_fixture_writes_html(tmp_path):
    from research_agent.__main__ import run_fixture
    run_fixture(tmp_path)
    assert (tmp_path / "report.md").exists() and (tmp_path / "result.json").exists()
    assert (tmp_path / "report.html").exists()


# -- company profile ----------------------------------------------------------------


def test_profile_is_quote_checked_and_sourced(fx):
    r = _run(fx)
    p = r.profile
    assert p["headquarters"].value == "Leipzig, Germany" and p["founded"].value == "1994"
    assert p["description"].value.startswith("Develops and builds brake systems")
    by_id = {s.id: s for s in r.sources}
    for key, pf in p.items():
        s = by_id[pf.source_ids[0]]
        assert s.trust == "trusted" and pf.quote, key
    # The parent-company value is not in its quote: dropped by code, never shown.
    assert "parent_company" not in p
    assert any(x.claim.startswith("Profile parent_company") for x in r.rejected)
    # One extra search at most, and profile-only pages add no risk facts.
    assert [x.id for x in r.plan if x.id.startswith("profile")] == ["profile-1"]
    prof_ids = {s.id for s in r.sources if s.found_by == "profile-1"}
    assert prof_ids and not any(set(f.source_ids) & prof_ids for f in r.flags)


def test_profile_search_skipped_when_pages_already_state_it(fx):
    fx2 = json.loads(json.dumps(fx))
    about = next(d for d in fx2["documents"] if d["url"].endswith("/company/about"))
    ar = next(d for d in fx2["documents"] if d["url"].endswith("annual-report-2025"))
    ar["raw_content"] += " " + about["raw_content"]
    ar["profile"] += about["profile"]
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    assert r.profile["founded"].value == "1994"
    assert not any(x.id.startswith("profile") for x in r.plan)


def test_profile_never_invented_and_verifier_can_reject(fx):
    fx2 = json.loads(json.dumps(fx))
    fx2["documents"] = [d for d in fx2["documents"] if not d["url"].endswith("/company/about")]
    ar = next(d for d in fx2["documents"] if d["url"].endswith("annual-report-2025"))
    ar["profile"][1]["verdict"] = {"supported": False, "entity_match": "exact"}
    ar["profile"].append({"key": "founded", "value": "1989", "quote": "Annual Report 2025."})
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    assert set(r.profile) == {"description"}  # products rejected by the verifier, 1989 not in its quote
