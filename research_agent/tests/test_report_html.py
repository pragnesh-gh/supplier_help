import json
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from research_agent.models import (
    UMBRELLAS,
    AreaScore,
    AreaStatus,
    ClarificationRequest,
    ConfirmedEntity,
    Flag,
    Followup,
    ResearchResult,
    RunStats,
    ScoreCard,
    Source,
)
from research_agent.report_html import (
    AREA_LABELS,
    excerpt_around,
    locate_quote,
    render_html,
    safe_url,
    text_fragment_url,
    write_report_html,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
WEIGHTS = {"operations": 0.3, "financial": 0.16, "people": 0.15, "legal": 0.13, "country": 0.13, "reputation": 0.13}
HOSTILE = '<script>alert("x")</script><img src=x onerror=alert(1)>'


def _src(i, trust="trusted", tier="major_news", title=None, url=None):
    return Source(id=f"S{i}", url=url or f"https://www.reuters.com/a{i}", title=title or f"Title {i}",
                  publisher="Reuters", tier=tier, trust=trust, published_date="2026-03-0" + str(i % 9 + 1),
                  retrieved_at="2026-10-18T09:00:00+00:00", found_by="legal-1", umbrella="legal")


def _flag(i, colour, area="legal", src=1, summary=None, quote=None, date="2026-03-11", trust="trusted"):
    return Flag(id=f"F{i}", colour=colour, area=area, event_type="regulatory_fine", severity="high",
                claim_status="confirmed", summary=summary or f"Summary {i} of a {colour} item.",
                quote=quote or f"quoted words for fact {i}", event_date=date, source_ids=[f"S{src}"], trust=trust)


def _areas(assessed=("financial", "legal", "operations")):
    out = []
    for a in UMBRELLAS:
        used = 1 if a in assessed else 0
        out.append(AreaStatus(area=a, label=AREA_LABELS[a], status="amber" if used else "not_assessed",
                              finding=f"Finding for {a}." if used else "Not assessed — no evidence.",
                              trusted_pages_used=used, pages_checked=1))
    return out


def _scores(values, weights=WEIGHTS, total=None, level=None, method="not scored yet"):
    """values: area -> (score or None, coverage)."""
    areas = [AreaScore(area=a, score=values.get(a, (None, "not_assessed"))[0],
                       level=_lvl(values.get(a, (None, "not_assessed"))[0]),
                       coverage=values.get(a, (None, "not_assessed"))[1], trusted_pages=1) for a in UMBRELLAS]
    return ScoreCard(areas=areas, total=total, total_level=level, weights=weights, total_method=method)


def _lvl(v):
    if v is None:
        return None
    return "Low" if v < 25 else "Medium" if v < 50 else "High" if v < 75 else "Critical"


def _result(scores=None, flags=None, sources=None, **kw):
    sources = sources or [_src(1), _src(2), _src(3, trust="unverified", tier="open_web", url="https://blog.example/x")]
    flags = flags if flags is not None else [
        _flag(1, "red", src=1), _flag(2, "amber", area="operations", src=2, date="2025-08"),
        _flag(3, "amber", area="people", src=3, trust="unverified", date="2026-04"),
        _flag(4, "green", area="financial", src=2, date="2025"),
    ]
    base = dict(status="ok", company_input="Acme Rail", researched_at="2026-10-18T10:00:00+00:00",
                entity=ConfirmedEntity(legal_name="Acme Rail GmbH", country_code="DE", country_name="Germany",
                                       website="acme-rail.example"),
                verdict="Red flags — review before shortlisting", summary="One red flag was found.",
                flags=flags, areas=_areas(),
                scores=scores or _scores({a: (None, "assessed") for a in ("financial", "legal", "operations")}),
                next_steps=["Request a written legal statement."], limits=["Automated public-source research."],
                sources=sources, stats=RunStats(pages_read=3, trusted_pages_read=2, unverified_pages_read=1))
    base.update(kw)
    return ResearchResult(**base)


FULL: dict[str, tuple[int | None, str]] = {"financial": (20, "assessed"), "legal": (60, "assessed"), "country": (10, "assessed"),
        "people": (30, "assessed"), "operations": (40, "assessed"), "reputation": (80, "assessed")}


def _vertices(html):
    return {m.group(1): m.group(2) for m in re.finditer(r'class="vertex[^"]*" data-axis="(\w+)" data-value="(\w+)"', html)}


def test_render_is_deterministic_and_input_form_independent():
    r = _result(scores=_scores(FULL, total=37, level="Medium"))
    a, b = render_html(r), render_html(r)
    assert a == b
    assert render_html(json.loads(r.model_dump_json())) == a


def test_sample_fixture_renders_twice_identically(tmp_path):
    sample = EXAMPLES / "sample_result.json"
    one = render_html(sample)
    assert one == render_html(sample)
    out = write_report_html(sample, tmp_path)
    assert out.name == "report.html" and out.read_text(encoding="utf-8") == one


def test_hostile_text_is_escaped():
    src = _src(1, title=HOSTILE, url="javascript:alert(1)")
    src.publisher = HOSTILE
    r = _result(sources=[src], flags=[_flag(1, "red", src=1, summary=HOSTILE, quote=HOSTILE)],
                company_input=HOSTILE, verdict=HOSTILE, summary=HOSTILE, next_steps=[HOSTILE], limits=[HOSTILE])
    r.entity = ConfirmedEntity(legal_name=HOSTILE, website=HOSTILE)
    html = render_html(r)
    assert "<script>alert" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert 'href="javascript:' not in html
    assert safe_url("javascript:alert(1)") is None and safe_url("https://a.example/x") == "https://a.example/x"


def test_not_assessed_axes_are_never_plotted_as_zero():
    vals = dict(FULL)
    vals["reputation"] = (0, "not_assessed")  # hostile input: a score on an area without evidence
    vals["country"] = (None, "assessed")
    html = render_html(_result(scores=_scores(vals, total=30, level="Medium")))
    v = _vertices(html)
    assert v["reputation"] == "none" and v["country"] == "none"
    assert v["financial"] == "20"
    assert 'class="profile"' not in html  # no closed polygon when an axis is missing
    assert 'class="vertex na" data-axis="reputation"' in html
    # nothing is drawn at the centre (a 0 score would sit at 220,138)
    assert 'cx="220.0" cy="138.0"' not in html


def test_full_scores_draw_polygon_and_total():
    html = render_html(_result(scores=_scores(FULL, total=37, level="Medium")))
    assert 'class="profile"' in html
    assert set(_vertices(html).values()) == {"20", "60", "10", "30", "40", "80"}
    assert '<div class="n">37<small> /100</small></div>' in html
    assert "Coverage 100%" in html


def test_no_score_path_shows_placeholder():
    unscored = {a: (None, "assessed") for a in ("financial", "legal", "operations")}
    html = render_html(_result(scores=_scores(unscored)))
    assert "Not scored yet" in html
    assert set(_vertices(html).values()) == {"none"}
    assert "not scored yet" in html
    assert "Evidence coverage 59%" in html  # financial .16 + legal .13 + operations .30


def test_total_not_shown_and_range_from_method_line():
    method = ("total not shown: coverage 40 % is below the 50 % minimum (appendix §A5); possible range 12-72")
    vals = {"financial": (30, "assessed"), "legal": (50, "assessed")}
    html = render_html(_result(scores=_scores(vals, total=None, method=method)))
    assert "No total: too little assessed" in html
    assert "Coverage 40%" in html
    assert "12–72" in html


def test_unverified_marker_and_trust_labels():
    html = render_html(_result())
    assert "🟨" in html
    assert "not in our trusted source list" in html
    assert "✅ trusted" in html
    assert "unverified source only" in html


def test_citation_popover_shows_quote_in_context_and_deep_link():
    quote = "fined EUR 4.2 million for price-fixing"
    page = "Bonn, 11 March 2026. The authority said Acme Rail was fined EUR 4.2 million for price-fixing in brakes."
    r = _result(flags=[_flag(1, "red", src=1, quote=quote)], sources=[_src(1)])
    html = render_html(r, page_texts={"S1": page})
    assert "<mark>was fined EUR 4.2 million for price-fixing</mark>" not in html  # only the quote is marked
    assert "<mark>fined EUR 4.2 million for price-fixing</mark>" in html
    assert "Open source at this passage" in html
    assert "#:~:text=fined%20EUR%204.2%20million%20for%20price%2Dfixing" in html
    # print: the quote is also in the Sources list
    sources_part = html[html.index("<h3>Sources</h3>"):]
    assert f"“{quote}”" in sources_part


def test_quote_context_from_raw_result_json():
    r = _result(flags=[_flag(1, "red", src=1, quote="fined EUR 4.2 million")], sources=[_src(1)])
    raw = json.loads(r.model_dump_json())
    raw["flags"][0]["quote_context"] = "Earlier text. Acme was fined EUR 4.2 million last week."
    html = render_html(raw)
    assert "Acme was <mark>fined EUR 4.2 million</mark> last week." in html


def test_locate_quote_and_excerpt_offsets():
    text = ("x " * 300) + "The Company, said: “Profit fell 20%”… and more. " + ("y " * 300)
    span = locate_quote("company said profit fell 20%", text)
    assert span is not None
    ex, qs, qe = excerpt_around(text, *span)
    assert ex[qs:qe] == "Company, said: “Profit fell 20"
    assert ex.startswith("… ") and ex.endswith(" …")
    assert len(ex) < 500
    assert locate_quote("not on the page at all", text) is None
    assert locate_quote("Company said ... and more", text) is not None


def test_text_fragment_url_encoding():
    short = text_fragment_url("https://a.example/p?q=1#top", "co-op, A&B fine")
    assert short == "https://a.example/p?q=1#:~:text=co%2Dop%2C%20A%26B%20fine"
    long = text_fragment_url("https://a.example/p", "one two three four five six seven eight nine ten-x, eleven")
    frag = long.split("#:~:text=")[1]
    start, end = frag.split(",")
    assert unquote(start) == "one two three four" and unquote(end) == "eight nine ten-x, eleven"
    assert "-" not in frag and "&" not in frag
    assert text_fragment_url("javascript:alert(1)", "x y") == "javascript:alert(1)"  # never turned into a link


def test_area_labels_match_dataset_umbrellas():
    yaml = pytest.importorskip("yaml")
    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "scoring.yaml").read_text())
    assert {a: cfg["areas"][a]["dataset_umbrella"] for a in UMBRELLAS} == AREA_LABELS


