from __future__ import annotations

from threading import Lock

from .models import CallStat, PageStat
from .vision.base import VisionResult


class MetricsCollector:
    """Thread-safe run-local collector; totals are derived from recorded calls."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.pages: list[PageStat] = []
        self.calls: list[CallStat] = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.docling_pages = 0
        self.docling_time_s = 0.0

    def record_page(self, page: PageStat) -> None:
        with self._lock:
            self.pages.append(page)

    def record_call(
        self,
        kind: str,
        identifier: str,
        result: VisionResult,
        *,
        cache_hit: bool = False,
    ) -> None:
        with self._lock:
            self.calls.append(
                CallStat(
                    kind=kind,  # type: ignore[arg-type]
                    id=identifier,
                    model=result.model,
                    latency_s=result.latency_s,
                    input_tokens=result.usage.input_tokens,
                    output_tokens=result.usage.output_tokens,
                    total_tokens=result.usage.total_tokens,
                    estimated=result.usage.estimated,
                    cache_hit=cache_hit,
                )
            )

    def record_cache(self, *, hit: bool) -> None:
        with self._lock:
            if hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def record_docling(self, duration_s: float) -> None:
        with self._lock:
            self.docling_pages += 1
            self.docling_time_s += duration_s
