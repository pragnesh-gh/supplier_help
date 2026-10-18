"""End-to-end pipeline tests with fake Tavily + fake LLM (no network, no keys)."""

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


def test_non_allowlisted_results_are_dropped(fx):
    r = _run(fx)
    assert all("random-blog.example" not in s.url for s in r.sources)
    assert r.stats.results_dropped_not_allowlisted >= 1


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
    assert r.flags == []
    assert r.stats.llm_errors > 0
    assert "No red flags" in r.verdict or "Not enough evidence" in r.verdict
    assert any(x.reason == "Verifier unavailable" for x in r.rejected)


def test_no_evidence_result(fx):
    fx2 = dict(fx)
    fx2["documents"] = [d for d in fx["documents"] if "gleif" in d["url"] or "railwaygazette" in d["url"]]
    r = _run(fx2, llm=FakeLLM(fx2), search=FakeSearch(fx2))
    assert r.status == "ok"
    assert r.flags == []
    assert all(a.status == "not_assessed" for a in r.areas)
    assert r.verdict.startswith("Not enough evidence")
    assert "no risk" not in render_markdown(r).lower()


def test_report_from_run_is_short_and_complete(fx):
    r = _run(fx)
    md = render_markdown(r)
    assert report_word_count(md) <= 600
    for h in ("Red flags", "Watch items", "Strengths", "Risk areas", "What we dug into", "Limits of this report",
              "Recommended next steps", "Sources"):
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
    lists = md.split("## Risk areas", 1)[0].split("**Verdict:", 1)[1]
    listed = [f for f in r.flags if f.colour != "neutral"]
    assert len([f for f in listed if f.colour == "amber"]) <= 5  # fixture is under every cap
    for f in listed:
        assert f.summary in lists, f"{f.id} {f.summary!r} missing from lists"
    for a in r.areas:
        for fid in a.flag_ids[:1]:
            f = next(x for x in r.flags if x.id == fid)
            if f.colour != "neutral":
                assert f.summary in lists
    assert "result.json" not in md and "(s)" not in md
    assert report_word_count(md) <= 600


def test_followup_and_limits_text_pluralised(fx):
    r = _run(fx)
    text = " ".join([fu.outcome for fu in r.followups] + r.limits + [r.summary])
    assert "(s)" not in text
    assert "Confirmed by a second source" in r.followups[0].outcome or "more sources" in r.followups[0].outcome
    assert "1 results" not in text
