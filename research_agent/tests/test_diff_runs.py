import json

from research_agent.diff_runs import diff_results, main


def _r(flags, areas=(), verdict="V", sources=()):
    return {"verdict": verdict, "flags": list(flags), "areas": list(areas), "sources": [{"url": u} for u in sources],
            "plan": [], "fingerprint": {"config_hash": "a", "queries": [{"id": "legal-1", "query": "q1", "status": "done"}]}}


def test_diff_finds_gained_lost_and_colour_changes(tmp_path):
    old = _r([{"area": "legal", "event_type": "major_lawsuit", "event_date": "2023", "colour": "amber", "summary": "Thiele"},
              {"area": "legal", "event_type": "regulatory_fine", "event_date": "2026-03-11", "colour": "red", "summary": "Fine"}],
             [{"area": "legal", "label": "Legal", "status": "amber", "finding": "x"}], "Watch items only", ["https://a"])
    new = _r([{"area": "legal", "event_type": "regulatory_fine", "event_date": "Wed, 11 Mar 2026 00:00:00 GMT",
               "colour": "amber", "summary": "Fine"}],
             [{"area": "legal", "label": "Legal", "status": "context", "finding": "y"}], "No red flags", ["https://a", "https://b"])
    new["fingerprint"]["config_hash"] = "b"
    out = diff_results(old, new)
    assert "Verdict: 'Watch items only' -> 'No red flags'" in out
    assert "config_hash: a -> b" in out
    assert "- [amber] legal/major_lawsuit 2023: Thiele" in out
    assert "~ legal/regulatory_fine 2026-03-11: red -> amber" in out  # matched across date formats
    assert "Legal: amber -> context" in out and "1 new, 0 gone" in out
    p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
    p1.write_text(json.dumps(old)), p2.write_text(json.dumps(new))
    assert main([str(p1), str(p2)]) == 0
