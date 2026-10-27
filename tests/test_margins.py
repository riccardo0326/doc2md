from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from doc2md import Config, convert
from doc2md.config import FastConfig, ImageConfig
from doc2md.converters.pdf.margins import strip_repeated_margins
from doc2md.models import Block, PageResult, Provenance


def _margin_fixture(path: Path) -> None:
    document = canvas.Canvas(str(path), pagesize=letter)
    for page_number in range(1, 4):
        document.setFont("Helvetica", 10)
        document.drawString(72, 760, "Running document title")
        document.drawString(72, 700, f"Unique body text for page {page_number}")
        document.drawString(72, 40, str(page_number))
        document.showPage()
    document.save()


def test_convert_removes_repeated_headers_and_numeric_footers(tmp_path: Path) -> None:
    source = tmp_path / "margins.pdf"
    _margin_fixture(source)

    result = convert(source, config=Config(images=ImageConfig(enabled=False)))
    page_text = [[block.text for block in page.blocks] for page in result.document.pages]

    assert page_text[0].count("Running document title") == 1
    assert all("Running document title" not in texts for texts in page_text[1:])
    assert all(str(page_number) not in texts for page_number, texts in enumerate(page_text[1:], 2))
    assert all(
        f"Unique body text for page {page_number}" in texts
        for page_number, texts in enumerate(page_text, 1)
    )


def test_convert_can_keep_repeated_margins(tmp_path: Path) -> None:
    source = tmp_path / "margins.pdf"
    _margin_fixture(source)
    config = Config(
        fast=FastConfig(strip_repeated_margins=False),
        images=ImageConfig(enabled=False),
    )

    result = convert(source, config=config)
    page_text = [[block.text for block in page.blocks] for page in result.document.pages]

    assert all("Running document title" in texts for texts in page_text)
    assert all(str(page_number) in texts for page_number, texts in enumerate(page_text, 1))


def test_margin_filter_removes_repeated_vision_margins() -> None:
    pages = [
        PageResult(
            page=page_number,
            status="ok",
            page_class="COMPLEX",
            method="vision",
            blocks=[
                Block(
                    block_id=f"p{page_number:04d}-b001",
                    type="paragraph",
                    markdown="Running document title",
                    text="Running document title",
                    provenance=Provenance(page=page_number, source="vision"),
                ),
                Block(
                    block_id=f"p{page_number:04d}-b002",
                    type="paragraph",
                    markdown=f"Unique body {page_number}",
                    text=f"Unique body {page_number}",
                    provenance=Provenance(page=page_number, source="vision"),
                ),
                Block(
                    block_id=f"p{page_number:04d}-b003",
                    type="paragraph",
                    markdown=str(page_number),
                    text=str(page_number),
                    provenance=Provenance(page=page_number, source="vision"),
                ),
            ],
        )
        for page_number in range(1, 4)
    ]

    filtered = strip_repeated_margins(pages)

    assert [block.text for block in filtered[0].blocks] == [
        "Running document title",
        "Unique body 1",
        "1",
    ]
    assert [block.text for block in filtered[1].blocks] == ["Unique body 2"]
    assert [block.text for block in filtered[2].blocks] == ["Unique body 3"]
