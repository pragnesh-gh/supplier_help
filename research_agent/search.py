"""Search/fetch layer. All web retrieval goes through Tavily; we never fetch URLs ourselves.

Verified against docs.tavily.com on 2026-10-18:
  POST https://api.tavily.com/search   Authorization: Bearer <key>
    query, topic (general|news|finance), search_depth (basic|advanced|fast|ultra-fast),
    max_results (0-20), start_date/end_date (YYYY-MM-DD), time_range (day..year),
    include_domains (max 300), include_domains_mode (restrict|prefer; default restrict)
    -> results[]: title, url, content, score, published_date (auto for topic=news or
       include_published_date=true), raw_content (opt.)
  POST https://api.tavily.com/extract
    urls (1-20), query (reranks chunks), chunks_per_source (1-5), extract_depth (basic|advanced),
    format (markdown|text), timeout (1-60 s)
    -> results[]: url, raw_content ; failed_results[]: url, error
Note: there is no 'days' parameter in the current spec; we use start_date for look-back.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx2


class SearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchRequest:
    query: str
    include_domains: list[str]
    topic: Literal["general", "news"] = "general"
    start_date: str | None = None
    max_results: int = 8


@dataclass
class SearchHit:
    url: str
    title: str
    content: str
    score: float = 0.0
    published_date: str | None = None


@dataclass
class ExtractResponse:
    pages: dict[str, str] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)


class SearchClient(Protocol):
    def search(self, request: SearchRequest) -> list[SearchHit]: ...

    def extract(self, urls: list[str], query: str | None = None) -> ExtractResponse: ...


class TavilyClient:
    """Minimal Tavily REST client (httpx2). Keys are sent only in the Authorization header."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.tavily.com",
        search_depth: str = "advanced",
        extract_depth: str = "basic",
        timeout_s: float = 30.0,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        key = api_key or os.environ.get("TAVILY_API_KEY")
        if not key:
            raise SearchError("TAVILY_API_KEY is not set")
        self._client = httpx2.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=timeout_s,
            transport=transport,
        )
        self._search_depth = search_depth
        self._extract_depth = extract_depth
        self._timeout_s = timeout_s

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post(path, json=body)
        except httpx2.TimeoutException:
            raise SearchError(f"Tavily {path} timed out") from None
        except httpx2.RequestError as exc:
            raise SearchError(f"Tavily {path} network error: {type(exc).__name__}") from None
        if resp.status_code != 200:
            raise SearchError(f"Tavily {path} returned HTTP {resp.status_code}")
        data = resp.json()
        if not isinstance(data, dict):
            raise SearchError(f"Tavily {path} returned unexpected JSON")
        return data

    def search(self, request: SearchRequest) -> list[SearchHit]:
        if not request.include_domains:
            return []  # never search the open web
        body: dict[str, Any] = {
            "query": request.query[:400],
            "topic": request.topic,
            "search_depth": self._search_depth,
            "max_results": max(1, min(request.max_results, 20)),
            "include_domains": request.include_domains[:300],
            "include_domains_mode": "restrict",
            "include_published_date": True,
            "include_answer": False,
            "include_raw_content": False,
        }
        if request.start_date:
            body["start_date"] = request.start_date
        data = self._post("/search", body)
        hits: list[SearchHit] = []
        for r in data.get("results") or []:
            if not isinstance(r, dict) or not r.get("url"):
                continue
            hits.append(
                SearchHit(
                    url=str(r["url"]),
                    title=str(r.get("title") or ""),
                    content=str(r.get("content") or ""),
                    score=float(r.get("score") or 0.0),
                    published_date=(str(r["published_date"]) if r.get("published_date") else None),
                )
            )
        return hits

    def extract(self, urls: list[str], query: str | None = None) -> ExtractResponse:
        out = ExtractResponse()
        for start in range(0, len(urls), 20):
            batch = urls[start : start + 20]
            body: dict[str, Any] = {
                "urls": batch,
                "extract_depth": self._extract_depth,
                "format": "text",
                "timeout": min(60.0, max(1.0, self._timeout_s)),
            }
            if query:
                body["query"] = query[:400]
                body["chunks_per_source"] = 5
            data = self._post("/extract", body)
            for r in data.get("results") or []:
                if isinstance(r, dict) and r.get("url"):
                    out.pages[str(r["url"])] = str(r.get("raw_content") or "")
            for r in data.get("failed_results") or []:
                if isinstance(r, dict) and r.get("url"):
                    out.failed[str(r["url"])] = str(r.get("error") or "failed")
        return out
