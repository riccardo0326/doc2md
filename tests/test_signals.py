from __future__ import annotations

from doc2md.config import RouterConfig
from doc2md.converters.pdf.signals import compute_signals


class FakeTable:
    def __init__(self, rows: list[list[object]]) -> None:
        self.rows = rows

    def extract(self) -> list[list[object]]:
        return self.rows


class FakePage:
    width = 100
    height = 100

    def __init__(
        self, text: str, chars: int, images: list[dict[str, float]], tables: list[FakeTable]
    ):
        self._text = text
        self.chars = [{} for _ in range(chars)]
        self.images = images
        self._tables = tables

    def extract_text(self, **_: object) -> str:
        return self._text

    def extract_words(self) -> list[dict[str, str]]:
        return [{"text": word} for word in self._text.split()]

    def find_tables(self) -> list[FakeTable]:
        return self._tables


def test_compute_signals_collects_text_images_tables_and_garbling() -> None:
    page = FakePage(
        "alpha beta (cid:12)",
        chars=20,
        images=[{"x0": 0, "y0": 0, "x1": 50, "y1": 40}],
        tables=[FakeTable([["a", "b"], ["c"]])],
    )

    signals = compute_signals(page, RouterConfig())  # type: ignore[arg-type]

    assert signals.chars == 20
    assert signals.words == 3
    assert signals.image_count == 1
    assert signals.image_area_ratio == 0.2
    assert signals.table_count == 1
    assert signals.table_irregular
    assert signals.garbled_ratio > 0
    assert signals.has_text_layer


def test_compute_signals_uses_configured_text_layer_threshold() -> None:
    page = FakePage("short", chars=5, images=[], tables=[])

    signals = compute_signals(page, RouterConfig(min_chars_text_layer=10))  # type: ignore[arg-type]

    assert not signals.has_text_layer
