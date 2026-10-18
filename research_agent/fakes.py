"""Offline fakes for Tavily and the LLM, driven by a JSON fixture.

Used by the tests and by ``python -m research_agent.cli --fixture`` to produce the
example report without network access or API keys. Nothing here is real research.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from .config import domain_of
from .llm import LLMError, Role
from .models import (
    CandidateFactOut,
    ExtractOutput,
    FactVerdict,
    FollowupOutput,
    FollowupPick,
    IdentityCandidate,
    IdentityOutput,
    NumberOut,
    PlanOutput,
    PlannedQuery,
    ProfileItemOut,
    ProfileVerdict,
    SummaryOutput,
    VerifyOutput,
)
from .search import ExtractResponse, SearchHit, SearchRequest

FIXTURE_DIR = Path(__file__).parent / "tests" / "fixtures"
# Grading signals the fake verifier returns when a fixture verdict does not set them.
DEFAULT_SIGNALS: dict[str, Any] = {"publisher_named": True, "dated": True, "claim_specific_checkable": True,
                                   "cites_primary_document": False, "attribution": "named_source"}
T = TypeVar("T", bound=BaseModel)

_URL_RE = re.compile(r'<untrusted_source id="([^"]+)" url="([^"]+)"')
_FACT_ID_RE = re.compile(r'"fact_id":\s*"([^"]+)"')
_ITEM_RE = re.compile(r'"item_id":\s*"([^"]+)",\s*"key":\s*"([^"]+)"')
_FLAG_LINE_RE = re.compile(r"^- id=(\S+) colour=(\S+)", re.MULTILINE)
_SLOT_RE = re.compile(r"^- slot_id=(\S+) .*?draft=(.*)$", re.MULTILINE)


def load_fixture(name: str = "veltrava.json") -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


class FakeSearch:
    """Returns fixture documents whose keywords hit the query and whose domain is in include_domains
    (trusted search) or not in exclude_domains (open-web search), like Tavily would.
    ``ignore_domain_filter`` docs come back regardless, to test the code-side filters."""

    def __init__(self, fixture: dict[str, Any], delay_s: float = 0.0) -> None:
        self.docs: list[dict[str, Any]] = fixture["documents"]
        self.delay_s = delay_s
        self.requests: list[SearchRequest] = []
        self.extracted: list[str] = []
        self._lock = threading.Lock()

    def search(self, request: SearchRequest) -> list[SearchHit]:
        with self._lock:
            self.requests.append(request)
        if self.delay_s:
            time.sleep(self.delay_s)
        allowed = set(request.include_domains)
        excluded = set(request.exclude_domains)
        q = request.query.lower()
        hits: list[SearchHit] = []
        for d in self.docs:
            host = domain_of(d["url"])
            if request.open_web:
                ok = not any(host == a or host.endswith("." + a) for a in excluded)
            else:
                ok = any(host == a or host.endswith("." + a) for a in allowed)
            if not ok and not d.get("ignore_domain_filter"):
                continue
            if not any(k.lower() in q for k in d.get("keywords", [])):
                continue
            hits.append(
                SearchHit(url=d["url"], title=d["title"], content=d["raw_content"][:300],
                          score=float(d.get("score", 0.5)), published_date=d.get("published_date"))
            )
        return hits

    def extract(self, urls: list[str], query: str | None = None) -> ExtractResponse:
        out = ExtractResponse()
        by_url = {d["url"]: d for d in self.docs}
        with self._lock:
            self.extracted.extend(urls)
        for u in urls:
            if u in by_url and not by_url[u].get("extract_fails"):
                out.pages[u] = by_url[u]["raw_content"]
            else:
                out.failed[u] = "fixture: not extractable"
        return out


class FakeLLM:
    """Scripted model. Answers come from the fixture, keyed by URL and claim.

    It is deliberately naive: on the injection page it 'obeys' the injected text and
    returns a fabricated fact, so tests can show the deterministic checks stop it.
    """

    def __init__(self, fixture: dict[str, Any], fail_roles: set[str] | None = None) -> None:
        self.fx = fixture
        self.calls: list[tuple[str, str, str, str]] = []  # (role, schema, system, user)
        self.fail_roles = fail_roles or set()
        self._lock = threading.Lock()
        self._docs = {d["url"]: d for d in fixture["documents"]}

    def model_name(self, role: Role) -> str:
        return f"fake-{role}"

    def structured(self, *, role: Role, system: str, user: str, schema: type[T]) -> T:
        with self._lock:
            self.calls.append((role, schema.__name__, system, user))
        if schema.__name__ in self.fail_roles or role in self.fail_roles:
            raise LLMError("fake failure")
        out: BaseModel
        if schema is IdentityOutput:
            out = self._identity(user)
        elif schema is PlanOutput:
            out = PlanOutput(queries=[PlannedQuery(slot_id=s, query=q.strip()) for s, q in _SLOT_RE.findall(user)])
        elif schema is ExtractOutput:
            out = self._extract(user)
        elif schema is VerifyOutput:
            out = self._verify(user)
        elif schema is FollowupOutput:
            out = self._followup(user)
        elif schema is SummaryOutput:
            out = SummaryOutput(summary=self.fx.get("summary_text", "Summary of verified findings."))
        else:  # pragma: no cover
            raise LLMError(f"fake has no answer for {schema.__name__}")
        return cast(T, out)

    # -- roles -----------------------------------------------------------
    def _identity(self, user: str) -> IdentityOutput:
        ids = dict((u, sid) for sid, u in _URL_RE.findall(user))
        cands = []
        for c in self.fx.get("identity_candidates", []):
            src = [ids[u] for u in c.get("urls", []) if u in ids]
            if not src:
                continue
            cands.append(
                IdentityCandidate(legal_name=c["legal_name"], country_code=c["country_code"],
                                  country_name=c["country_name"], website=c["website"],
                                  description=c["description"], evidence_source_ids=src)
            )
        return IdentityOutput(candidates=cands)

    def _extract(self, user: str) -> ExtractOutput:
        m = _URL_RE.search(user)
        doc = self._docs.get(m.group(2)) if m else None
        if not doc:
            return ExtractOutput(facts=[])
        facts = [CandidateFactOut(claim=f["claim"], quote=f["quote"], entity_named=f["entity_named"],
                                  event_date=f.get("event_date", "")) for f in doc.get("facts", [])]
        numbers = [NumberOut(**n) for n in doc.get("numbers", [])]
        profile = [ProfileItemOut(key=p["key"], value=p["value"], quote=p["quote"]) for p in doc.get("profile", [])]
        return ExtractOutput(facts=facts, numbers=numbers, profile=profile)

    def _verify(self, user: str) -> VerifyOutput:
        m = _URL_RE.search(user)
        doc = self._docs.get(m.group(2)) if m else None
        verdicts = []
        fact_ids = _FACT_ID_RE.findall(user)
        claims = re.findall(r'"claim":\s*"((?:[^"\\]|\\.)*)"', user)
        for fid, claim in zip(fact_ids, claims, strict=False):
            spec = None
            for f in (doc or {}).get("facts", []):
                if json.dumps(f["claim"])[1:-1] == claim:
                    spec = f.get("verdict")
            if spec is None:
                verdicts.append(FactVerdict(fact_id=fid, supported=False, entity_match="unclear", relevant=False,
                                            event_type="other_neutral", severity="low", claim_status="unclear",
                                            event_date="", summary="", reject_reason="not verifiable",
                                            **DEFAULT_SIGNALS))
            else:
                verdicts.append(FactVerdict(fact_id=fid, **{**DEFAULT_SIGNALS, **spec}))
        contradicts = bool((doc or {}).get("contradicts")) and "Claim under check" in user
        specs = {p["key"]: p.get("verdict", {}) for p in (doc or {}).get("profile", [])}
        profile = [ProfileVerdict(item_id=pid, **{"supported": True, "entity_match": "exact", **specs.get(key, {})})
                   for pid, key in _ITEM_RE.findall(user)]
        return VerifyOutput(verdicts=verdicts, contradicts_claim_under_check=contradicts, profile_verdicts=profile)

    def _followup(self, user: str) -> FollowupOutput:
        picks = []
        plan = self.fx.get("followup_queries", {})
        for fid, colour in _FLAG_LINE_RE.findall(user):
            line = next(ln for ln in user.splitlines() if ln.startswith(f"- id={fid} "))
            for key, spec in plan.items():
                if key in line:
                    picks.append(FollowupPick(flag_id=fid, question=spec["question"], query=spec["query"],
                                              query_local=spec.get("query_local", spec["query"])))
                    break
        return FollowupOutput(picks=picks)
