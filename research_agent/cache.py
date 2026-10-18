"""Same-day cache for search, extract and model calls, keyed by the exact request.

Why: Tavily results and model answers change from run to run (these models accept no
temperature setting), so two runs on the same company differed in which facts they found.
With the cache, a rerun on the same day gets identical inputs and costs nothing. A new day
starts fresh, so news is never more than a day old.

Works with any SearchClient and any LLM adapter (Claude now, e.g. Nemotron later). Failures
are never cached. Files: <dir>/<YYYY-MM-DD>/<kind>/<sha256>.json
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .llm import LLM, Role
from .search import ExtractResponse, SearchClient, SearchHit, SearchRequest

T = TypeVar("T", bound=BaseModel)


class DayCache:
    def __init__(self, root: Path, day: str) -> None:
        self.dir = root / day
        self.hits = 0
        self._lock = threading.Lock()

    @staticmethod
    def key(payload: Any) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def get(self, kind: str, key: str) -> Any | None:
        path = self.dir / kind / f"{key}.json"
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        with self._lock:
            self.hits += 1
        return value

    def put(self, kind: str, key: str, value: Any) -> None:
        folder = self.dir / kind
        folder.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False)
        os.replace(tmp, folder / f"{key}.json")  # atomic: parallel workers never read half a file


class CachingSearch:
    """SearchClient wrapper. Extract is cached per URL, so a page read once is reused."""

    def __init__(self, inner: SearchClient, cache: DayCache) -> None:
        self.inner = inner
        self.cache = cache

    def search(self, request: SearchRequest) -> list[SearchHit]:
        k = self.cache.key(asdict(request))
        cached = self.cache.get("search", k)
        if cached is not None:
            return [SearchHit(**h) for h in cached]
        hits = self.inner.search(request)
        self.cache.put("search", k, [asdict(h) for h in hits])
        return hits

    def extract(self, urls: list[str], query: str | None = None) -> ExtractResponse:
        out = ExtractResponse()
        missing: list[str] = []
        for u in urls:
            cached = self.cache.get("extract", self.cache.key({"url": u, "query": query}))
            if cached is not None:
                out.pages[u] = str(cached)
            else:
                missing.append(u)
        if missing:
            fresh = self.inner.extract(missing, query)
            for u, text in fresh.pages.items():
                self.cache.put("extract", self.cache.key({"url": u, "query": query}), text)
            out.pages.update(fresh.pages)
            out.failed.update(fresh.failed)  # failures are not cached: retried next run
        return out


class CachingLLM:
    """LLM wrapper: the same role, model, settings, prompt and input give the cached answer."""

    def __init__(self, inner: LLM, cache: DayCache, settings_key: str = "") -> None:
        self.inner = inner
        self.cache = cache
        self.settings_key = settings_key

    def model_name(self, role: Role) -> str:
        return self.inner.model_name(role)

    def structured(self, *, role: Role, system: str, user: str, schema: type[T]) -> T:
        k = self.cache.key({"role": role, "model": self.inner.model_name(role), "settings": self.settings_key,
                            "schema": schema.__name__, "system": system, "user": user})
        cached = self.cache.get("llm", k)
        if cached is not None:
            try:
                return schema.model_validate(cached)
            except ValueError:
                pass  # schema changed since; ask again
        out = self.inner.structured(role=role, system=system, user=user, schema=schema)
        self.cache.put("llm", k, out.model_dump(mode="json"))
        return out
