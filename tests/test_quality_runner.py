from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from doc2md.models import ConvertedDocument


def _runner_module() -> ModuleType:
    path = Path("scripts/check_quality.py")
    spec = importlib.util.spec_from_file_location("check_quality", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quality_runner_accepts_formatting_differences(text_pdf: Path, tmp_path: Path) -> None:
    runner = _runner_module()
    reference = tmp_path / "reference.md"
    reference.write_text(
        "# Page 1 heading\nPage 1 paragraph.\n"
        "# Page 2 heading\nPage 2 paragraph.\n"
        "# Page 3 heading\nPage 3 paragraph.\n",
        encoding="utf-8",
    )

    report = runner.run_quality(
        text_pdf,
        tmp_path / "out",
        reference=reference,
        no_images=True,
    )

    assert report.passed
    assert report.failed_pages == []
    assert report.reference_token_coverage == 1.0
    assert report.json_path is not None
    ConvertedDocument.model_validate_json(Path(report.json_path).read_text(encoding="utf-8"))


def test_quality_runner_reports_missing_reference_content(text_pdf: Path, tmp_path: Path) -> None:
    runner = _runner_module()
    reference = tmp_path / "reference.md"
    reference.write_text(
        "Page 1 heading Page 1 paragraph. "
        "This reference contains a term absent from the candidate output "
        "and several additional missing terms.",
        encoding="utf-8",
    )

    report = runner.run_quality(text_pdf, tmp_path / "out", reference=reference, no_images=True)

    assert not report.passed
    assert any("reference token coverage" in error for error in report.errors)


def test_quality_runner_distinguishes_intentional_hard_page_failure(tmp_path: Path) -> None:
    runner = _runner_module()
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")

    report = runner.run_quality(source, tmp_path / "out", no_images=True)

    assert not report.passed
    assert report.failed_pages == [1]
    assert report.environment["enterprise_hard_adapter_configured"] is False
    assert any("failed pages" in error for error in report.errors)
