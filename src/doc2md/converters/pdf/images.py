from __future__ import annotations

import hashlib
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from ...cache import DiskCache, vision_cache_key
from ...config import ImageConfig
from ...errors import VisionError
from ...models import ImageBlockDraft, ImageRecord
from ...vision.base import VisionBackend, VisionResult


@dataclass(frozen=True)
class ImageCandidate:
    image_id: str
    page: int
    png: bytes | None
    width_px: int
    height_px: int
    sha256: str
    bbox: dict[str, float] | None
    skip_reason: Literal["too_small", "bad_aspect", "duplicate"] | None = None
    canonical_image_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ImageProcessingResult:
    records: list[ImageRecord]
    blocks: list[ImageBlockDraft]
    vision_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tokens_estimated: bool
    cache_hits: int = 0
    cache_misses: int = 0
    calls: list[tuple[str, VisionResult]] = field(default_factory=list)


def _render_crop(pdfium_document: Any, page_number: int, image: dict[str, Any], dpi: int) -> bytes:
    page = pdfium_document[page_number - 1]
    try:
        scale = dpi / 72.0
        bitmap = page.render(scale=scale)
        rendered = bitmap.to_pil().convert("RGB")
        x0 = float(image["x0"]) * scale
        x1 = float(image["x1"]) * scale
        top = float(image.get("top", float(page.get_size()[1]) - float(image["y1"]))) * scale
        bottom = float(image.get("bottom", float(page.get_size()[1]) - float(image["y0"]))) * scale
        left_px = max(0, min(rendered.width, round(x0)))
        right_px = max(left_px, min(rendered.width, round(x1)))
        top_px = max(0, min(rendered.height, round(top)))
        bottom_px = max(top_px, min(rendered.height, round(bottom)))
        crop = rendered.crop((left_px, top_px, right_px, bottom_px))
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        page.close()


def collect_images(
    page: Any,
    pdfium_document: Any,
    page_number: int,
    config: ImageConfig,
    seen: dict[str, str],
) -> list[ImageCandidate]:
    candidates: list[ImageCandidate] = []
    for index, image in enumerate(page.images or [], start=1):
        image_id = f"p{page_number:04d}-i{index:02d}"
        bbox = {key: float(image[key]) for key in ("x0", "y0", "x1", "y1") if key in image}
        try:
            png = _render_crop(pdfium_document, page_number, image, config.render_dpi)
            from PIL import Image

            with Image.open(BytesIO(png)) as rendered:
                width_px, height_px = rendered.size
        except Exception as error:  # noqa: BLE001 - image failures are isolated
            candidates.append(
                ImageCandidate(
                    image_id=image_id,
                    page=page_number,
                    png=None,
                    width_px=0,
                    height_px=0,
                    sha256="",
                    bbox=bbox or None,
                    error=f"{type(error).__name__}: {error}",
                )
            )
            continue

        area = width_px * height_px
        if (
            width_px < config.min_width_px
            or height_px < config.min_height_px
            or area < config.min_area_px
        ):
            candidates.append(
                ImageCandidate(
                    image_id=image_id,
                    page=page_number,
                    png=png,
                    width_px=width_px,
                    height_px=height_px,
                    sha256=hashlib.sha256(png).hexdigest(),
                    bbox=bbox or None,
                    skip_reason="too_small",
                )
            )
            continue

        aspect = max(width_px / height_px, height_px / width_px)
        digest = hashlib.sha256(png).hexdigest()
        stream = image.get("stream")
        dedupe_digest = digest
        if stream is not None and hasattr(stream, "get_data"):
            dedupe_digest = hashlib.sha256(stream.get_data()).hexdigest()
        if aspect > config.max_aspect:
            skip_reason: Literal["too_small", "bad_aspect", "duplicate"] | None = "bad_aspect"
            canonical = None
        elif dedupe_digest in seen:
            skip_reason = "duplicate"
            canonical = seen[dedupe_digest]
        else:
            skip_reason = None
            canonical = None
            seen[dedupe_digest] = image_id
        candidates.append(
            ImageCandidate(
                image_id=image_id,
                page=page_number,
                png=png,
                width_px=width_px,
                height_px=height_px,
                sha256=digest,
                bbox=bbox or None,
                skip_reason=skip_reason,
                canonical_image_id=canonical,
            )
        )
    return candidates


def _figure_draft(record: ImageRecord, text: str, data_uri: str | None = None) -> ImageBlockDraft:
    source = record.path or data_uri or ""
    markdown = (
        f"![Figure {record.image_id}]({source})\n"
        f"> **Image description ({record.image_id}):** {text}"
    )
    return ImageBlockDraft(
        image_id=record.image_id,
        page=record.page,
        markdown=markdown,
        text=text,
        source_path=record.path,
    )


