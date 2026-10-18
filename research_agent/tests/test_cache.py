"""Same-day cache: a rerun with the same requests gives the same answers without new calls."""

from datetime import date

from research_agent.cache import CachingLLM, CachingSearch, DayCache
from research_agent.config import load_all
from research_agent.fakes import FakeLLM, FakeSearch, load_fixture
from research_agent.models import SummaryOutput
from research_agent.orchestrator import run_research
from research_agent.search import SearchRequest


def test_search_and_extract_cached(tmp_path):
    fx = load_fixture()
    inner = FakeSearch(fx)
    c = CachingSearch(inner, DayCache(tmp_path, "2026-10-18"))
    req = SearchRequest(query="Veltrava recall", include_domains=["railway-technology.com"])
    a = c.search(req)
    b = c.search(req)
    assert a == b and len(inner.requests) == 1
    url = a[0].url
    c.extract([url])
    c.extract([url])
    assert inner.extracted == [url]


def test_failed_extract_not_cached(tmp_path):
    inner = FakeSearch(load_fixture())
    c = CachingSearch(inner, DayCache(tmp_path, "d"))
    c.extract(["https://nowhere.example/x"])
    c.extract(["https://nowhere.example/x"])
    assert inner.extracted.count("https://nowhere.example/x") == 2


def test_llm_cached_and_keyed_by_input(tmp_path):
    inner = FakeLLM(load_fixture())
    c = CachingLLM(inner, DayCache(tmp_path, "d"))
    a = c.structured(role="verifier", system="s", user="u1", schema=SummaryOutput)
    b = c.structured(role="verifier", system="s", user="u1", schema=SummaryOutput)
    c.structured(role="verifier", system="s", user="u2", schema=SummaryOutput)
    assert a == b and len(inner.calls) == 2


def test_rerun_same_day_is_identical_and_makes_no_calls(tmp_path):
    fx = load_fixture()
    cfg, day = load_all(), date(2026, 10, 18)
    r1 = run_research("Veltrava", "DE", "veltrava-rail.example", llm=FakeLLM(fx), search=FakeSearch(fx),
                      cache=DayCache(tmp_path, "2026-10-18"), config=cfg, today=day)
    llm2, search2 = FakeLLM(fx), FakeSearch(fx)
    r2 = run_research("Veltrava", "DE", "veltrava-rail.example", llm=llm2, search=search2,
                      cache=DayCache(tmp_path, "2026-10-18"), config=cfg, today=day)
    assert llm2.calls == [] and search2.requests == [] and search2.extracted == []
    assert [(f.event_type, f.colour, f.summary) for f in r1.flags] == [(f.event_type, f.colour, f.summary) for f in r2.flags]
    assert r2.stats.cache_hits > 0 and r2.fingerprint["cache_day"] == "2026-10-18"
