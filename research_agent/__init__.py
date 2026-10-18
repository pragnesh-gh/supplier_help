"""Supplier deep-research agent (first draft).

Public entry point: :func:`run_research`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import ProgressEvent, ResearchResult

__all__ = ["run_research", "ResearchResult", "ProgressEvent"]

if TYPE_CHECKING:
    from .orchestrator import run_research
else:

    def __getattr__(name: str) -> Any:
        if name == "run_research":
            from .orchestrator import run_research

            return run_research
        raise AttributeError(name)
