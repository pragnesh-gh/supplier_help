"""Run budget: counts searches, page extracts and follow-ups, and enforces the wall clock."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping

from .config import BudgetSettings


def split_by_weight(total: int, weights: Mapping[str, float], order: list[str]) -> dict[str, int]:
    """Split ``total`` pages across areas in proportion to ``weights`` (largest remainder),
    giving every area at least 1 when ``total`` allows. Ties go to the earlier area in ``order``."""
    areas = [a for a in order if a in weights] or list(order)
    if not areas or total <= 0:
        return {a: 0 for a in order}
    w = {a: max(0.0, weights.get(a, 0.0)) for a in areas}
    wsum = sum(w.values()) or float(len(areas))
    if not sum(w.values()):
        w = {a: 1.0 for a in areas}
    exact = {a: total * w[a] / wsum for a in areas}
    minimum = 1 if total >= len(areas) else 0
    share = {a: max(minimum, int(exact[a])) for a in areas}
    rank = sorted(areas, key=lambda a: (-(exact[a] - int(exact[a])), -w[a], areas.index(a)))
    left = total - sum(share.values())
    for a in rank:
        if left <= 0:
            break
        share[a] += 1
        left -= 1
    for a in reversed(rank):  # only if the minimum of 1 overshot the total
        if left >= 0:
            break
        if share[a] > max(minimum, 1):
            share[a] -= 1
            left += 1
    return {a: share.get(a, 0) for a in order}


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

    def take_extracts(self, wanted: int, keep_for_followups: bool, keep_back: int = 0) -> int:
        """Reserve up to ``wanted`` page extracts; returns how many were granted.

        ``keep_back`` holds back further extracts (e.g. the open-web pages) on top of the
        follow-up reserve, so one kind of page can never use up another kind's share."""
        with self._lock:
            if self.expired():
                return 0
            cap = self.settings.max_extracts - max(0, keep_back)
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
