"""Run budget: counts searches, page extracts and follow-ups, and enforces the wall clock."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .config import BudgetSettings


class Budget:
    def __init__(self, settings: BudgetSettings, clock: Callable[[], float] = time.monotonic) -> None:
        self.settings = settings
        self._clock = clock
        self._start = clock()
        self._lock = threading.Lock()
        self.searches = 0
        self.extracts = 0
        self.followups = 0
        self.timed_out = False

    # time -------------------------------------------------------------
    def elapsed(self) -> float:
        return self._clock() - self._start

    def remaining(self) -> float:
        return max(0.0, self.settings.wall_clock_seconds - self.elapsed())

    def expired(self) -> bool:
        if self.remaining() <= 0:
            self.timed_out = True
            return True
        return False

    # counters ---------------------------------------------------------
    def take_search(self) -> bool:
        with self._lock:
            if self.expired() or self.searches >= self.settings.max_searches:
                return False
            self.searches += 1
            return True

    def take_extracts(self, wanted: int, keep_for_followups: bool) -> int:
        """Reserve up to ``wanted`` page extracts; returns how many were granted."""
        with self._lock:
            if self.expired():
                return 0
            cap = self.settings.max_extracts
            if keep_for_followups:
                cap -= self.settings.extracts_reserved_for_followups
            granted = max(0, min(wanted, cap - self.extracts))
            self.extracts += granted
            return granted

    def take_followup(self) -> bool:
        with self._lock:
            if self.expired() or self.followups >= self.settings.max_followups:
                return False
            self.followups += 1
            return True
