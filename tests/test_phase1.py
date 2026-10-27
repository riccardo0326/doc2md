from __future__ import annotations

import json
import sys
from pathlib import Path

from typer.testing import CliRunner

from doc2md import Config, ConversionResult, convert
from doc2md.cli import app
from doc2md.config import RenderConfig
from doc2md.models import ConvertedDocument

runner = CliRunner()


def test_convert_writes_markdown_and_provenance(text_pdf: Path, tmp_path: Path) -> None:
    result = convert(
        text_pdf,
        tmp_path / "out",
        config=Config(render=RenderConfig(page_markers=True)),
    )

    assert isinstance(result, ConversionResult)
    assert result.markdown_path == tmp_path / "out" / "fixture" / "fixture.md"
    assert result.markdown.count("<!-- page: ") == 3
    assert "Page 1 heading" in result.markdown
    assert "Page 3 paragraph." in result.markdown

    assert result.json_path is not None
    sidecar = ConvertedDocument.model_validate_json(result.json_path.read_text(encoding="utf-8"))
    blocks = [block for page in sidecar.pages for block in page.blocks]
    assert [block.provenance.page for block in blocks] == [1, 1, 2, 2, 3, 3]
    assert [block.block_id for block in blocks] == [
        "p0001-b001",
        "p0001-b002",
        "p0002-b001",
        "p0002-b002",
        "p0003-b001",
        "p0003-b002",
    ]
    assert result.run_path is not None
    assert json.loads(result.run_path.read_text(encoding="utf-8"))["pipeline"] == "tiered"


def test_convert_is_deterministic_for_content_outputs(text_pdf: Path, tmp_path: Path) -> None:
    first = convert(text_pdf, tmp_path / "first")
    second = convert(text_pdf, tmp_path / "second")

    assert first.markdown == second.markdown
    assert first.json_path is not None
    assert second.json_path is not None
    assert first.json_path.read_bytes() == second.json_path.read_bytes()


def test_page_markers_are_opt_in_and_json_provenance_remains(text_pdf: Path) -> None:
    result = convert(text_pdf)

    assert "<!-- page: " not in result.markdown
    assert [block.provenance.page for page in result.document.pages for block in page.blocks] == [
        1,
        1,
        2,
        2,
        3,
        3,
    ]


def test_cli_convert_returns_zero_and_writes_outputs(text_pdf: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(text_pdf), "--out", str(tmp_path / "cli-out")])

    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "cli-out" / "fixture" / "fixture.md").is_file()
    assert "fixture.md" in result.stdout


def test_importing_public_api_does_not_import_docling() -> None:
    assert "docling" not in sys.modules
