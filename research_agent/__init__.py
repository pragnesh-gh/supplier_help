"""Supplier deep-research agent (first draft).

Public entry point: :func:`run_research`.

Everything is imported lazily, so ``research_agent.app_adapter`` (used by the web app) can be
imported without the research dependencies (pydantic, anthropic) installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["run_research", "ResearchResult", "ProgressEvent"]

if TYPE_CHECKING:
    from .models import ProgressEvent, ResearchResult
    from .orchestrator import run_research
else:

    def __getattr__(name: str) -> Any:
        if name == "run_research":
            from .orchestrator import run_research

            return run_research
        if name in ("ResearchResult", "ProgressEvent"):
            from . import models

            return getattr(models, name)
        raise AttributeError(name)
