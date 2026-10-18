"""Command line for the team.

    python -m research_agent.cli "Knorr-Bremse" --country DE --website knorr-bremse.com
    python -m research_agent.cli --check            # validate config + keys, no paid calls
    python -m research_agent.cli --fixture          # offline demo on invented fixture data
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from .config import ConfigError, load_all, load_prompt
from .models import ProgressEvent, ResearchResult
from .report import render_markdown, report_word_count

PKG_DIR = Path(__file__).parent
FIXTURE_NOTICE = (
    "Example generated from invented fixture data. Veltrava Rail Components GmbH is fictional; "
    "nothing here describes a real company."
)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv(PKG_DIR / ".env")
    load_dotenv()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "company"


def write_outputs(result: ResearchResult, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "report.md"
    json_path = out_dir / "result.json"
    md_path.write_text(render_markdown(result), encoding="utf-8")
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return md_path, json_path


def _print_progress(ev: ProgressEvent) -> None:
    print(f"[{ev.elapsed_s:6.1f}s] {ev.kind:<9} {ev.message}", file=sys.stderr, flush=True)


def check() -> int:
    """Validate config files and report which keys are present. Makes no API calls."""
    ok = True
    try:
        cfg = load_all()
        for name in ("identity", "plan", "extract", "verify", "followup", "summary"):
            load_prompt(name)
        n_domains = sum(len(d) for d in cfg.allowlist.tiers.values())
        print(f"config: OK ({n_domains} allowlisted domains, {len(cfg.rules.event_types)} event rules, 6 risk areas)")
        print(f"models: gatherer={cfg.settings.models.gatherer} verifier={cfg.settings.models.verifier}")
        b = cfg.settings.budget
        print(f"budget: {b.max_searches} searches, {b.max_extracts} page extracts, "
              f"{b.max_followups} follow-ups, {b.wall_clock_seconds:.0f} s")
    except ConfigError as exc:
        print(f"config: ERROR {exc}")
        ok = False
    for key in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY"):
        print(f"{key}: {'set' if os.environ.get(key) else 'MISSING'}")  # never print the value
        ok = ok and bool(os.environ.get(key))
    try:
        import anthropic

        print(f"anthropic SDK: {anthropic.__version__}")
    except ImportError:
        print("anthropic SDK: MISSING (pip install -r research_agent/requirements.txt)")
        ok = False
    print("ready for live runs" if ok else "NOT ready for live runs (see above)")
    return 0 if ok else 1


def run_fixture(out_dir: Path) -> ResearchResult:
    from .fakes import FakeLLM, FakeSearch, load_fixture
    from .orchestrator import run_research

    fx = load_fixture()
    result = run_research(
        "Veltrava Rail Components", "DE", "veltrava-rail.example", on_progress=_print_progress,
        llm=FakeLLM(fx), search=FakeSearch(fx), today=date(2026, 10, 18),
    )
    result.notice = FIXTURE_NOTICE
    result.researched_at = "2026-10-18T09:00:00+00:00"
    for s in result.sources:
        s.retrieved_at = result.researched_at
    for ev in result.trail:
        ev.elapsed_s = 0.0
    result.stats.elapsed_s = 0.0
    write_outputs(result, out_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m research_agent.cli", description="Supplier deep-research agent (draft).")
    p.add_argument("company", nargs="?", help="Company name as the buyer typed it")
    p.add_argument("--country", help="Country code or name, e.g. DE or Germany")
    p.add_argument("--website", help="Official website, e.g. knorr-bremse.com")
    p.add_argument("--out", type=Path, help="Output folder (default research_agent/output/<slug>-<date>/)")
    p.add_argument("--check", action="store_true", help="Validate config and keys without calling paid APIs")
    p.add_argument("--fixture", action="store_true", help="Offline demo on invented fixture data (no keys needed)")
    args = p.parse_args(argv)
    _load_env()

    if args.check:
        return check()
    if args.fixture:
        out = args.out or PKG_DIR / "output" / "fixture-veltrava"
        r = run_fixture(out)
        print(f"{r.status}: {r.verdict} → {out}/report.md ({report_word_count(render_markdown(r))} words)")
        return 0
    if not args.company:
        p.error("company name is required (or use --check / --fixture)")

    from .orchestrator import run_research

    result = run_research(args.company, args.country, args.website, on_progress=_print_progress)
    out = args.out or PKG_DIR / "output" / f"{slugify(args.company)}-{date.today().isoformat()}"
    md_path, json_path = write_outputs(result, out)
    print(f"status: {result.status}")
    if result.status == "needs_clarification" and result.clarification:
        print(result.clarification.question)
        for c in result.clarification.candidates:
            print(f"  - {c.legal_name} | {c.country_name or c.country_code} | {c.website}")
        print("Re-run with --country and/or --website.")
    elif result.status == "error":
        print("; ".join(result.warnings))
    else:
        print(f"verdict: {result.verdict}")
    print(f"wrote {md_path} and {json_path}")
    summary = {"status": result.status, "flags": len(result.flags), "sources": len(result.sources)}
    print(json.dumps(summary))
    return 0 if result.status in ("ok", "partial", "needs_clarification") else 2


if __name__ == "__main__":
    raise SystemExit(main())
