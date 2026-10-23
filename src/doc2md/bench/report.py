from __future__ import annotations

import csv
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
    lines.extend(["", "## Notes", "", "- Results are grouped from the recorded repetitions.", ""])
    return "\n".join(lines)


def write_report(run_dir: str | Path) -> Path:
    directory = Path(run_dir)
    path = directory / "report.md"
    path.write_text(render_report(directory / "results.csv"), encoding="utf-8", newline="\n")
    return path
