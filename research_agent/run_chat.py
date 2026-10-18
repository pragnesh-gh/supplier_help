"""Answer follow-up questions about one finished research run. Deterministic: no model call,
no new search. Answers only from what the report already holds (verified flags, scores,
coverage, next steps, limits), each claim with its citation number."""

from __future__ import annotations

import re
from typing import Any

STOPWORDS = {"what", "which", "where", "when", "does", "have", "this", "that", "about", "company", "supplier",
             "risk", "risks", "please", "tell", "research", "report", "they", "their", "there", "with", "from",
             "is", "are", "the", "any", "and", "for", "how", "why", "was", "were", "show", "give", "more"}
COLOUR_WORD = {"red": "Red flag", "amber": "Watch item", "green": "Strength", "neutral": "Context"}
NO_ANSWER = "This report does not answer that. No new search was run; start a new research run to look further."


def _marks(nums: list[int]) -> str:
    return "".join(f"[{n}]" for n in nums)


def _flag_line(f: dict[str, Any]) -> str:
    when = f" ({f['date']})" if f.get("date") else ""
    tags = []
    if f.get("claim_status") == "alleged":
        tags.append("alleged")
    if f.get("trust") == "unverified":
        tags.append("source not in our trusted list")
    tag = f" · {', '.join(tags)}" if tags else ""
    return f"• {COLOUR_WORD.get(f['colour'], 'Finding')} · {f['area_label']}{tag}: {f['summary']}{when} {_marks(f.get('citations', [])[:3])}".rstrip()


def _reply(answer: str, flags: list[dict[str, Any]], run: dict[str, Any]) -> dict[str, Any]:
    nums = {n for f in flags for n in f.get("citations", [])[:3]}
    cites = [c for c in run.get("citations", []) if c.get("n") in nums]
    return {"answer": answer, "finding_ids": [f["id"] for f in flags],
            "source_ids": list(dict.fromkeys(c["source_id"] for c in cites)), "citations": cites,
            "new_research": False}


def chat(run: dict[str, Any], message: Any) -> dict[str, Any]:
    if run.get("status") != "completed":
        raise ValueError("Wait for this research to finish before asking about it")
    question = message.strip() if isinstance(message, str) else ""
    if not question or len(question) > 2000:
        raise ValueError("Enter a question")
    if run.get("schema_version") != "research-run-v2" or "flags" not in run:
        return {"answer": "This is an older report. Open it to read the findings, or run the research again "
                          "to ask questions about it.", "finding_ids": [], "source_ids": [], "citations": [],
                "new_research": False}
    lower = question.casefold()
    flags: list[dict[str, Any]] = run.get("flags", [])
    scores = run.get("scores") or {}
    company = run.get("company", "this company")

    if re.search(r"\b(score|scored|rating|radar|points|weight|level)\b", lower):
        lines = []
        total = scores.get("total")
        lines.append(f"Public research score for {company}: "
                     + (f"{total}/100 · {scores.get('level')}" if total is not None else "no total score (too little evidence)")
                     + (f" · coverage {scores['coverage_pct']}%" if scores.get("coverage_pct") is not None else "") + ".")
        for a in scores.get("areas", []):
            value = f"{a['score']}/100 · {a['level']}" if a.get("score") is not None else "Not assessed"
            lines.append(f"• {a['label']}: {value}")
        lines.append("0 = no risk, 100 = maximum risk. This score is not comparable to the catalogue scores. "
                     "Open the report and choose “How was this scored?” for the per-fact breakdown.")
        return _reply("\n".join(lines), [], run)

    if re.search(r"\b(gap|gaps|missing|unknown|not assessed|still need|open questions?|coverage)\b", lower):
        na = [a["label"] for a in scores.get("areas", []) if a.get("coverage") == "not_assessed"]
        lines = [("Not assessed (no evidence found): " + ", ".join(na) + ".") if na else "All six areas have some evidence."]
        lines += [f"• {x}" for x in run.get("limitations", [])[:3]]
        if run.get("next_steps"):
            lines.append("Suggested next checks:")
            lines += [f"• {x}" for x in run["next_steps"][:4]]
        return _reply("\n".join(lines), [], run)

    if re.search(r"\b(entity|subsidiar\w*|parent|group|legal name|which company)\b", lower):
        ent = run.get("entity") or {}
        answer = (f"Researched entity: {ent.get('legal_name') or company}"
                  + (f" ({ent.get('country_name') or ent.get('country_code')})" if ent.get("country_name") or ent.get("country_code") else "")
                  + f". Identity {ent.get('verification', 'unverified')}. Findings about a parent or sister company "
                    "were only kept when the source named this entity.")
        return _reply(answer, [], run)

    if re.search(r"\b(summar\w*|overview|verdict|main|key|what do we know|tl;?dr|red flags?|concerns?|issues?)\b", lower):
        top = [f for f in flags if f["colour"] in ("red", "amber")][:4] or flags[:3]
        answer = f"{run.get('verdict') or 'Research complete'}.\n" + "\n".join(_flag_line(f) for f in top)
        return _reply(answer.strip(), top, run)

    if re.search(r"\b(strength\w*|positive|good|green)\b", lower):
        top = [f for f in flags if f["colour"] == "green"][:4]
        if not top:
            return _reply("No strengths were recorded from the sources checked.", [], run)
        return _reply("\n".join(_flag_line(f) for f in top), top, run)

    words = set(re.findall(r"[a-zà-ÿ0-9]{3,}", lower)) - STOPWORDS
    ranked = []
    for f in flags:
        hay = " ".join([f["summary"], f["area"], f["area_label"], f.get("event_type", "").replace("_", " ")]).casefold()
        score = sum(1 for w in words if w in hay)
        if score:
            ranked.append((score, f))
    ranked.sort(key=lambda p: -p[0])
    top = [f for _, f in ranked[:3]]
    if not top:
        return _reply(NO_ANSWER, [], run)
    return _reply("From this report (no new search):\n" + "\n".join(_flag_line(f) for f in top), top, run)
