from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pdfplumber

from ...config import FastConfig
from ...models import Block, Provenance
from .headings import normalize_heading
from .margins import MarginSignatures, is_margin_line
from .normalize import is_garbled, normalize_text
from .signals import detect_borderless_table

_LIST_MARKER_RE = re.compile(r"(?<!\S)(?:[-*+\u2022\u25cf]|\d+[.)])\s+")
_SECTION_PREFIX_RE = re.compile(
    r"^(?:(?:\d+(?:\.\d+)+|[IVXLCDM]+(?:\.[IVXLCDM]+)*|[A-Z](?:\.\d+)*)[.)]?|\d+|[IVXLCDM]+|[A-Z])(?:\s|$)",
    re.IGNORECASE,
)
_SECTION_PREFIX_ONLY_RE = re.compile(
    r"^(?:\d+(?:\.\d+)+|[IVXLCDM]+(?:\.[IVXLCDM]+)*|[A-Z](?:\.\d+)*|\d+|[IVXLCDM]+|[A-Z])[.)]?$",
    re.IGNORECASE,
)
_SIMPLE_NUMERIC_HEADING_RE = re.compile(r"^\d+\s+", re.IGNORECASE)
_TOC_LEADER_RE = re.compile(r"\.{3,}\s*\d+\s*$")


@dataclass(frozen=True)
class _Line:
    words: tuple[dict[str, Any], ...]
    top: float
    bottom: float
    x0: float
    text: str
    size: float


@dataclass(frozen=True)
class _Element:
    top: float
    kind: str
    value: Any


def _word_lines(page: Any, config: FastConfig) -> list[_Line]:
    if not hasattr(page, "extract_words"):
        return []
    try:
        words = (
            page.extract_words(
                x_tolerance=1,
                y_tolerance=3,
                extra_attrs=["size"],
            )
            or []
        )
    except (TypeError, AttributeError):
        words = page.extract_words(x_tolerance=1, y_tolerance=3) or []
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(
        words, key=lambda item: (float(item.get("top", 0)), float(item.get("x0", 0)))
    ):
        top = float(word.get("top", 0))
        target = next(
            (
                line
                for line in reversed(lines)
                if abs(float(line[0].get("top", 0)) - top) <= 3
                and float(word.get("x0", 0))
                - max(float(item.get("x1", item.get("x0", 0))) for item in line)
                <= config.column_gutter_min_pt
            ),
            None,
        )
        if target is None:
            lines.append([word])
        else:
            target.append(word)
    result: list[_Line] = []
    for words_on_line in lines:
        ordered = tuple(sorted(words_on_line, key=lambda item: float(item.get("x0", 0))))
        text = " ".join(str(word.get("text", "")) for word in ordered).strip()
        if not text:
            continue
        sizes = [float(word.get("size", 0)) for word in ordered if word.get("size") is not None]
        result.append(
            _Line(
                words=ordered,
                top=min(float(word.get("top", 0)) for word in ordered),
                bottom=max(float(word.get("bottom", word.get("top", 0))) for word in ordered),
                x0=min(float(word.get("x0", 0)) for word in ordered),
                text=text,
                size=max(sizes, default=0.0),
            )
        )
    return result


def _reading_order(lines: list[_Line], page_width: float, config: FastConfig) -> list[_Line]:
    if not lines:
        return []
    left = [line for line in lines if line.x0 < page_width / 2]
    right = [line for line in lines if line.x0 >= page_width / 2]
    if not left or not right:
        return sorted(lines, key=lambda line: (line.top, line.x0))
    left_edge = max(line.x0 for line in left)
    right_edge = min(line.x0 for line in right)
    if right_edge - left_edge < config.column_gutter_min_pt:
        return sorted(lines, key=lambda line: (line.top, line.x0))
    # A clear two-column layout is read top-to-bottom in the left column first.
    return sorted(left, key=lambda line: (line.top, line.x0)) + sorted(
        right, key=lambda line: (line.top, line.x0)
    )


