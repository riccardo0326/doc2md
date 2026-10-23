from __future__ import annotations

import json
from pathlib import Path

from doc2md.bench.judge import judge_run, parse_judge_response
from doc2md.bench.report import render_report
from doc2md.bench.review import select_pages, write_review_sheet
from doc2md.bench.runner import RESULT_COLUMNS


def _write_page_output(run_dir: Path, pipeline: str, page_classes: list[str]) -> None:
    output = run_dir / "outputs" / "doc" / pipeline / "rep1"
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": {"name": "fixture.pdf", "page_count": len(page_classes)},
        "pages": [
            {
                "page": page,
                "page_class": page_class,
                "status": "ok",
                "blocks": [
                    {
                        "block_id": f"p{page:04d}-b001",
                        "type": "paragraph",
                        "markdown": f"candidate page {page}",
                        "text": f"candidate page {page}",
                    }
                ],
            }
            for page, page_class in enumerate(page_classes, start=1)
        ],
    }
    (output / "fixture.json").write_text(json.dumps(payload), encoding="utf-8")


def _run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    classes = ["TEXT"] * 4 + ["COMPLEX"] * 3 + ["SCANNED"] * 2
    for pipeline in ("tiered", "full-vision", "docling-only"):
        _write_page_output(run_dir, pipeline, classes)
    (run_dir / "env.json").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "env.json").write_text(
        json.dumps({"documents": {"doc": str(tmp_path / "fixture.pdf")}}),
        encoding="utf-8",
    )
    (run_dir / "results.csv").write_text(",".join(RESULT_COLUMNS) + "\n", encoding="utf-8")
    return run_dir


def test_stratified_page_selection_is_seeded_and_balanced(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path)

    first = select_pages(run_dir, n=6, seed=42)
    second = select_pages(run_dir, n=6, seed=42)

    assert first == second
    assert len(first) == 6
    assert {sample.page_class for sample in first} == {"TEXT", "COMPLEX", "SCANNED"}


def test_review_sheet_blinds_pipeline_labels_and_writes_unblind_map(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path)

    paths = write_review_sheet(run_dir, n=6, seed=42)

    sheet = paths.csv_path.read_text(encoding="utf-8")
    mapping = json.loads(paths.unblind_path.read_text(encoding="utf-8"))
    assert "output_A" in sheet
    assert "tiered" not in sheet
    assert len(mapping) == 6
    assert paths.markdown_path.is_file()


def test_judge_parser_accepts_fenced_json_and_isolates_malformed_output() -> None:
    valid = parse_judge_response(
        '```json\n{"text_fidelity": 2, "special_characters": 1, '
        '"table_fidelity": 2, "figure_usefulness": 0, "reading_order": 2}\n```'
    )
    invalid = parse_judge_response("not json")

    assert valid.judge_error is None
    assert valid.scores["text_fidelity"] == 2
    assert invalid.judge_error is not None


def test_judge_run_writes_scores_and_report_merges_them(tmp_path: Path) -> None:
    run_dir = _run_dir(tmp_path)
    write_review_sheet(run_dir, n=3, seed=42)

    class FakeJudge:
        def judge(self, prompt: str, *, image_png: bytes | None = None) -> str:
            del prompt, image_png
            return (
                '{"text_fidelity": 2, "special_characters": 2, "table_fidelity": 2, '
                '"figure_usefulness": 2, "reading_order": 2}'
            )

    judge_path = judge_run(run_dir, backend=FakeJudge())

    assert judge_path.is_file()
    assert "Quality Scores" in render_report(run_dir / "results.csv")
