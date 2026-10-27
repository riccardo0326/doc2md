from __future__ import annotations

import pytest

from doc2md.config import RouterConfig
from doc2md.converters.pdf.router import classify
from doc2md.models import PageSignals


def signals(**changes: object) -> PageSignals:
    values: dict[str, object] = {
        "chars": 500,
        "words": 90,
        "image_area_ratio": 0.0,
        "image_count": 0,
        "table_count": 0,
        "table_irregular": False,
        "garbled_ratio": 0.0,
        "has_text_layer": True,
    }
    values.update(changes)
    return PageSignals.model_validate(values)


@pytest.mark.parametrize(
    ("page_signals", "expected", "reason"),
    [
        (signals(chars=0, words=0, has_text_layer=False), "TEXT", "empty_page"),
        (signals(has_text_layer=False), "SCANNED", "no_text_layer"),
        (signals(chars=5, image_area_ratio=0.8), "SCANNED", "scan_like_page"),
        (signals(garbled_ratio=0.2), "COMPLEX", "garbled_text"),
        (signals(table_irregular=True), "COMPLEX", "irregular_table"),
        (signals(chars=100, image_area_ratio=0.6), "COMPLEX", "image_dominant"),
        (signals(), "TEXT", "text_page"),
    ],
)
def test_classify_uses_first_matching_route_rule(
    page_signals: PageSignals, expected: str, reason: str
) -> None:
    decision = classify(page_signals, RouterConfig(), page=7)

    assert decision.page == 7
    assert decision.page_class == expected
    assert reason in decision.reasons


def test_classify_routes_missing_text_layer_to_scanned() -> None:
    decision = classify(signals(has_text_layer=False), RouterConfig(), page=1)

    assert decision.page_class == "SCANNED"
    assert "no_text_layer" in decision.reasons


def test_classify_keeps_textless_page_with_content_signals_on_hard_path() -> None:
    decision = classify(
        signals(chars=0, words=0, has_text_layer=False, image_count=1, image_area_ratio=1.0),
        RouterConfig(),
        page=2,
    )

    assert decision.page_class == "SCANNED"
    assert "no_text_layer" in decision.reasons
