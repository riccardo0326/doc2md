from __future__ import annotations

import hashlib
import importlib.metadata
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pdfplumber

from .config import Config, config_hash
from .converters.pdf.fast import extract_page
from .converters.pdf.router import classify
from .converters.pdf.signals import compute_signals
from .errors import ConfigError, ConversionFailed, SourceError
from .models import (
    ConversionResult,
    ConvertedDocument,
    PageResult,
    PageStat,
    RouteDecision,
    RunStats,
    SourceInfo,
    ToolInfo,
)
from .render.markdown import render_markdown
from .render.sidecar import write_document, write_run


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version(package: str, fallback: str = "unknown") -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return fallback


def _validate_pages(pages: tuple[int, ...] | None, page_count: int) -> set[int]:
    if pages is None:
        return set(range(1, page_count + 1))
    selected = set(pages)
    if not selected or any(page < 1 or page > page_count for page in selected):
        raise ConfigError("pages must contain valid 1-based page numbers")
    return selected


def convert(
    source: str | Path,
    out_dir: str | Path | None = None,
    *,
    pipeline: str = "tiered",
    config: Config | None = None,
    pages: tuple[int, ...] | None = None,
    context: object | None = None,
    strict: bool = False,
) -> ConversionResult:
    del context
    if pipeline != "tiered":
        raise ConfigError("Phase 1 supports only the 'tiered' pipeline")

    source_path = Path(source)
    if not source_path.is_file():
        raise SourceError(f"source does not exist: {source_path}")
    effective_config = config or Config()
    effective_config_hash = config_hash(effective_config)
    started = datetime.now(timezone.utc)
    started_counter = time.perf_counter()
    source_info: SourceInfo
    page_results: list[PageResult] = []
    page_stats: list[PageStat] = []
    warnings: list[str] = []

    try:
        with pdfplumber.open(str(source_path)) as pdf:
            page_count = len(pdf.pages)
            source_info = SourceInfo(
                name=source_path.name,
                sha256=_sha256(source_path),
                size_bytes=source_path.stat().st_size,
                page_count=page_count,
            )
            selected_pages = _validate_pages(pages, page_count)
            for page_number, page in enumerate(pdf.pages, start=1):
                if page_number not in selected_pages:
                    result = PageResult(
                        page=page_number,
                        status="skipped",
                        page_class=None,
                        method=None,
                        warnings=["page_not_selected"],
                    )
                    page_results.append(result)
                    page_stats.append(
                        PageStat(
                            page=page_number,
                            status="skipped",
                            page_class=None,
                            method=None,
                            duration_s=0.0,
                        )
                    )
                    continue

                page_started = time.perf_counter()
                try:
                    decision = classify(
                        compute_signals(page, effective_config.router),
                        effective_config.router,
                        page=page_number,
                    )
                    if decision.page_class == "TEXT":
                        result = PageResult(
                            page=page_number,
                            status="ok",
                            page_class=decision.page_class,
                            method="pdfplumber",
                            blocks=extract_page(page, page_number),
                        )
                    else:
                        result = PageResult(
                            page=page_number,
                            status="ok",
                            page_class=decision.page_class,
                            method=None,
                            warnings=[f"routed_to_hard_path:{','.join(decision.reasons)}"],
                        )
                except Exception as error:  # noqa: BLE001 - page failures are isolated
                    result = PageResult(
                        page=page_number,
                        status="failed",
                        page_class="TEXT",
                        method=None,
                        error=f"{type(error).__name__}: {error}",
                    )
                    warnings.append(f"page {page_number} failed")
                duration = time.perf_counter() - page_started
                page_results.append(result)
                page_stats.append(
                    PageStat(
                        page=page_number,
                        status=result.status,
                        page_class=result.page_class,
                        method=result.method,
                        duration_s=duration,
                    )
                )
    except Exception as error:  # noqa: BLE001 - source failures become SourceError
        raise SourceError(f"unable to read PDF: {error}") from error

    failed_count = sum(result.status == "failed" for result in page_results)
    if strict and failed_count:
        raise ConversionFailed(f"{failed_count} page(s) failed")

    tool = ToolInfo(
        doc2md="0.1.0",
        pdfplumber=_version("pdfplumber"),
        config_hash=effective_config_hash,
    )
    document = ConvertedDocument(
        source=source_info,
        pipeline=pipeline,
        pages=page_results,
        tool=tool,
    )
    markdown = render_markdown(
        document,
        page_markers=effective_config.render.page_markers,
        block_anchors=effective_config.render.block_anchors,
    )
    finished = datetime.now(timezone.utc)
    stats = RunStats(
        run_id=str(uuid4()),
        started_at=started,
        finished_at=finished,
        pipeline=pipeline,
        source=source_info,
        config_hash=effective_config_hash,
        wall_time_s=time.perf_counter() - started_counter,
        pages=page_stats,
        pages_failed=failed_count,
        warnings=warnings,
    )

    markdown_path: Path | None = None
    json_path: Path | None = None
    run_path: Path | None = None
    if out_dir is not None:
        destination = Path(out_dir) / source_path.stem
        destination.mkdir(parents=True, exist_ok=True)
        markdown_path = destination / f"{source_path.stem}.md"
        json_path = destination / f"{source_path.stem}.json"
        run_path = destination / "run.json"
        with markdown_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)
        write_document(json_path, document)
        write_run(run_path, stats)

    return ConversionResult(
        document=document,
        markdown=markdown,
        markdown_path=markdown_path,
        json_path=json_path,
        run_path=run_path,
        stats=stats,
    )


def inspect_pdf(source: str | Path, *, config: Config | None = None) -> list[RouteDecision]:
    source_path = Path(source)
    if not source_path.is_file():
        raise SourceError(f"source does not exist: {source_path}")
    effective_config = config or Config()
    try:
        with pdfplumber.open(str(source_path)) as pdf:
            return [
                classify(
                    compute_signals(page, effective_config.router),
                    effective_config.router,
                    page=page_number,
                )
                for page_number, page in enumerate(pdf.pages, start=1)
            ]
    except Exception as error:  # noqa: BLE001 - source failures become SourceError
        raise SourceError(f"unable to inspect PDF: {error}") from error
