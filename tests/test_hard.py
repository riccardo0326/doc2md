from __future__ import annotations

import sys
from pathlib import Path

import pytest

from doc2md import Config, convert
from doc2md.config import HardConfig, RouterConfig
from doc2md.converters.pdf.hard import DoclingExtractor
from doc2md.errors import HardExtractionError


def test_docling_adapter_import_is_lazy() -> None:
    assert "docling" not in sys.modules


def test_docling_requires_local_artifacts_by_default() -> None:
    source = Path("tests/fixtures/synthetic/phase1_table.pdf")

    with pytest.raises(HardExtractionError, match="artifacts"):
        DoclingExtractor().extract(source, [1])


def test_default_hard_path_fails_page_without_remote_download() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")

    result = convert(source)

    page = result.document.pages[0]
    assert page.status == "failed"
    assert page.error is not None
    assert "artifacts" in page.error.lower()


@pytest.mark.slow
def test_docling_extracts_table_blocks() -> None:
    source = Path("tests/fixtures/synthetic/phase1_table.pdf")
    extractor = DoclingExtractor(HardConfig(ocr=False, threads=1, allow_remote_download=True))

    blocks = extractor.extract(source, [1])[1]

    tables = [block for block in blocks if block.type == "table"]
    assert len(tables) == 1
    assert tables[0].meta["table_rows"] == 3
    assert tables[0].meta["table_cols"] == 3
    assert "| Item" in tables[0].markdown
    assert tables[0].provenance.page == 1


@pytest.mark.slow
def test_docling_preserves_non_contiguous_original_page_numbers() -> None:
    source = Path("tests/fixtures/synthetic/phase1_text_en.pdf")
    extractor = DoclingExtractor(HardConfig(ocr=False, threads=1, allow_remote_download=True))

    blocks_by_page = extractor.extract(source, [1, 3])

    assert set(blocks_by_page) == {1, 3}
    assert all(
        block.provenance.page == page for page, blocks in blocks_by_page.items() for block in blocks
    )


@pytest.mark.slow
def test_convert_routes_table_to_docling() -> None:
    source = Path("tests/fixtures/synthetic/phase1_table.pdf")
    config = Config(
        router=RouterConfig(complex_image_ratio=0.0, image_page_min_chars=1000),
        hard=HardConfig(ocr=False, threads=1, allow_remote_download=True),
    )

    result = convert(source, config=config)

    assert result.document.pages[0].method == "docling"
    assert any(block.type == "table" for block in result.document.pages[0].blocks)


@pytest.mark.slow
def test_docling_ocr_handles_image_only_page() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")
    extractor = DoclingExtractor(HardConfig(threads=1, allow_remote_download=True))

    try:
        blocks = extractor.extract(source, [1])[1]
    except HardExtractionError as error:
        message = str(error).lower()
        if "certificate" in message or "download" in message or "model" in message:
            pytest.skip(f"OCR model unavailable in this environment: {error}")
        raise

    assert any(block.text.strip() for block in blocks)
