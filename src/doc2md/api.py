from __future__ import annotations

import hashlib
import importlib.metadata
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import pdfplumber

from .cache import DiskCache, docling_cache_key, vision_cache_key
from .config import Config, config_hash
from .converters.pdf.fast import extract_page
from .converters.pdf.hard import DoclingExtractor, KelpieHardExtractor
from .converters.pdf.images import collect_images, process_images
from .converters.pdf.margins import detect_repeated_margins, strip_repeated_margins
from .converters.pdf.router import classify
from .converters.pdf.signals import compute_signals
from .errors import ConfigError, ConversionFailed, HardExtractionError, SourceError
from .metrics import MetricsCollector
from .models import (
    Block,
    ConversionResult,
    ConvertedDocument,
    PageResult,
    PageStat,
    Provenance,
    RouteDecision,
    RunStats,
    SourceInfo,
    ToolInfo,
)
from .render.markdown import render_markdown
from .render.sidecar import write_document, write_run
from .vision.base import VisionBackend, VisionResult
from .vision.factory import build_vision_backend


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


def _render_page(pdfium_document: object, page_number: int, dpi: int) -> bytes:
    page = pdfium_document[page_number - 1]  # type: ignore[index]
    try:
        bitmap = page.render(scale=dpi / 72.0)
        image = bitmap.to_pil().convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        page.close()


def _vision_block(page: int, result: VisionResult) -> Block:
    return Block(
        block_id=f"p{page:04d}-b001",
        type="paragraph",
        markdown=result.text.strip(),
        text=result.text.strip(),
        provenance=Provenance(page=page, source="vision"),
    )


def _blocks_from_cache(value: dict[str, object]) -> list[Block]:
    raw_blocks = value.get("blocks", [])
    if not isinstance(raw_blocks, list):
        return []
    return [Block.model_validate(item) for item in raw_blocks if isinstance(item, dict)]


def _record_hard_calls(hard_extractor: object, collector: MetricsCollector) -> None:
    drain_calls = getattr(hard_extractor, "drain_calls", None)
    if not callable(drain_calls):
        return
    for call_id, call_result in drain_calls():
        collector.record_call("transcribe_page", call_id, call_result)


def _backend(context: object | None, config: Config, required: bool) -> VisionBackend | None:
    supplied = getattr(context, "vision", None) if context is not None else None
    if supplied is not None:
        return cast(VisionBackend, supplied)
    return build_vision_backend(config.vision) if required else None


