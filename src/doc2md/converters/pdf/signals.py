from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from ...config import RouterConfig
from ...models import PageSignals

_CID_RE = re.compile(r"\(cid:\d+\)")


def _image_area(page: Any) -> float:
    page_area = float(page.width) * float(page.height)
    if page_area <= 0:
        return 0.0
    total = 0.0
    for image in page.images or []:
        x0 = max(0.0, min(float(page.width), float(image.get("x0", 0))))
        x1 = max(0.0, min(float(page.width), float(image.get("x1", 0))))
        y0 = max(0.0, min(float(page.height), float(image.get("y0", 0))))
        y1 = max(0.0, min(float(page.height), float(image.get("y1", 0))))
        total += max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return min(1.0, total / page_area)


def _table_irregular(tables: Iterable[Any], none_ratio: float) -> bool:
    for table in tables:
        rows = table.extract() or []
        lengths = [len(row) for row in rows if row is not None]
        if lengths and len(set(lengths)) > 1:
            return True
        cells = [cell for row in rows for cell in (row or [])]
        if cells and sum(cell in (None, "") for cell in cells) / len(cells) >= none_ratio:
            return True
    return False


def compute_signals(page: Any, config: RouterConfig | None = None) -> PageSignals:
    effective_config = config or RouterConfig()
    text = page.extract_text() or ""
    chars = len(page.chars) if getattr(page, "chars", None) else len(text)
    words = len(page.extract_words() or [])
    tables = page.find_tables() or []
    garbled_count = len(_CID_RE.findall(text))
    garbled_count += text.count("\ufffd")
    garbled_count += sum(0xE000 <= ord(char) <= 0xF8FF for char in text)
    return PageSignals(
        chars=chars,
        words=words,
        image_area_ratio=_image_area(page),
        image_count=len(page.images or []),
        table_count=len(tables),
        table_irregular=_table_irregular(tables, effective_config.table_none_ratio),
        garbled_ratio=garbled_count / max(len(text), 1),
        has_text_layer=chars >= effective_config.min_chars_text_layer,
    )
