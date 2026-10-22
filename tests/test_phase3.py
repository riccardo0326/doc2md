from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from doc2md import convert, inspect_pdf
from doc2md.cli import app

runner = CliRunner()


def test_inspect_returns_text_decisions(text_pdf: Path) -> None:
    decisions = inspect_pdf(text_pdf)

    assert len(decisions) == 3
    assert [decision.page_class for decision in decisions] == ["TEXT", "TEXT", "TEXT"]
    assert all(decision.signals.has_text_layer for decision in decisions)


def test_inspect_classifies_image_only_fixture() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")

    decisions = inspect_pdf(source)

    assert len(decisions) == 1
    assert decisions[0].page_class == "SCANNED"
    assert "no_text_layer" in decisions[0].reasons


def test_convert_leaves_hard_path_placeholder() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")

    result = convert(source)

    assert "<!-- page: 1 -->" in result.markdown
    assert "routed to hard path (not yet implemented)" in result.markdown
    assert result.document.pages[0].page_class == "SCANNED"
    assert result.document.pages[0].method is None


def test_inspect_cli_prints_classes_and_accepts_overrides(text_pdf: Path) -> None:
    result = runner.invoke(
        app,
        [
            "inspect",
            str(text_pdf),
            "--set",
            "router.min_chars_text_layer=10000",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "SCANNED" in result.stdout
    assert "page" in result.stdout.lower()
