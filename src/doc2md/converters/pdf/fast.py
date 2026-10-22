from __future__ import annotations

import pdfplumber

from ...models import Block, Provenance
from .normalize import is_garbled, normalize_text


def _paragraph_lines(text: str) -> list[str]:
    paragraphs: list[str] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if line:
            paragraphs.append(line)
    return paragraphs


def extract_page(page: pdfplumber.page.Page, page_number: int) -> list[Block]:
    extracted = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
    text = normalize_text(extracted, preserve_lines=True)
    blocks: list[Block] = []
    for block_number, paragraph in enumerate(_paragraph_lines(text), start=1):
        blocks.append(
            Block(
                block_id=f"p{page_number:04d}-b{block_number:03d}",
                type="paragraph",
                markdown=paragraph,
                text=paragraph,
                provenance=Provenance(page=page_number, source="pdfplumber"),
                meta={"garbled": True} if is_garbled(paragraph) else {},
            )
        )
    return blocks
