from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from ...models import Block, PageResult
from .normalize import normalize_text

_NUMERIC_RE = re.compile(r"^\d{1,4}$")


@dataclass(frozen=True)
class MarginSignatures:
    headers: frozenset[str]
    footers: frozenset[str]
    numeric_footer: bool
    zone_ratio: float = 0.12


def _key(text: str) -> str:
    return normalize_text(text).casefold()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold()))


def _matches_signature(key: str, signatures: frozenset[str]) -> bool:
    if key in signatures:
        return True
    candidate_tokens = _tokens(key)
    if not candidate_tokens:
        return False
    return any(
        len(signature_tokens) >= 3
        and (
            len(candidate_tokens & signature_tokens) / len(signature_tokens) >= 0.8
            or (len(candidate_tokens) >= 2 and candidate_tokens <= signature_tokens)
        )
        for signature_tokens in (_tokens(signature) for signature in signatures)
    )


def _group_words(words: Iterable[dict[str, Any]]) -> list[tuple[float, float, str]]:
    lines: list[list[dict[str, Any]]] = []
    for word in sorted(
        words,
        key=lambda item: (float(item.get("top", 0)), float(item.get("x0", 0))),
    ):
        top = float(word.get("top", 0))
        target = next(
            (line for line in reversed(lines) if abs(float(line[0].get("top", 0)) - top) <= 3),
            None,
        )
        if target is None:
            lines.append([word])
        else:
            target.append(word)

    result: list[tuple[float, float, str]] = []
    for line in lines:
        ordered = sorted(line, key=lambda item: float(item.get("x0", 0)))
        text = " ".join(str(item.get("text", "")) for item in ordered).strip()
        if text:
            result.append(
                (
                    min(float(item.get("top", 0)) for item in ordered),
                    max(
                        float(item.get("bottom", item.get("top", 0)))
                        for item in ordered
                    ),
                    text,
                )
            )
    return result


def _page_margin_lines(page: Any, zone_ratio: float) -> list[tuple[str, str]]:
    if not hasattr(page, "extract_words"):
        return []
    try:
        words = page.extract_words() or []
    except (TypeError, AttributeError):
        return []
    height = float(getattr(page, "height", 792.0))
    lines = _group_words(words)
    result: list[tuple[str, str]] = []
    for top, bottom, text in lines:
        if top <= height * zone_ratio:
            role = "header"
        elif bottom >= height * (1 - zone_ratio):
            role = "footer"
        else:
            role = ""
        if role:
            result.append((role, _key(text)))
    return result


def detect_repeated_margins(
    pages: Iterable[Any], *, min_repetitions: int = 2, zone_ratio: float = 0.12
) -> MarginSignatures:
    occurrences: dict[tuple[str, str], set[int]] = defaultdict(set)
    numeric_footer_pages: set[int] = set()
    for page_number, page in enumerate(pages, start=1):
        for role, text in _page_margin_lines(page, zone_ratio):
            occurrences[(role, text)].add(page_number)
            if role == "footer" and _NUMERIC_RE.fullmatch(text):
                numeric_footer_pages.add(page_number)

    repeated_headers = {
        text
        for (role, text), page_numbers in occurrences.items()
        if role == "header" and len(page_numbers) >= min_repetitions
    }
    repeated_footers = {
        text
        for (role, text), page_numbers in occurrences.items()
        if role == "footer" and len(page_numbers) >= min_repetitions
    }
    return MarginSignatures(
        headers=frozenset(repeated_headers),
        footers=frozenset(repeated_footers),
        numeric_footer=len(numeric_footer_pages) >= min_repetitions,
        zone_ratio=zone_ratio,
    )


def is_margin_line(
    top: float,
    bottom: float,
    text: str,
    page_height: float,
    signatures: MarginSignatures,
) -> bool:
    key = _key(text)
    if (
        top <= page_height * signatures.zone_ratio
        and _matches_signature(key, signatures.headers)
    ):
        return True
    if bottom >= page_height * (1 - signatures.zone_ratio):
        return _matches_signature(key, signatures.footers) or (
            signatures.numeric_footer and _NUMERIC_RE.fullmatch(key) is not None
        )
    return False


def _candidate_blocks(page: PageResult) -> list[tuple[str, Block]]:
    if page.status != "ok":
        return []
    blocks = [block for block in page.blocks if block.text.strip()]
    if not blocks:
        return []
    if len(blocks) == 1:
        return [("header", blocks[0])]
    edge_count = min(3, len(blocks))
    return [
        *(("header", block) for block in blocks[:edge_count]),
        *(("footer", block) for block in blocks[-edge_count:]),
    ]


def strip_repeated_margins(
    pages: list[PageResult],
    *,
    min_repetitions: int = 2,
    signatures: MarginSignatures | None = None,
) -> list[PageResult]:
    candidates_by_page = {page.page: _candidate_blocks(page) for page in pages}
    if signatures is None:
        occurrences: dict[tuple[str, str], set[int]] = defaultdict(set)
        numeric_footer_pages: set[int] = set()
        for page in pages:
            for role, block in candidates_by_page[page.page]:
                key = _key(block.text)
                occurrences[(role, key)].add(page.page)
                if role == "footer" and _NUMERIC_RE.fullmatch(key):
                    numeric_footer_pages.add(page.page)
        signatures = MarginSignatures(
            headers=frozenset(
                text
                for (role, text), page_numbers in occurrences.items()
                if role == "header" and len(page_numbers) >= min_repetitions
            ),
            footers=frozenset(
                text
                for (role, text), page_numbers in occurrences.items()
                if role == "footer" and len(page_numbers) >= min_repetitions
            ),
            numeric_footer=len(numeric_footer_pages) >= min_repetitions,
        )

    filtered: list[PageResult] = []
    for page in pages:
        remove_ids: set[str] = set()
        for role, block in candidates_by_page[page.page]:
            key = _key(block.text)
            repeated = _matches_signature(
                key,
                signatures.headers if role == "header" else signatures.footers,
            )
            numeric_footer = (
                role == "footer"
                and signatures.numeric_footer
                and _NUMERIC_RE.fullmatch(key) is not None
            )
            if page.page != 1 and (repeated or numeric_footer):
                remove_ids.add(block.block_id)
        if remove_ids:
            filtered.append(
                page.model_copy(
                    update={
                        "blocks": [
                            block for block in page.blocks if block.block_id not in remove_ids
                        ]
                    }
                )
            )
        else:
            filtered.append(page)
    return filtered
