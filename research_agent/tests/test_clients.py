"""Live-path client tests without network: Tavily via httpx2.MockTransport, Anthropic via a stub module."""

import json
import sys
import types
from typing import Any

import httpx2
import pytest

from research_agent.llm import AnthropicLLM, LLMError
from research_agent.models import SummaryOutput
from research_agent.search import SearchError, SearchRequest, TavilyClient


def _tavily(handler):
    return TavilyClient(api_key="tvly-test-secret", transport=httpx2.MockTransport(handler))


def test_search_sends_restricted_allowlist_and_date():
    seen: dict[str, Any] = {}

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen["path"] = req.url.path
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json={"results": [
            {"title": "T", "url": "https://www.reuters.com/x", "content": "c", "score": 0.7, "published_date": "2026-01-02"}]})

    hits = _tavily(handler).search(SearchRequest(query="Veltrava fine", include_domains=["reuters.com"],
                                                 topic="news", start_date="2023-10-18", max_results=8))
    assert seen["path"] == "/search"
    assert seen["auth"] == "Bearer tvly-test-secret"
    b = seen["body"]
    assert b["include_domains"] == ["reuters.com"] and b["include_domains_mode"] == "restrict"
    assert b["topic"] == "news" and b["start_date"] == "2023-10-18" and b["max_results"] == 8
    assert "days" not in b
    assert hits[0].published_date == "2026-01-02"


def test_search_without_domains_never_calls_open_web():
    def handler(req):  # pragma: no cover - must not be called
        raise AssertionError("open-web search attempted")

    assert _tavily(handler).search(SearchRequest(query="x", include_domains=[])) == []


def test_open_web_search_sends_no_include_domains_but_excludes_denylist():
    seen: dict[str, Any] = {}

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json={"results": []})

    _tavily(handler).search(SearchRequest(query="Veltrava scandal", include_domains=[], open_web=True,
                                          exclude_domains=["reddit.com", "x.com"]))
    b = seen["body"]
    assert "include_domains" not in b and "include_domains_mode" not in b  # mode without domains is a 400
    assert b["exclude_domains"] == ["reddit.com", "x.com"]


def test_extract_splits_results_and_failures():
    def handler(req):
        body = json.loads(req.content)
        assert req.url.path == "/extract" and body["urls"] == ["https://a", "https://b"]
        return httpx2.Response(200, json={"results": [{"url": "https://a", "raw_content": "text"}],
                                           "failed_results": [{"url": "https://b", "error": "blocked"}]})

    out = _tavily(handler).extract(["https://a", "https://b"])
    assert out.pages == {"https://a": "text"} and out.failed == {"https://b": "blocked"}


def test_http_error_does_not_leak_key():
    def handler(req):
        return httpx2.Response(401, json={"detail": "bad key"})

    with pytest.raises(SearchError) as e:
        _tavily(handler).search(SearchRequest(query="x", include_domains=["reuters.com"]))
    assert "tvly-test-secret" not in str(e.value)


def test_missing_tavily_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(SearchError):
        TavilyClient()


# --- Anthropic adapter with a stub SDK ------------------------------------------------


class _StubAPIError(Exception):
    message = "boom"


def _install_stub(monkeypatch, parse_impl):
    calls = []

    class Messages:
        def parse(self, **kwargs):
            calls.append(kwargs)
            return parse_impl(**kwargs)

    class Anthropic:
        def __init__(self, api_key, timeout, max_retries):
            self.messages = Messages()

    mod = types.ModuleType("anthropic")
    setattr(mod, "Anthropic", Anthropic)
    setattr(mod, "APIError", _StubAPIError)
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    return calls


def test_anthropic_adapter_uses_parse_with_pydantic_output_format(monkeypatch):
    def ok(**kw):
        return types.SimpleNamespace(stop_reason="end_turn", parsed_output=SummaryOutput(summary="Hi."))

    calls = _install_stub(monkeypatch, ok)
    llm = AnthropicLLM("claude-haiku-5-5", "claude-opus-5-5", api_key="sk-test")
    out = llm.structured(role="verifier", system="sys", user="u", schema=SummaryOutput)
    assert out.summary == "Hi."
    assert calls[0]["model"] == "claude-opus-5-5"
    assert calls[0]["output_format"] is SummaryOutput
    assert calls[0]["system"] == "sys"
    assert calls[0]["messages"] == [{"role": "user", "content": "u"}]
    assert "output_config" not in calls[0]  # no effort configured -> nothing sent
    assert "thinking" not in calls[0]


def test_anthropic_adapter_sends_effort_per_role(monkeypatch):
    calls = _install_stub(monkeypatch, lambda **kw: types.SimpleNamespace(
        stop_reason="end_turn", parsed_output=SummaryOutput(summary="Hi.")))
    llm = AnthropicLLM("claude-sonnet-5-5", "claude-opus-5-5", api_key="sk-test",
                       gatherer_effort="medium", verifier_effort="high")
    llm.structured(role="gatherer", system="s", user="u", schema=SummaryOutput)
    llm.structured(role="verifier", system="s", user="u", schema=SummaryOutput)
    assert calls[0]["model"] == "claude-sonnet-5-5" and calls[0]["output_config"] == {"effort": "medium"}
    assert calls[1]["model"] == "claude-opus-5-5" and calls[1]["output_config"] == {"effort": "high"}
    assert calls[0]["output_format"] is SummaryOutput


def test_parse_merges_effort_with_schema_in_real_sdk():
    """Real anthropic SDK over a mock transport: one output_config with both effort and format."""
    anthropic = pytest.importorskip("anthropic")
    seen: dict[str, Any] = {}

    def handler(req: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(req.content)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": [{"type": "text", "text": '{"summary": "Hi."}'}], "stop_reason": "end_turn",
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})

    client = anthropic.Anthropic(api_key="sk-test", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    out = client.messages.parse(model="claude-sonnet-5-5", max_tokens=100, messages=[{"role": "user", "content": "u"}],
                                output_format=SummaryOutput, output_config={"effort": "medium"})
    oc = seen["body"]["output_config"]
    assert oc["effort"] == "medium" and oc["format"]["type"] == "json_schema"
    assert out.parsed_output == SummaryOutput(summary="Hi.")


def test_anthropic_adapter_errors_become_llmerror(monkeypatch):
    def fail(**kw):
        raise _StubAPIError()

    _install_stub(monkeypatch, fail)
    llm = AnthropicLLM("g", "v", api_key="sk-secret")
    with pytest.raises(LLMError) as e:
        llm.structured(role="gatherer", system="s", user="u", schema=SummaryOutput)
    assert "sk-secret" not in str(e.value)


def test_anthropic_adapter_refusal(monkeypatch):
    _install_stub(monkeypatch, lambda **kw: types.SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(LLMError):
        AnthropicLLM("g", "v", api_key="k").structured(role="gatherer", system="s", user="u", schema=SummaryOutput)
