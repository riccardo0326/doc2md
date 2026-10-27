from __future__ import annotations

from ...config import RouterConfig
from ...models import PageClass, PageSignals, RouteDecision


def classify(signals: PageSignals, config: RouterConfig, *, page: int = 0) -> RouteDecision:
    if (
        signals.chars == 0
        and signals.words == 0
        and signals.image_count == 0
        and signals.table_count == 0
    ):
        page_class: PageClass = "TEXT"
        reasons = ["empty_page"]
    elif not signals.has_text_layer:
        page_class = "SCANNED"
        reasons = ["no_text_layer"]
    elif signals.chars < config.min_chars and signals.image_area_ratio >= config.scan_image_ratio:
        page_class = "SCANNED"
        reasons = ["scan_like_page"]
    elif signals.garbled_ratio >= config.max_garbled:
        page_class = "COMPLEX"
        reasons = ["garbled_text"]
    elif signals.table_irregular:
        page_class = "COMPLEX"
        reasons = ["irregular_table"]
    elif (
        signals.image_area_ratio >= config.complex_image_ratio
        and signals.chars < config.image_page_min_chars
    ):
        page_class = "COMPLEX"
        reasons = ["image_dominant"]
    else:
        page_class = "TEXT"
        reasons = ["text_page"]

    return RouteDecision(page=page, page_class=page_class, reasons=reasons, signals=signals)
