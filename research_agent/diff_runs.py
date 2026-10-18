"""Compare two research runs (result.json files).

    python -m research_agent.diff_runs OLD/result.json NEW/result.json

Shows: verdict, fingerprint differences (config hash, models, cache day, queries), facts
gained and lost, colour changes, risk-area changes, and sources gained and lost. Facts are
matched by area, event type and month, because the same event is often found through
different pages in different runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .dates import month_key

FactKey = tuple[str, str, str]


def _fact_key(f: dict[str, Any]) -> FactKey:
    return (str(f.get("area")), str(f.get("event_type")), month_key(f.get("event_date")) or "no date")


def _queries(r: dict[str, Any]) -> dict[str, str]:
    fp = r.get("fingerprint") or {}
    if fp.get("queries"):
        return {q["id"]: q["query"] for q in fp["queries"] if q.get("status") != "skipped"}
    return {p["id"]: p["query"] for p in r.get("plan", []) if p.get("status") != "skipped"}


def diff_results(old: dict[str, Any], new: dict[str, Any]) -> str:
    L: list[str] = []
    L.append(f"Verdict: {old.get('verdict')!r} -> {new.get('verdict')!r}" if old.get("verdict") != new.get("verdict")
             else f"Verdict unchanged: {new.get('verdict')!r}")

    fo, fn = old.get("fingerprint") or {}, new.get("fingerprint") or {}
    for k in ("config_hash", "models", "effort", "cache_day", "country_data"):
        if fo.get(k) != fn.get(k):
            L.append(f"Fingerprint {k}: {fo.get(k, 'n/a')} -> {fn.get(k, 'n/a')}")
    qo, qn = _queries(old), _queries(new)
    q_changed = [i for i in sorted(set(qo) | set(qn)) if qo.get(i) != qn.get(i)]
    L.append(f"Queries: {len(qo)} -> {len(qn)}, {len(q_changed)} different")
    for i in q_changed:
        L.append(f"  {i}: {qo.get(i, '(none)')!r} -> {qn.get(i, '(none)')!r}")

    def facts(r: dict[str, Any]) -> dict[FactKey, dict[str, Any]]:
        out: dict[FactKey, dict[str, Any]] = {}
        for f in r.get("flags", []):
            out.setdefault(_fact_key(f), f)
        return out

    a, b = facts(old), facts(new)
    lost = [a[k] for k in a if k not in b]
    gained = [b[k] for k in b if k not in a]
    changed = [(a[k], b[k]) for k in a if k in b and a[k].get("colour") != b[k].get("colour")]
    L.append(f"Facts: {len(a)} -> {len(b)}; {len(gained)} gained, {len(lost)} lost, {len(changed)} colour changes")
    for f in gained:
        L.append(f"  + [{f.get('colour')}] {f.get('area')}/{f.get('event_type')} {f.get('event_date') or ''}: {f.get('summary')}")
    for f in lost:
        L.append(f"  - [{f.get('colour')}] {f.get('area')}/{f.get('event_type')} {f.get('event_date') or ''}: {f.get('summary')}")
    for x, y in changed:
        L.append(f"  ~ {x.get('area')}/{x.get('event_type')} {x.get('event_date') or ''}: {x.get('colour')} -> {y.get('colour')}")

    ao = {x["area"]: x for x in old.get("areas", [])}
    an = {x["area"]: x for x in new.get("areas", [])}
    area_lines = []
    for area in an:
        x, y = ao.get(area, {}), an[area]
        if x.get("status") != y.get("status"):
            area_lines.append(f"  {y.get('label', area)}: {x.get('status', 'n/a')} -> {y.get('status')} "
                              f"({y.get('finding', '')[:90]})")
    L.append(f"Areas changed: {len(area_lines)}")
    L += area_lines

    so = {s["url"] for s in old.get("sources", [])}
    sn = {s["url"] for s in new.get("sources", [])}
    L.append(f"Sources: {len(so)} -> {len(sn)}; {len(sn - so)} new, {len(so - sn)} gone, {len(so & sn)} in both")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: python -m research_agent.diff_runs OLD/result.json NEW/result.json", file=sys.stderr)
        return 2
    old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args)
    print(diff_results(old, new))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
