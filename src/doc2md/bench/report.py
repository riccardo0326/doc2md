from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from .runner import RESULT_COLUMNS


def _number(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def render_report(results_path: str | Path) -> str:
    with Path(results_path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != RESULT_COLUMNS:
            raise ValueError("results.csv does not have the required Phase 7 columns")
        rows = list(reader)
    by_pipeline: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_pipeline[row["pipeline"]].append(row)

    lines = [
        "# Benchmark Report",
        "",
        "## Summary",
        "",
        "| Pipeline | Runs | Pages | Failed | Vision calls | Total tokens | Wall time (s) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pipeline in sorted(by_pipeline):
        values = by_pipeline[pipeline]
        lines.append(
            "| {pipeline} | {runs} | {pages:.0f} | {failed:.0f} | {calls:.0f} | "
            "{tokens:.0f} | {wall:.3f} |".format(
                pipeline=pipeline,
                runs=len(values),
                pages=sum(_number(row, "pages_total") for row in values) / len(values),
                failed=sum(_number(row, "pages_failed") for row in values),
                calls=sum(_number(row, "vision_calls") for row in values),
                tokens=sum(_number(row, "total_tokens") for row in values),
                wall=median(_number(row, "wall_time_s") for row in values),
            )
        )

    lines.extend(
        [
            "",
            "## Savings",
            "",
            "Savings are computed from total parsing tokens when both pipelines report them.",
            "",
            "| Pipeline | Compared with | Token savings |",
            "|---|---|---:|",
        ]
    )
    token_totals = {
        pipeline: sum(_number(row, "total_tokens") for row in values)
        for pipeline, values in by_pipeline.items()
    }
    comparisons = ["baseline_current", "full-vision"]
    for pipeline in sorted(by_pipeline):
        if pipeline in comparisons:
            continue
        for baseline in comparisons:
            if baseline not in token_totals or token_totals[baseline] <= 0:
                continue
            savings = (token_totals[baseline] - token_totals[pipeline]) / token_totals[baseline]
            lines.append(f"| {pipeline} | {baseline} | {savings:.1%} |")
    lines.extend(["", "## Notes", "", "- Results are grouped from the recorded repetitions."])
    judge_path = Path(results_path).parent / "scores_judge.json"
    if judge_path.is_file():
        records = json.loads(judge_path.read_text(encoding="utf-8"))
        mapping_path = Path(results_path).parent / "review" / "unblind_map.json"
        mapping = (
            json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.is_file() else {}
        )
        totals: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for record in records:
            scores = record.get("scores", {})
            pipeline = mapping.get(record.get("sample_id"), {}).get(record.get("label"))
            if not pipeline or record.get("judge_error"):
                continue
            for criterion, score in scores.items():
                if isinstance(score, int):
                    totals[pipeline][criterion].append(score)
        lines.extend(
            [
                "",
                "## Quality Scores",
                "",
                "Judge scores use the local model and may reflect model/style bias.",
                "",
                "| Pipeline | Text | Special chars | Tables | Figures | Order |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for pipeline in sorted(totals):
            quality_values = totals[pipeline]
            means = {
                criterion: sum(scores) / len(scores) if scores else 0.0
                for criterion, scores in quality_values.items()
            }
            lines.append(
                f"| {pipeline} | {means.get('text_fidelity', 0):.2f} | "
                f"{means.get('special_characters', 0):.2f} | "
                f"{means.get('table_fidelity', 0):.2f} | "
                f"{means.get('figure_usefulness', 0):.2f} | "
                f"{means.get('reading_order', 0):.2f} |"
            )
    manual_paths = (
        Path(results_path).parent / "scores_manual.csv",
        Path(results_path).parent / "review" / "review_sheet.csv",
    )
    manual_path = next((path for path in manual_paths if path.is_file()), None)
    mapping_path = Path(results_path).parent / "review" / "unblind_map.json"
    if manual_path is not None and mapping_path.is_file():
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        manual_totals: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        criteria = {
            "text": "text_fidelity",
            "special": "special_characters",
            "table": "table_fidelity",
            "figure": "figure_usefulness",
            "order": "reading_order",
        }
        with manual_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                for label, pipeline in mapping.get(row.get("sample_id", ""), {}).items():
                    for prefix, criterion in criteria.items():
                        raw = row.get(f"{prefix}_{label}_score", "")
                        if raw in {"0", "1", "2"}:
                            manual_totals[pipeline][criterion].append(int(raw))
        if manual_totals:
            lines.extend(
                [
                    "",
                    "## Manual Quality Scores",
                    "",
                    "| Pipeline | Text | Special chars | Tables | Figures | Order |",
                    "|---|---:|---:|---:|---:|---:|",
                ]
            )
            for pipeline in sorted(manual_totals):
                manual_values = manual_totals[pipeline]
                means = {
                    criterion: sum(scores) / len(scores) if scores else 0.0
                    for criterion, scores in manual_values.items()
                }
                lines.append(
                    f"| {pipeline} | {means.get('text_fidelity', 0):.2f} | "
                    f"{means.get('special_characters', 0):.2f} | "
                    f"{means.get('table_fidelity', 0):.2f} | "
                    f"{means.get('figure_usefulness', 0):.2f} | "
                    f"{means.get('reading_order', 0):.2f} |"
                )
    lines.append("")
    return "\n".join(lines)


def write_report(run_dir: str | Path) -> Path:
    directory = Path(run_dir)
    path = directory / "report.md"
    path.write_text(render_report(directory / "results.csv"), encoding="utf-8", newline="\n")
    return path
