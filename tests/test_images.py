from __future__ import annotations

import hashlib
from pathlib import Path

import pypdfium2 as pdfium

from doc2md import Config, convert
from doc2md.config import CacheConfig, ImageConfig, RouterConfig, VisionConfig
from doc2md.converters.pdf.images import collect_images, process_images
from doc2md.vision.fake import FakeVisionBackend


def test_image_stage_filters_deduplicates_and_describes(tmp_path: Path) -> None:
    source = Path("tests/fixtures/synthetic/phase5_embedded_images.pdf")
    config = Config(
        router=RouterConfig(complex_image_ratio=1.0),
        vision=VisionConfig(backend="fake", max_workers=1),
        cache=CacheConfig(dir=str(tmp_path / "cache")),
    )

    result = convert(source, tmp_path / "out", config=config)

    described = [image for image in result.document.images if image.status == "described"]
    skipped = [image for image in result.document.images if image.status == "skipped"]
    assert len(described) == 1
    assert {image.skip_reason for image in skipped} == {"duplicate", "too_small"}
    assert result.stats.vision_calls == 1
    assert result.stats.total_tokens == 20
    assert "[fake description of " in result.markdown
    assert len(list((tmp_path / "out" / "phase5_embedded_images" / "images").glob("*.png"))) == 1


def test_relative_area_filter_skips_decorative_image_before_vision(tmp_path: Path) -> None:
    source = Path("tests/fixtures/synthetic/phase5_embedded_images.pdf")
    config = Config(
        images=ImageConfig(
            min_width_px=1,
            min_height_px=1,
            min_area_px=1,
            min_page_area_ratio=0.02,
        ),
        router=RouterConfig(complex_image_ratio=1.0),
        vision=VisionConfig(backend="fake", max_workers=1),
        cache=CacheConfig(dir=str(tmp_path / "cache")),
    )

    result = convert(source, tmp_path / "out", config=config)

    described = [image for image in result.document.images if image.status == "described"]
    skipped = [image for image in result.document.images if image.status == "skipped"]
    assert len(described) == 1
    assert any(image.skip_reason == "too_small" for image in skipped)
    assert result.stats.vision_calls == 1


def test_image_failure_isolated_from_document(tmp_path: Path) -> None:
    source = Path("tests/fixtures/synthetic/phase5_embedded_images.pdf")
    import pdfplumber

    pdfium_document = pdfium.PdfDocument(str(source))
    try:
        with pdfplumber.open(str(source)) as pdf:
            candidates = collect_images(
                pdf.pages[0],
                pdfium_document,
                1,
                Config().images,
                {},
            )
    finally:
        pdfium_document.close()
    canonical = next(candidate for candidate in candidates if candidate.skip_reason is None)
    backend = FakeVisionBackend(fail_on={hashlib.sha256(canonical.png or b"").hexdigest()[:4]})

    result = process_images(
        candidates,
        backend,
        prompt_id="describe_image.v1",
        max_workers=1,
        output_dir=tmp_path,
    )

    assert any(record.status == "failed" for record in result.records)
    assert any("description failed" in block.markdown for block in result.blocks)
