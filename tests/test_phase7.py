from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

from doc2md.bench.baseline_current import FakeBaselineAdapter
from doc2md.bench.report import render_report
from doc2md.bench.runner import RESULT_COLUMNS, run_benchmark
from doc2md.bench.suite import load_suite
from doc2md.vision.fake import FakeVisionBackend


class FakeHardExtractor:
    name = "fake-docling"

    def extract(self, source: Path, pages: list[int], context: object | None = None):
        del source, context
        return {page: [] for page in pages}


def _suite_file(tmp_path: Path) -> Path:
    path = tmp_path / "suite.toml"
    path.write_text(
        """
[suite]
name = "synthetic"
repetitions = 2
cold_cache = true

[[documents]]
id = "text"
path = "fixture.pdf"
tags = ["digital", "en"]

[[pipelines]]
name = "tiered"
[[pipelines]]
name = "full-vision"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_suite_loader_resolves_document_paths(tmp_path: Path) -> None:
    suite_path = _suite_file(tmp_path)

    suite = load_suite(suite_path)

    assert suite.name == "synthetic"
    assert suite.repetitions == 2
    assert suite.documents[0].path == tmp_path / "fixture.pdf"
    assert [pipeline.name for pipeline in suite.pipelines] == ["tiered", "full-vision"]


def test_runner_writes_exact_results_schema_and_cold_runs(text_pdf: Path, tmp_path: Path) -> None:
    suite_path = _suite_file(tmp_path)
    suite_path.write_text(
        suite_path.read_text(encoding="utf-8").replace("fixture.pdf", text_pdf.name)
    )

    def context_factory():
        return SimpleNamespace(vision=FakeVisionBackend(), hard=FakeHardExtractor())

    run_dir = run_benchmark(
        suite_path,
        output_dir=tmp_path / "bench-runs",
        context_factory=context_factory,
    )

    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        assert handle is not None
    assert list(rows[0]) == RESULT_COLUMNS
    assert len(rows) == 4
    assert {row["pipeline"] for row in rows} == {"tiered", "full-vision"}
    assert {row["rep"] for row in rows} == {"1", "2"}
    assert all(row["cache_hits"] == "0" for row in rows)
    assert (run_dir / "suite.toml").is_file()
    assert (run_dir / "env.json").is_file()


def test_report_is_deterministic_and_includes_comparison_sections(
    text_pdf: Path, tmp_path: Path
) -> None:
    suite_path = _suite_file(tmp_path)
    suite_path.write_text(
        suite_path.read_text(encoding="utf-8").replace("fixture.pdf", text_pdf.name)
    )

    run_dir = run_benchmark(
        suite_path,
        output_dir=tmp_path / "bench-runs",
        context_factory=lambda: SimpleNamespace(
            vision=FakeVisionBackend(), hard=FakeHardExtractor()
        ),
    )

    first = render_report(run_dir / "results.csv")
    second = render_report(run_dir / "results.csv")
    assert first == second
    assert "## Summary" in first
    assert "## Savings" in first
    assert "full-vision" in first


def test_fake_baseline_adapter_is_optional_and_uses_same_csv_schema(
    text_pdf: Path, tmp_path: Path
) -> None:
    suite_path = _suite_file(tmp_path)
    suite_path.write_text(
        suite_path.read_text(encoding="utf-8")
        .replace('[[pipelines]]\nname = "full-vision"', '[[pipelines]]\nname = "baseline_current"')
        .replace("fixture.pdf", text_pdf.name),
        encoding="utf-8",
    )

    run_dir = run_benchmark(
        suite_path,
        output_dir=tmp_path / "bench-runs",
        baseline_factory=FakeBaselineAdapter,
    )

    with (run_dir / "results.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == RESULT_COLUMNS
    baseline_rows = [row for row in rows if row["pipeline"] == "baseline_current"]
    assert baseline_rows
    assert baseline_rows[0]["total_tokens"] == ""
