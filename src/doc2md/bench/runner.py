from __future__ import annotations

import csv
import json
import platform
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable
from uuid import uuid4

from ..api import convert
from ..config import CacheConfig, Config
from ..converters.pdf.hard import DoclingExtractor
from ..errors import ConfigError
from ..models import ConversionResult
from ..vision.factory import build_vision_backend
from .baseline_current import BaselineAdapter, FakeBaselineAdapter
from .pipelines import validate_pipelines
from .suite import BenchmarkSuite, load_suite

RESULT_COLUMNS = [
    "run_id",
    "doc_id",
    "pipeline",
    "rep",
    "pages_total",
    "pages_text",
    "pages_complex",
    "pages_scanned",
    "pages_failed",
    "images_found",
    "images_described",
    "images_skipped",
    "vision_calls",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "tokens_estimated",
    "docling_pages",
    "wall_time_s",
    "time_easy_pages_s",
    "time_hard_pages_s",
    "output_chars",
    "cache_hits",
    "error",
]

ContextFactory = Callable[[], object]
BaselineFactory = Callable[[], BaselineAdapter]


def _timestamped_dir(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate = root / stamp
    suffix = 1
    while candidate.exists():
        candidate = root / f"{stamp}-{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _default_context(config: Config) -> object:
    return SimpleNamespace(
        vision=build_vision_backend(config.vision),
        hard=DoclingExtractor(config.hard),
    )


def _conversion_row(
    result: ConversionResult,
    doc_id: str,
    pipeline: str,
    rep: int,
) -> dict[str, object]:
    pages = result.document.pages
    images = result.document.images
    return {
        "run_id": result.stats.run_id,
        "doc_id": doc_id,
        "pipeline": pipeline,
        "rep": rep,
        "pages_total": len(pages),
        "pages_text": sum(page.page_class == "TEXT" for page in pages),
        "pages_complex": sum(page.page_class == "COMPLEX" for page in pages),
        "pages_scanned": sum(page.page_class == "SCANNED" for page in pages),
        "pages_failed": result.stats.pages_failed,
        "images_found": len(images),
        "images_described": sum(image.status == "described" for image in images),
        "images_skipped": sum(image.status == "skipped" for image in images),
        "vision_calls": result.stats.vision_calls,
        "input_tokens": result.stats.input_tokens,
        "output_tokens": result.stats.output_tokens,
        "total_tokens": result.stats.total_tokens,
        "tokens_estimated": result.stats.tokens_estimated,
        "docling_pages": result.stats.docling_pages,
        "wall_time_s": result.stats.wall_time_s,
        "time_easy_pages_s": sum(
            page.duration_s for page in result.stats.pages if page.page_class == "TEXT"
        ),
        "time_hard_pages_s": sum(
            page.duration_s for page in result.stats.pages if page.page_class != "TEXT"
        ),
        "output_chars": len(result.markdown),
        "cache_hits": result.stats.cache_hits,
        "error": "",
    }


def _baseline_row(
    result: object,
    source: Path,
    doc_id: str,
    pipeline: str,
    rep: int,
) -> dict[str, object]:
    baseline = result
    markdown = Path(getattr(baseline, "markdown_path")).read_text(encoding="utf-8")
    usage = getattr(baseline, "usage", None)
    return {
        "run_id": str(uuid4()),
        "doc_id": doc_id,
        "pipeline": pipeline,
        "rep": rep,
        "pages_total": getattr(baseline, "pages", ""),
        "pages_text": "",
        "pages_complex": "",
        "pages_scanned": "",
        "pages_failed": "",
        "images_found": "",
        "images_described": "",
        "images_skipped": "",
        "vision_calls": "",
        "input_tokens": usage.input_tokens if usage else "",
        "output_tokens": usage.output_tokens if usage else "",
        "total_tokens": usage.total_tokens if usage else "",
        "tokens_estimated": usage.estimated if usage else "",
        "docling_pages": "",
        "wall_time_s": getattr(baseline, "wall_time_s"),
        "time_easy_pages_s": "",
        "time_hard_pages_s": "",
        "output_chars": len(markdown),
        "cache_hits": "",
        "error": "",
    }


def _write_environment(path: Path, config: Config) -> None:
    payload = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "config_hash": __import__("doc2md.config", fromlist=["config_hash"]).config_hash(config),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_benchmark(
    suite: str | Path | BenchmarkSuite,
    *,
    output_dir: str | Path = "bench_runs",
    pipelines: list[str] | tuple[str, ...] | None = None,
    repetitions: int | None = None,
    config: Config | None = None,
    context_factory: ContextFactory | None = None,
    baseline_factory: BaselineFactory | None = None,
) -> Path:
    if isinstance(suite, BenchmarkSuite):
        suite_path = None
        loaded = suite
    else:
        suite_path = Path(suite)
        loaded = load_suite(suite_path)
    selected = validate_pipelines(
        list(pipelines) if pipelines is not None else [item.name for item in loaded.pipelines]
    )
    reps = repetitions if repetitions is not None else loaded.repetitions
    if reps < 1:
        raise ConfigError("benchmark repetitions must be at least 1")
    effective_config = config or Config()
    run_dir = _timestamped_dir(Path(output_dir))
    (run_dir / "outputs").mkdir()
    if suite_path is not None:
        shutil.copyfile(suite_path, run_dir / "suite.toml")
    _write_environment(run_dir / "env.json", effective_config)
    rows: list[dict[str, object]] = []

    for document in loaded.documents:
        if not document.path.is_file():
            raise ConfigError(f"benchmark document does not exist: {document.path}")
        for pipeline in selected:
            for rep in range(1, reps + 1):
                output_path = run_dir / "outputs" / document.id / pipeline / f"rep{rep}"
                output_path.mkdir(parents=True)
                cache_root = (
                    run_dir / "cache" / document.id / pipeline / f"rep{rep}"
                    if loaded.cold_cache
                    else run_dir / "cache" / "shared"
                )
                run_config = effective_config.model_copy(
                    update={"cache": CacheConfig(enabled=True, dir=str(cache_root))}
                )
                started = time.perf_counter()
                try:
                    if pipeline == "baseline_current":
                        adapter = (
                            baseline_factory()
                            if baseline_factory is not None
                            else FakeBaselineAdapter()
                        )
                        baseline_result = adapter.run(document.path, output_path)
                        row = _baseline_row(
                            baseline_result, document.path, document.id, pipeline, rep
                        )
                    else:
                        context = (
                            context_factory()
                            if context_factory is not None
                            else _default_context(run_config)
                        )
                        result = convert(
                            document.path,
                            output_path,
                            pipeline=pipeline,
                            config=run_config,
                            context=context,
                        )
                        row = _conversion_row(result, document.id, pipeline, rep)
                except Exception as error:  # noqa: BLE001 - benchmark records isolated errors
                    row = {column: "" for column in RESULT_COLUMNS}
                    row.update(
                        {
                            "run_id": str(uuid4()),
                            "doc_id": document.id,
                            "pipeline": pipeline,
                            "rep": rep,
                            "wall_time_s": time.perf_counter() - started,
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
                rows.append(row)

    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return run_dir