def process_images(
    candidates: list[ImageCandidate],
    backend: VisionBackend,
    *,
    prompt_id: str,
    max_workers: int,
    output_dir: Path | None,
    cache: DiskCache | None = None,
    describe: bool = True,
    cache_config: object | None = None,
) -> ImageProcessingResult:
    records_by_id: dict[str, ImageRecord] = {}
    canonical_candidates = [
        candidate
        for candidate in candidates
        if candidate.error is None and candidate.skip_reason is None and candidate.png is not None
    ]
    paths_by_id: dict[str, str | None] = {}
    data_uris_by_id: dict[str, str] = {}
    if output_dir is not None and canonical_candidates:
        (output_dir / "images").mkdir(parents=True, exist_ok=True)

    for candidate in canonical_candidates:
        data_uri = "data:image/png;base64," + __import__("base64").b64encode(
            candidate.png or b""
        ).decode("ascii")
        data_uris_by_id[candidate.image_id] = data_uri
        path: str | None = None
        if output_dir is not None:
            asset_path = output_dir / "images" / f"{candidate.image_id}.png"
            asset_path.write_bytes(candidate.png or b"")
            path = str(asset_path.relative_to(output_dir)).replace("\\", "/")
        paths_by_id[candidate.image_id] = path

    def describe_candidate(candidate: ImageCandidate) -> tuple[VisionResult, bool]:
        if cache is not None:
            key = vision_cache_key(
                candidate.sha256,
                prompt_id,
                getattr(backend, "model", "unknown"),
                cache_config if cache_config is not None else {"max_workers": max_workers},
            )
            cached = cache.get("vision-image", key)
            if cached is not None:
                return VisionResult.model_validate(cached), True
        result = backend.describe_image(candidate.png or b"", prompt_id=prompt_id)
        if not result.text.strip():
            raise VisionError(f"vision returned an empty description for {candidate.image_id}")
        if cache is not None:
            cache.put(
                "vision-image",
                key,
                result.model_dump(mode="json"),
            )
        return result, False

    descriptions: dict[str, tuple[VisionResult, bool] | Exception] = {}
    cache_hits = cache_misses = 0
    if canonical_candidates and describe:
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            futures: dict[Future[tuple[VisionResult, bool]], ImageCandidate] = {
                executor.submit(describe_candidate, candidate): candidate
                for candidate in canonical_candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    description = future.result()
                    descriptions[candidate.image_id] = description
                    if description[1]:
                        cache_hits += 1
                    else:
                        cache_misses += 1
                except Exception as error:  # noqa: BLE001 - image failures are isolated
                    descriptions[candidate.image_id] = error
                    cache_misses += 1

    records: list[ImageRecord] = []
    drafts: list[ImageBlockDraft] = []
    calls: list[tuple[str, VisionResult]] = []
    input_tokens = output_tokens = total_tokens = 0
    tokens_estimated = False
    for candidate in candidates:
        base: dict[str, Any] = {
            "image_id": candidate.image_id,
            "page": candidate.page,
            "width_px": candidate.width_px,
            "height_px": candidate.height_px,
            "sha256": candidate.sha256,
            "bbox": candidate.bbox,
        }
        if candidate.error is not None:
            records.append(ImageRecord(status="failed", **base))
            continue
        if candidate.skip_reason is not None:
            canonical_id = candidate.canonical_image_id
            canonical = records_by_id.get(canonical_id or "")
            record = ImageRecord(
                status="skipped",
                skip_reason=candidate.skip_reason,
                canonical_image_id=canonical_id,
                path=canonical.path if canonical else None,
                description=canonical.description if canonical else None,
                **base,
            )
            records.append(record)
            if candidate.skip_reason == "duplicate" and canonical and canonical.description:
                drafts.append(_figure_draft(record, canonical.description))
            continue

        if not describe:
            record = ImageRecord(
                status="skipped",
                skip_reason="vision_disabled",
                path=paths_by_id[candidate.image_id],
                **base,
            )
            records.append(record)
            drafts.append(_figure_draft(record, "Vision description disabled for this pipeline."))
            records_by_id[candidate.image_id] = record
            continue

        result = descriptions[candidate.image_id]
        if isinstance(result, Exception):
            record = ImageRecord(status="failed", path=paths_by_id[candidate.image_id], **base)
            records.append(record)
            drafts.append(
                ImageBlockDraft(
                    image_id=candidate.image_id,
                    page=candidate.page,
                    markdown=f"<!-- image {candidate.image_id}: description failed -->",
                    text="",
                    source_path=record.path,
                )
            )
            records_by_id[candidate.image_id] = record
            continue

        assert not isinstance(result, Exception)
        vision_result, _cache_hit = result
        if not _cache_hit:
            calls.append((candidate.image_id, vision_result))
        usage = vision_result.usage
        record = ImageRecord(
            status="described",
            path=paths_by_id[candidate.image_id],
            description=vision_result.text,
            usage=usage,
            **base,
        )
        records.append(record)
        records_by_id[candidate.image_id] = record
        drafts.append(
            _figure_draft(record, vision_result.text, data_uris_by_id[candidate.image_id])
        )
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        total_tokens += usage.total_tokens
        tokens_estimated = tokens_estimated or usage.estimated

    return ImageProcessingResult(
        records=records,
        blocks=drafts,
        vision_calls=len(canonical_candidates),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        tokens_estimated=tokens_estimated,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        calls=calls,
    )
