"""Supplier research engines; optional CLI dependencies load only on access."""
from typing import TYPE_CHECKING, Any

__all__ = ["run_research", "ResearchResult", "ProgressEvent"]

if TYPE_CHECKING:
    from .models import ProgressEvent, ResearchResult
    from .orchestrator import run_research


def __getattr__(name: str) -> Any:
    if name == "run_research":
        from .orchestrator import run_research
        return run_research
    if name in ("ResearchResult", "ProgressEvent"):
        from . import models
        return getattr(models, name)
    raise AttributeError(name)