def _median(values: list[float]) -> float:
    ordered = sorted(value for value in values if value > 0)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _table_markdown(
    rows: list[list[Any]],
) -> tuple[str, str, dict[str, str | int | float | bool]] | None:
    clean_rows = [
        [normalize_text(str(cell or ""), preserve_lines=True).strip() for cell in row]
        for row in rows
    ]
    if (
        len(clean_rows) < 2
        or not clean_rows[0]
        or any(len(row) != len(clean_rows[0]) for row in clean_rows)
    ):
        return None
    if len(clean_rows[0]) < 2:
        return None

    simplified = any(not value for row in clean_rows for value in row)

    def cell(value: str) -> str:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        return "<br>".join(line.replace("|", "\\|") for line in lines)

    header = clean_rows[0]
    markdown = [
        "| " + " | ".join(cell(value) for value in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    if simplified:
        markdown.insert(0, "<!-- table: simplified -->")
    markdown.extend(
        "| " + " | ".join(cell(value) for value in row) + " |" for row in clean_rows[1:]
    )
    text = "\n".join(
        " | ".join(" ".join(value.splitlines()) for value in row) for row in clean_rows
    )
    return "\n".join(markdown), text, {"table_rows": len(clean_rows), "table_cols": len(header)}


def _starts_list_item(text: str) -> bool:
    return _LIST_MARKER_RE.match(text.strip()) is not None


def _list_items(text: str) -> list[str] | None:
    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        matches = list(_LIST_MARKER_RE.finditer(line))
        if matches and matches[0].start() == 0:
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
                item = line[match.end() : end].strip()
                if item:
                    items.append(item)
            continue
        if items:
            items[-1] = f"{items[-1]} {line}"
            continue
        return None
    return items or None


def _is_section_heading(text: str) -> bool:
    flattened = " ".join(text.split())
    return bool(
        flattened
        and not _TOC_LEADER_RE.search(flattened)
        and _SECTION_PREFIX_RE.match(flattened)
        and not _SECTION_PREFIX_ONLY_RE.fullmatch(flattened)
    )


def _is_heading_line(line: _Line, median_size: float, config: FastConfig) -> bool:
    if _starts_list_item(line.text):
        return False
    flattened = " ".join(line.text.split())
    prefix_only = _SECTION_PREFIX_ONLY_RE.fullmatch(flattened) is not None
    simple_numeric_heading = _SIMPLE_NUMERIC_HEADING_RE.match(flattened) is not None
    return bool(
        (median_size and line.size >= median_size * config.heading_ratio)
        or (not prefix_only and not simple_numeric_heading and _is_section_heading(line.text))
    )


def _paragraph_groups(
    lines: list[_Line], median_size: float, config: FastConfig
) -> list[list[_Line]]:
    groups: list[list[_Line]] = []
    for line in lines:
        if not groups:
            groups.append([line])
            continue
        previous = groups[-1][-1]
        current_heading = _is_heading_line(line, median_size, config)
        previous_heading = _is_heading_line(previous, median_size, config)
        heading_continuation = (
            current_heading
            and previous_heading
            and not _is_section_heading(line.text)
        )
        if (
            (current_heading and not heading_continuation)
            or (previous_heading and not heading_continuation)
            or (_starts_list_item(line.text) and not _starts_list_item(previous.text))
            or abs(line.x0 - previous.x0) >= config.column_gutter_min_pt
        ):
            groups.append([line])
            continue
        gap = line.top - previous.bottom
        line_height = max(previous.bottom - previous.top, line.bottom - line.top, 0.1)
        if gap > line_height * 0.9:
            groups.append([line])
        else:
            groups[-1].append(line)
    return groups


def _block(
    page_number: int,
    number: int,
    lines: list[_Line],
    median_size: float,
    config: FastConfig,
) -> Block:
    text = normalize_text("\n".join(line.text for line in lines), preserve_lines=True)
    flattened = " ".join(text.split())
    list_items = _list_items(text)
    if list_items:
        markdown = "\n".join(f"- {item}" for item in list_items)
        block_type = "list"
        level = None
    elif _is_heading_line(
        _Line(
            (),
            lines[0].top,
            lines[-1].bottom,
            lines[0].x0,
            flattened,
            max(line.size for line in lines),
        ),
        median_size,
        config,
    ):
        candidate_level = (
            1 if median_size and max(line.size for line in lines) >= median_size * 1.6 else 2
        )
        markdown, flattened, level = normalize_heading(flattened, candidate_level)
        block_type = "heading"
    else:
        level = None
        markdown = flattened
        block_type = "paragraph"
    return Block(
        block_id=f"p{page_number:04d}-b{number:03d}",
        type=block_type,  # type: ignore[arg-type]
        markdown=markdown,
        text=flattened,
        level=level,
        provenance=Provenance(page=page_number, source="pdfplumber"),
        meta={"garbled": True} if is_garbled(flattened) else {},
    )


def extract_page(
    page: pdfplumber.page.Page,
    page_number: int,
    config: FastConfig | None = None,
    margin_signatures: MarginSignatures | None = None,
) -> list[Block]:
    effective_config = config or FastConfig()
    lines = _word_lines(page, effective_config)
    had_word_lines = bool(lines)
    if lines and margin_signatures is not None and page_number != 1:
        lines = [
            line
            for line in lines
            if not is_margin_line(
                line.top,
                line.bottom,
                line.text,
                float(getattr(page, "height", 792.0)),
                margin_signatures,
            )
        ]
    if not lines and not had_word_lines:
        extracted = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
        text = normalize_text(extracted, preserve_lines=True)
        lines = [
            _Line((), float(index), float(index) + 0.1, 0.0, line, 0.0)
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]

    lines = _reading_order(lines, float(getattr(page, "width", 612.0)), effective_config)
    median_size = _median([line.size for line in lines])
    table_elements: list[_Element] = []
    table_ranges: list[tuple[float, float]] = []
    detected_tables = list((page.find_tables() if hasattr(page, "find_tables") else []) or [])
    for table in detected_tables:
        rows = table.extract() or []
        rendered = _table_markdown(rows)
        if rendered is None:
            continue
        markdown, text, meta = rendered
        bbox = tuple(getattr(table, "bbox", (0.0, 0.0, 0.0, 0.0)))
        top = float(bbox[1])
        bottom = float(bbox[3])
        table_elements.append(_Element(top, "table", (markdown, text, meta)))
        table_ranges.append((top, bottom))

    if not detected_tables:
        borderless = detect_borderless_table(page)
        if borderless is not None:
            rendered = _table_markdown(borderless.rows)
            if rendered is not None:
                markdown, text, meta = rendered
                table_elements.append(
                    _Element(borderless.top, "table", (markdown, text, meta))
                )
                table_ranges.append((borderless.top, borderless.bottom))

    text_lines = [
        line
        for line in lines
        if not any(top - 2 <= line.top <= bottom + 2 for top, bottom in table_ranges)
    ]
    elements: list[_Element] = [
        _Element(group[0].top, "text", group)
        for group in _paragraph_groups(text_lines, median_size, effective_config)
    ]
    elements.extend(table_elements)
    elements.sort(key=lambda element: (element.top, 0 if element.kind == "text" else 1))

    blocks: list[Block] = []
    for element in elements:
        number = len(blocks) + 1
        if element.kind == "text":
            blocks.append(_block(page_number, number, element.value, median_size, effective_config))
            continue
        markdown, text, meta = element.value
        blocks.append(
            Block(
                block_id=f"p{page_number:04d}-b{number:03d}",
                type="table",
                markdown=markdown,
                text=text,
                provenance=Provenance(page=page_number, source="pdfplumber"),
                meta=meta,
            )
        )
    return blocks
