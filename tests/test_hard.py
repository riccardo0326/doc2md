from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from doc2md import Config, convert
from doc2md.config import HardConfig, ImageConfig, RouterConfig
from doc2md.converters.pdf.hard import DoclingExtractor
from doc2md.errors import HardExtractionError

DOC_LING_AVAILABLE = importlib.util.find_spec("docling") is not None


class FailingHardExtractor:
    name = "failing-docling"

    def extract(self, source: Path, pages: list[int], context: object | None = None):
        del source, pages, context
        raise HardExtractionError("local Docling artifacts unavailable")


def _merged_table_pdf(path: Path) -> None:
    document = SimpleDocTemplate(str(path), pagesize=letter)
    table = Table(
        [
            ["Classification", "Definition"],
            ["Public", "Information without restrictions."],
            [None, "The public use of company information requires approval."],
        ],
        colWidths=[1.5 * 72, 5 * 72],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, "black"),
                ("SPAN", (0, 1), (0, 2)),
            ]
        )
    )
    document.build([table])


def _one_row_table_pdf(path: Path) -> None:
    document = SimpleDocTemplate(str(path), pagesize=letter)
    table = Table([["Secret requirements", "The content must remain protected."]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black")]))
    document.build([table])


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


def test_text_backed_hard_failure_falls_back_to_pdfplumber() -> None:
    source = Path("tests/fixtures/synthetic/phase1_table.pdf")
    config = Config(
        images=ImageConfig(enabled=False),
        router=RouterConfig(complex_image_ratio=0.0, image_page_min_chars=10_000),
    )
    context = SimpleNamespace(hard=FailingHardExtractor())

    result = convert(source, config=config, context=context)

    page = result.document.pages[0]
    assert page.status == "ok"
    assert page.page_class == "COMPLEX"
    assert page.method == "pdfplumber"
    assert any("hard_path_fallback" in warning for warning in page.warnings)
    assert "| Item | Language | Status |" in result.markdown


def test_scanned_hard_failure_does_not_use_text_fallback() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")
    config = Config(images=ImageConfig(enabled=False))
    context = SimpleNamespace(hard=FailingHardExtractor())

    result = convert(source, config=config, context=context)

    page = result.document.pages[0]
    assert page.status == "failed"
    assert page.method is None
    assert not any("hard_path_fallback" in warning for warning in page.warnings)


def test_fallback_marks_merged_tables_as_simplified(tmp_path: Path) -> None:
    source = tmp_path / "merged-table.pdf"
    _merged_table_pdf(source)
    config = Config(images=ImageConfig(enabled=False))
    context = SimpleNamespace(hard=FailingHardExtractor())

    result = convert(source, config=config, context=context)

    assert result.document.pages[0].status == "ok"
    assert "<!-- table: simplified -->" in result.markdown
    assert "The public use of company information requires approval." in result.markdown


def test_fallback_keeps_one_row_table_text(tmp_path: Path) -> None:
    source = tmp_path / "one-row-table.pdf"
    _one_row_table_pdf(source)
    config = Config(
        images=ImageConfig(enabled=False),
        router=RouterConfig(complex_image_ratio=0.0, image_page_min_chars=10_000),
    )
    context = SimpleNamespace(hard=FailingHardExtractor())

    result = convert(source, config=config, context=context)

    assert result.document.pages[0].status == "ok"
    assert "The content must remain protected." in result.markdown


@pytest.mark.slow
@pytest.mark.skipif(not DOC_LING_AVAILABLE, reason="Docling optional dependency is not installed")
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
@pytest.mark.skipif(not DOC_LING_AVAILABLE, reason="Docling optional dependency is not installed")
def test_docling_preserves_non_contiguous_original_page_numbers() -> None:
    source = Path("tests/fixtures/synthetic/phase1_text_en.pdf")
    extractor = DoclingExtractor(HardConfig(ocr=False, threads=1, allow_remote_download=True))

    blocks_by_page = extractor.extract(source, [1, 3])

    assert set(blocks_by_page) == {1, 3}
    assert all(
        block.provenance.page == page for page, blocks in blocks_by_page.items() for block in blocks
    )


@pytest.mark.slow
@pytest.mark.skipif(not DOC_LING_AVAILABLE, reason="Docling optional dependency is not installed")
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
@pytest.mark.skipif(not DOC_LING_AVAILABLE, reason="Docling optional dependency is not installed")
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