def test_special_pages_and_wording():
    clar = _result(status="needs_clarification", clarification=ClarificationRequest(
        question="Which Acme do you mean?", candidates=[ConfirmedEntity(legal_name="Acme A"), ConfirmedEntity(legal_name="Acme B")]))
    html = render_html(clar)
    assert "We need one detail" in html and "Acme B" in html and "<svg" not in html
    err = render_html(_result(status="error", warnings=["TAVILY_API_KEY missing"]))
    assert "Research failed" in err and "TAVILY_API_KEY missing" in err
    ok = render_html(_result(flags=[]))
    assert "no risk" not in ok.lower()
    assert "No red flags or watch items found in the sources checked." in ok


def test_context_area_status_and_followups_render():
    r = _result(followups=[Followup(id="followup-1", flag_id="F1", flag_summary="s", question="Was it appealed?",
                                    query="q", corroborating_source_ids=["S2"], outcome="Confirmed by a second source.")])
    r.areas[0].status = "context"
    html = render_html(r)
    assert "Context only" in html and "Was it appealed?" in html


def test_timeline_plots_dated_flags_only():
    flags = [_flag(1, "red", date="2026-03-11"), _flag(2, "amber", area="operations", date=None),
             _flag(3, "neutral", area="country", date="2026")]
    html = render_html(_result(flags=flags, sources=[_src(1)]))
    assert html.count('class="ev ev-') == 1
    assert "1 finding without a date not shown." in html