def convert(
    source: str | Path,
    out_dir: str | Path | None = None,
    *,
    pipeline: str = "tiered",
    config: Config | None = None,
    pages: tuple[int, ...] | None = None,
    context: object | None = None,
    strict: bool = False,
    no_cache: bool = False,
) -> ConversionResult:
    if pipeline not in {"tiered", "full-vision", "docling-only"}:
        raise ConfigError(f"unknown pipeline: {pipeline}")

    source_path = Path(source)
    if not source_path.is_file():
        raise SourceError(f"source does not exist: {source_path}")
    effective_config = config or Config()
    effective_config_hash = config_hash(effective_config)
    source_hash = _sha256(source_path)
    started = datetime.now(timezone.utc)
    started_counter = time.perf_counter()
    page_results: list[PageResult] = []
    collector = MetricsCollector()
    warnings: list[str] = []
    requires_vision = pipeline == "full-vision" or (
        pipeline != "docling-only"
        and (effective_config.images.enabled or effective_config.hard.engine == "kelpie")
    )
    vision_backend = _backend(context, effective_config, requires_vision)
    hard_extractor = getattr(context, "hard", None) if context is not None else None
    if hard_extractor is None:
        if pipeline != "docling-only" and effective_config.hard.engine == "kelpie":
            if vision_backend is None:
                raise ConfigError("Kelpie hard path requires a vision backend")
            hard_extractor = KelpieHardExtractor(
                vision_backend,
                page_dpi=effective_config.hard.page_dpi,
                prompt_id=effective_config.vision.transcribe_prompt,
            )
        else:
            development_config = effective_config.hard.model_copy(
                update={"engine": "docling-dev-only"}
            )
            hard_extractor = DoclingExtractor(development_config)
    cache = DiskCache(
        effective_config.cache.dir,
        source_hash,
        enabled=effective_config.cache.enabled and not no_cache,
    )
    destination = Path(out_dir) / source_path.stem if out_dir is not None else None
    if destination is not None:
        destination.mkdir(parents=True, exist_ok=True)

    image_candidates = []
    seen_image_hashes: dict[str, str] = {}
    pdfium_document = None
    needs_pdfium = effective_config.images.enabled and pipeline != "full-vision"
    if needs_pdfium or pipeline == "full-vision":
        try:
            import pypdfium2 as pdfium

            pdfium_document = pdfium.PdfDocument(str(source_path))
        except Exception as error:  # noqa: BLE001 - page/image failures remain isolated
            warnings.append(f"page renderer unavailable: {type(error).__name__}: {error}")

    try:
        with pdfplumber.open(str(source_path)) as pdf:
            page_count = len(pdf.pages)
            source_info = SourceInfo(
                name=source_path.name,
                sha256=source_hash,
                size_bytes=source_path.stat().st_size,
                page_count=page_count,
            )
            selected_pages = _validate_pages(pages, page_count)
            margin_signatures = (
                detect_repeated_margins(
                    pdf.pages,
                    min_repetitions=effective_config.fast.repeated_margin_min_pages,
                    zone_ratio=effective_config.fast.margin_zone_ratio,
                )
                if effective_config.fast.strip_repeated_margins
                else None
            )
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
                    collector.record_page(
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
                decision: RouteDecision | None = None
                try:
                    decision = classify(
                        compute_signals(page, effective_config.router),
                        effective_config.router,
                        page=page_number,
                    )
                    page_class = decision.page_class
                    if pipeline == "full-vision":
                        if pdfium_document is None:
                            raise SourceError("page renderer unavailable for full-vision")
                        assert vision_backend is not None
                        key = vision_cache_key(
                            f"page:{page_number}",
                            effective_config.vision.transcribe_prompt,
                            getattr(vision_backend, "model", "unknown"),
                            effective_config.vision.model_dump(mode="json"),
                        )
                        cached = cache.get("vision-page", key)
                        if cached is not None:
                            vision_result = VisionResult.model_validate(cached)
                            collector.record_cache(hit=True)
                        else:
                            collector.record_cache(hit=False)
                            image_png = _render_page(
                                pdfium_document, page_number, effective_config.vision.page_dpi
                            )
                            vision_result = vision_backend.transcribe_page(
                                image_png,
                                prompt_id=effective_config.vision.transcribe_prompt,
                            )
                            cache.put("vision-page", key, vision_result.model_dump(mode="json"))
                            collector.record_call(
                                "transcribe_page", f"p{page_number:04d}", vision_result
                            )
                        result = PageResult(
                            page=page_number,
                            status="ok",
                            page_class=page_class,
                            method="vision",
                            blocks=[_vision_block(page_number, vision_result)],
                            warnings=["forced_pipeline:full-vision"],
                        )
                    else:
                        use_hard = pipeline == "docling-only" or page_class != "TEXT"
                        if use_hard:
                            use_kelpie_hard = (
                                pipeline != "docling-only"
                                and effective_config.hard.engine == "kelpie"
                            )
                            extraction_method: Literal["pdfplumber", "docling", "vision"] = (
                                "vision" if use_kelpie_hard else "docling"
                            )
                            fallback_warnings: list[str] = []
                            if use_kelpie_hard:
                                assert vision_backend is not None
                                key = vision_cache_key(
                                    f"hard-page:{page_number}",
                                    effective_config.vision.transcribe_prompt,
                                    getattr(vision_backend, "model", "unknown"),
                                    effective_config.vision.model_dump(mode="json"),
                                )
                                cache_stage = "vision-page"
                            else:
                                key = docling_cache_key(
                                    page_number,
                                    effective_config.hard.model_dump(mode="json"),
                                    _version("docling"),
                                )
                                cache_stage = "docling"
                            try:
                                cached = cache.get(cache_stage, key)
                                if cached is not None:
                                    hard_blocks = _blocks_from_cache(cached)
                                    collector.record_cache(hit=True)
                                else:
                                    collector.record_cache(hit=False)
                                    hard_started = time.perf_counter()
                                    hard_blocks = hard_extractor.extract(
                                        source_path, [page_number], context=context
                                    )[page_number]
                                    if extraction_method == "docling":
                                        collector.record_docling(time.perf_counter() - hard_started)
                                    _record_hard_calls(hard_extractor, collector)
                                    cache.put(
                                        cache_stage,
                                        key,
                                        {
                                            "blocks": [
                                                block.model_dump(mode="json")
                                                for block in hard_blocks
                                            ]
                                        },
                                    )
                            except HardExtractionError as error:
                                _record_hard_calls(hard_extractor, collector)
                                if not (
                                    pipeline == "tiered"
                                    and page_class == "COMPLEX"
                                    and decision.signals.has_text_layer
                                ):
                                    raise
                                hard_blocks = extract_page(
                                    page,
                                    page_number,
                                    effective_config.fast,
                                    margin_signatures,
                                )
                                if not hard_blocks:
                                    raise
                                extraction_method = "pdfplumber"
                                fallback_warnings = [
                                    "hard_path_fallback: "
                                    f"{type(error).__name__}: {error}"
                                ]
                                warnings.append(f"page {page_number} used hard_path_fallback")
                            result_warnings = [
                                "forced_pipeline:docling-only"
                                if pipeline == "docling-only"
                                else f"routed_to_hard_path:{','.join(decision.reasons)}"
                            ]
                            if extraction_method == "vision":
                                result_warnings.append("hard_path:kelpie")
                            result = PageResult(
                                page=page_number,
                                status="ok",
                                page_class=page_class,
                                method=extraction_method,
                                blocks=hard_blocks,
                                warnings=[*result_warnings, *fallback_warnings],
                            )
                        else:
                            result = PageResult(
                                page=page_number,
                                status="ok",
                                page_class=page_class,
                                method="pdfplumber",
                                blocks=extract_page(
                                    page,
                                    page_number,
                                    effective_config.fast,
                                    margin_signatures,
                                ),
                            )
                except Exception as error:  # noqa: BLE001 - page failures are isolated
                    result = PageResult(
                        page=page_number,
                        status="failed",
                        page_class=decision.page_class if decision is not None else "TEXT",
                        method=None,
                        error=f"{type(error).__name__}: {error}",
                    )
                    warnings.append(f"page {page_number} failed")

                if (
                    pdfium_document is not None
                    and effective_config.images.enabled
                    and pipeline != "full-vision"
                    and result.status == "ok"
                    and result.page_class != "SCANNED"
                ):
                    image_candidates.extend(
                        collect_images(
                            page,
                            pdfium_document,
                            page_number,
                            effective_config.images,
                            seen_image_hashes,
                        )
                    )
                duration = time.perf_counter() - page_started
                page_results.append(result)
                collector.record_page(
                    PageStat(
                        page=page_number,
                        status=result.status,
                        page_class=result.page_class,
                        method=result.method,
                        duration_s=duration,
                        reasons=decision.reasons if decision is not None else [],
                    )
                )
    except Exception as error:  # noqa: BLE001 - source failures become SourceError
        raise SourceError(f"unable to read PDF: {error}") from error
    finally:
        if pdfium_document is not None:
            pdfium_document.close()

    if effective_config.fast.strip_repeated_margins:
        page_results = strip_repeated_margins(
            page_results,
            min_repetitions=effective_config.fast.repeated_margin_min_pages,
            signatures=margin_signatures,
        )

    image_records = []
    if image_candidates:
        image_result = process_images(
            image_candidates,
            cast(VisionBackend, vision_backend),
            prompt_id=effective_config.vision.describe_prompt,
            max_workers=effective_config.vision.max_workers,
            output_dir=destination,
            cache=cache,
            describe=pipeline != "docling-only",
            cache_config=effective_config.vision.model_dump(mode="json"),
        )
        image_records = image_result.records
        for image_id, image_call in image_result.calls:
            collector.record_call("describe_image", image_id, image_call)
        for _ in range(image_result.cache_hits):
            collector.record_cache(hit=True)
        for _ in range(image_result.cache_misses):
            collector.record_cache(hit=False)
        for draft in image_result.blocks:
            page_result = page_results[draft.page - 1]
            if page_result.status == "failed":
                continue
            block = Block(
                block_id=f"p{draft.page:04d}-b{len(page_result.blocks) + 1:03d}",
                type="figure",
                markdown=draft.markdown,
                text=draft.text,
                provenance=Provenance(page=draft.page, source="vision"),
                meta={"image_id": draft.image_id},
            )
            page_results[draft.page - 1] = page_result.model_copy(
                update={"blocks": [*page_result.blocks, block]}
            )

    failed_count = sum(result.status == "failed" for result in page_results)
    if strict and failed_count:
        raise ConversionFailed(f"{failed_count} page(s) failed")

    tool = ToolInfo(
        doc2md="0.1.0",
        pdfplumber=_version("pdfplumber"),
        docling=_version("docling", fallback="not-installed"),
        pypdfium2=_version("pypdfium2", fallback="not-installed"),
        config_hash=effective_config_hash,
    )
    document = ConvertedDocument(
        source=source_info,
        pipeline=pipeline,
        pages=page_results,
        images=image_records,
        tool=tool,
    )
    markdown = render_markdown(
        document,
        page_markers=effective_config.render.page_markers,
        block_anchors=effective_config.render.block_anchors,
    )
    finished = datetime.now(timezone.utc)
    input_tokens = sum(call.input_tokens for call in collector.calls)
    output_tokens = sum(call.output_tokens for call in collector.calls)
    total_tokens = sum(call.total_tokens for call in collector.calls)
    stats = RunStats(
        run_id=str(uuid4()),
        started_at=started,
        finished_at=finished,
        pipeline=pipeline,
        source=source_info,
        config_hash=effective_config_hash,
        wall_time_s=time.perf_counter() - started_counter,
        pages=sorted(collector.pages, key=lambda item: item.page),
        pages_failed=failed_count,
        vision_calls=len(collector.calls),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        tokens_estimated=any(call.estimated for call in collector.calls),
        calls=collector.calls,
        cache_hits=collector.cache_hits,
        cache_misses=collector.cache_misses,
        docling_pages=collector.docling_pages,
        docling_time_s=collector.docling_time_s,
        warnings=warnings,
    )

    markdown_path: Path | None = None
    json_path: Path | None = None
    run_path: Path | None = None
    if out_dir is not None:
        assert destination is not None
        markdown_path = destination / f"{source_path.stem}.md"
        json_path = destination / f"{source_path.stem}.json"
        run_path = destination / "run.json"
        markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
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
