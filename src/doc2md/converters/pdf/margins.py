from __future__ import annotations

from collections import defaultdict

from ...models import Block, PageResult


def _key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _margin_blocks(page: PageResult) -> list[tuple[str, Block]]:
    if page.status != "ok":
        return []
    blocks = [
        block
        for block in page.blocks
        if block.provenance.source == "pdfplumber" and block.text.strip()
    ]
    if not blocks:
        return []
    if len(blocks) == 1:
        return [("header", blocks[0])]
    return [("header", blocks[0]), ("footer", blocks[-1])]


def strip_repeated_margins(
    pages: list[PageResult], *, min_repetitions: int = 2
) -> list[PageResult]:
    occurrences: dict[tuple[str, str], set[int]] = defaultdict(set)
    numeric_footer_pages: set[int] = set()
    candidates_by_page: dict[int, list[tuple[str, Block]]] = {}

    for page in pages:
        candidates = _margin_blocks(page)
        candidates_by_page[page.page] = candidates
        for role, block in candidates:
            key = _key(block.text)
            occurrences[(role, key)].add(page.page)
            if role == "footer" and key.isdecimal():
                numeric_footer_pages.add(page.page)

    repeated = {
        candidate
        for candidate, page_numbers in occurrences.items()
        if len(page_numbers) >= min_repetitions
    }
    remove_numeric_footers = len(numeric_footer_pages) >= min_repetitions

    filtered: list[PageResult] = []
    for page in pages:
        remove_ids: set[str] = set()
        for role, block in candidates_by_page[page.page]:
            key = _key(block.text)
            candidate = (role, key)
            if candidate in repeated and page.page != 1:
                remove_ids.add(block.block_id)
            if (
                role == "footer"
                and key.isdecimal()
                and remove_numeric_footers
            ):
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
