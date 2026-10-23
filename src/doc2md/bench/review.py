from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class SamplePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str
    doc_id: str
    page: int
    page_class: str


@dataclass(frozen=True)
class ReviewPaths:
    csv_path: Path
    markdown_path: Path
    unblind_path: Path


def _tiered_pages(run_dir: Path) -> list[SamplePage]:
    samples: list[SamplePage] = []
    for sidecar in sorted((run_dir / "outputs").glob("*/tiered/rep1/*.json")):
        doc_id = sidecar.parents[2].name
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        for page in payload.get("pages", []):
            if page.get("status", "ok") == "skipped":
                continue
            samples.append(
                SamplePage(
                    sample_id=f"{doc_id}-p{int(page['page']):04d}",
                    doc_id=doc_id,
                    page=int(page["page"]),
                    page_class=str(page.get("page_class") or "TEXT"),
                )
            )
    return samples


def select_pages(run_dir: str | Path, n: int = 30, seed: int = 42) -> list[SamplePage]:
    if n < 1:
        raise ValueError("review sample size must be at least 1")
    samples = _tiered_pages(Path(run_dir))
    grouped = {
        page_class: sorted(
            (sample for sample in samples if sample.page_class == page_class),
            key=lambda sample: sample.sample_id,
        )
        for page_class in ("TEXT", "COMPLEX", "SCANNED")
    }
    available_classes = [page_class for page_class in grouped if grouped[page_class]]
    if not available_classes:
        return []
    base, remainder = divmod(n, len(available_classes))
    selected: list[SamplePage] = []
    rng = random.Random(seed)
    for index, page_class in enumerate(available_classes):
        count = min(len(grouped[page_class]), base + (index < remainder))
        selected.extend(rng.sample(grouped[page_class], count))
    if len(selected) < min(n, len(samples)):
        selected_ids = {sample.sample_id for sample in selected}
        remaining = [sample for sample in samples if sample.sample_id not in selected_ids]
        selected.extend(rng.sample(remaining, min(n - len(selected), len(remaining))))
    return sorted(selected, key=lambda sample: sample.sample_id)


def _pipelines(run_dir: Path) -> list[str]:
    return sorted(path.name for path in (run_dir / "outputs").glob("*/*") if path.is_dir())


def _page_text(run_dir: Path, doc_id: str, pipeline: str, page_number: int) -> str:
    candidates = sorted((run_dir / "outputs" / doc_id / pipeline / "rep1").glob("*.json"))
    if not candidates:
        return ""
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    page: dict[str, Any] = next(
        (item for item in payload.get("pages", []) if item.get("page") == page_number), {}
    )
    return "\n\n".join(block.get("markdown", "") for block in page.get("blocks", []))


def _page_image(run_dir: Path, sample: SamplePage) -> str:
    existing = run_dir / "review" / "page-images" / f"{sample.doc_id}-p{sample.page:04d}.png"
    if existing.is_file():
        return existing.relative_to(run_dir).as_posix()
    try:
        environment = json.loads((run_dir / "env.json").read_text(encoding="utf-8"))
        source = Path(environment.get("documents", {}).get(sample.doc_id, ""))
        if not source.is_file():
            return ""
        import pypdfium2 as pdfium

        image_dir = run_dir / "review" / "page-images"
        image_dir.mkdir(parents=True, exist_ok=True)
        document = pdfium.PdfDocument(str(source))
        page = document[sample.page - 1]
        try:
            bitmap = page.render(scale=150 / 72.0)
            bitmap.to_pil().convert("RGB").save(existing, format="PNG")
        finally:
            page.close()
            document.close()
        return existing.relative_to(run_dir).as_posix()
    except Exception:  # noqa: BLE001 - review assets must not abort sampling
        return ""


def write_review_sheet(run_dir: str | Path, n: int = 30, seed: int = 42) -> ReviewPaths:
    directory = Path(run_dir)
    review_dir = directory / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    samples = select_pages(directory, n=n, seed=seed)
    pipelines = _pipelines(directory)
    labels = [chr(ord("A") + index) for index in range(len(pipelines))]
    rng = random.Random(seed + 1)
    mapping: dict[str, dict[str, str]] = {}
    criteria = ("text", "special", "table", "figure", "order")
    fields = ["sample_id", "doc_id", "page", "page_class", "page_image_path"]
    fields.extend(f"output_{label}" for label in labels)
    fields.extend(f"{criterion}_{label}_score" for label in labels for criterion in criteria)
    csv_path = review_dir / "review_sheet.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sample in samples:
            order = list(pipelines)
            rng.shuffle(order)
            sample_mapping = {label: pipeline for label, pipeline in zip(labels, order)}
            mapping[sample.sample_id] = sample_mapping
            row: dict[str, Any] = {
                "sample_id": sample.sample_id,
                "doc_id": sample.doc_id,
                "page": sample.page,
                "page_class": sample.page_class,
                "page_image_path": _page_image(directory, sample),
            }
            row.update(
                {
                    f"output_{label}": _page_text(directory, sample.doc_id, pipeline, sample.page)
                    for label, pipeline in sample_mapping.items()
                }
            )
            row.update(
                {f"{criterion}_{label}_score": "" for label in labels for criterion in criteria}
            )
            writer.writerow(row)
    unblind_path = review_dir / "unblind_map.json"
    unblind_path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path = review_dir / "review_sheet.md"
    markdown_lines = [
        "# Blind Review Sheet",
        "",
        "Fill the score columns in `review_sheet.csv`.",
        "",
    ]
    for sample in samples:
        markdown_lines.extend(
            [
                f"## `{sample.sample_id}`",
                "",
                f"Page {sample.page}, class `{sample.page_class}`.",
                "",
            ]
        )
        for label, pipeline in mapping[sample.sample_id].items():
            markdown_lines.extend(
                [
                    f"### Candidate {label}",
                    "",
                    _page_text(directory, sample.doc_id, pipeline, sample.page),
                    "",
                ]
            )
    markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    return ReviewPaths(csv_path, markdown_path, unblind_path)
