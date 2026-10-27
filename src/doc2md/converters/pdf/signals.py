from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ...config import RouterConfig
from ...models import PageSignals

_CID_RE = re.compile(r"\(cid:\d+\)")
_BORDERLESS_MIN_ROWS = 3
_BORDERLESS_MIN_COLUMNS = 3
_BORDERLESS_COLUMN_GAP_PT = 15.0


@dataclass(frozen=True)
class BorderlessTable:
    rows: list[list[str]]
    top: float
    bottom: float


def _word_rows(page: Any) -> list[list[dict[str, Any]]]:
    words = page.extract_words() or []
    rows: list[list[dict[str, Any]]] = []
    for word in sorted(
        words, key=lambda item: (float(item.get("top", 0)), float(item.get("x0", 0)))
    ):
        top = float(word.get("top", 0))
        row = next(
            (
                candidate
                for candidate in reversed(rows)
                if abs(float(candidate[0].get("top", 0)) - top) <= 2.5
            ),
            None,
        )
        if row is None:
            rows.append([word])
        else:
            row.append(word)
    return rows


def _numeric_row(row: list[dict[str, Any]]) -> bool:
    if len(row) < _BORDERLESS_MIN_COLUMNS:
        return False
    numeric_words = sum(any(char.isdigit() for char in str(word.get("text", ""))) for word in row)
    return numeric_words >= 1


def _clusters(rows: list[list[dict[str, Any]]]) -> list[float]:
    positions = sorted(float(word.get("x0", 0)) for row in rows for word in row)
    clusters: list[list[float]] = []
    for position in positions:
        if (
            not clusters
            or position - sum(clusters[-1]) / len(clusters[-1])
            > _BORDERLESS_COLUMN_GAP_PT
        ):
            clusters.append([position])
        else:
            clusters[-1].append(position)
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _map_row(row: list[dict[str, Any]], columns: list[float]) -> list[str]:
    cells = [""] * len(columns)
    for word in sorted(row, key=lambda item: float(item.get("x0", 0))):
        x0 = float(word.get("x0", 0))
        column = min(range(len(columns)), key=lambda index: abs(columns[index] - x0))
        value = str(word.get("text", "")).strip()
        if value:
            cells[column] = f"{cells[column]} {value}".strip()
    return cells


def detect_borderless_table(page: Any) -> BorderlessTable | None:
    if not hasattr(page, "extract_words"):
        return None
    rows = _word_rows(page)
    runs: list[list[int]] = []
    current: list[int] = []
    for index, row in enumerate(rows):
        if _numeric_row(row):
            current.append(index)
        elif current:
            if len(current) >= _BORDERLESS_MIN_ROWS:
                runs.append(current)
            current = []
    if len(current) >= _BORDERLESS_MIN_ROWS:
        runs.append(current)
    if not runs:
        return None

    data_indices = max(runs, key=len)
    data_rows = [rows[index] for index in data_indices]
    columns = _clusters(data_rows)
    if len(columns) < _BORDERLESS_MIN_COLUMNS:
        return None
    mapped_data = [_map_row(row, columns) for row in data_rows]
    if any(sum(bool(cell) for cell in row) < len(columns) - 1 for row in mapped_data):
        return None

    header_rows = rows[max(0, data_indices[0] - 2) : data_indices[0]]
    header = [""] * len(columns)
    for row in header_rows:
        mapped = _map_row(row, columns)
        for index, value in enumerate(mapped):
            if value:
                header[index] = f"{header[index]} {value}".strip()
    if sum(bool(cell) for cell in header) < _BORDERLESS_MIN_COLUMNS:
        header = mapped_data.pop(0)
    if not mapped_data:
        return None

    table_rows = [header, *mapped_data]
    top = float(rows[max(0, data_indices[0] - len(header_rows))][0].get("top", 0))
    bottom = max(float(word.get("bottom", word.get("top", 0))) for row in data_rows for word in row)
    return BorderlessTable(rows=table_rows, top=top, bottom=bottom)


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
    borderless_table = detect_borderless_table(page) if not tables else None
    garbled_count = len(_CID_RE.findall(text))
    garbled_count += text.count("\ufffd")
    garbled_count += sum(0xE000 <= ord(char) <= 0xF8FF for char in text)
    return PageSignals(
        chars=chars,
        words=words,
        image_area_ratio=_image_area(page),
        image_count=len(page.images or []),
        table_count=len(tables) + (1 if borderless_table else 0),
        table_irregular=_table_irregular(tables, effective_config.table_none_ratio)
        or borderless_table is not None,
        garbled_ratio=garbled_count / max(len(text), 1),
        has_text_layer=chars >= effective_config.min_chars_text_layer,
    )
