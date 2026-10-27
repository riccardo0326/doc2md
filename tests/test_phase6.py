from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from doc2md import Config, convert
from doc2md.config import CacheConfig, HardConfig, ImageConfig, RouterConfig, VisionConfig
from doc2md.converters.pdf.hard import DoclingExtractor
from doc2md.vision.fake import FakeVisionBackend


class CountingVisionBackend(FakeVisionBackend):
    def __init__(self) -> None:
        super().__init__()
        self.describe_calls = 0
        self.transcribe_calls = 0

    def describe_image(self, image_png: bytes, *, prompt_id: str, lang: str = "auto"):
        self.describe_calls += 1
        return super().describe_image(image_png, prompt_id=prompt_id, lang=lang)

    def transcribe_page(self, image_png: bytes, *, prompt_id: str, lang: str = "auto"):
        self.transcribe_calls += 1
        return super().transcribe_page(image_png, prompt_id=prompt_id, lang=lang)


class CountingHardExtractor:
    name = "fake-docling"

    def __init__(self) -> None:
        self.calls: list[tuple[Path, tuple[int, ...]]] = []

    def extract(self, source: Path, pages: list[int], context: object | None = None):
        del context
        self.calls.append((source, tuple(pages)))
        return {page: [] for page in pages}


def _semantic_pdf(path: Path) -> None:
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(path), pagesize=letter)
    table = Table([["Item", "Value"], ["Alpha", "1"], ["Beta", "2"]], colWidths=[2 * inch] * 2)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    document.build(
        [
            Paragraph("A Report Heading", styles["Title"]),
            Spacer(1, 0.15 * inch),
            Paragraph("This is the first sentence of a paragraph.", styles["BodyText"]),
            Paragraph("This is the second sentence of the same paragraph.", styles["BodyText"]),
            Spacer(1, 0.1 * inch),
            Paragraph("- first bullet", styles["BodyText"]),
            Paragraph("- second bullet", styles["BodyText"]),
            Spacer(1, 0.1 * inch),
            table,
        ]
    )


def test_fast_path_preserves_semantic_reading_order(tmp_path: Path) -> None:
    source = tmp_path / "semantic.pdf"
    _semantic_pdf(source)
    config = Config(
        images=ImageConfig(enabled=False),
        router=RouterConfig(complex_image_ratio=1.0),
    )

    result = convert(source, config=config)
    blocks = result.document.pages[0].blocks

    assert [block.type for block in blocks] == ["heading", "paragraph", "list", "table"]
    assert blocks[0].markdown.startswith("# ")
    assert "first sentence" in blocks[1].text and "second sentence" in blocks[1].text
    assert blocks[2].markdown == "- first bullet\n- second bullet"
    assert "| Item | Value |" in blocks[3].markdown
    assert [block.provenance.page for block in blocks] == [1, 1, 1, 1]


def test_fast_path_separates_heading_from_close_body_text(tmp_path: Path) -> None:
    source = tmp_path / "close-heading.pdf"
    document = canvas.Canvas(str(source), pagesize=letter)
    document.setFont("Helvetica", 14)
    document.drawString(72, 700, "Section heading")
    document.setFont("Helvetica", 10)
    document.drawString(72, 680, "Body text starts after the heading.")
    document.drawString(72, 666, "The paragraph continues on the next line.")
    document.drawString(72, 652, "The paragraph has enough body text.")
    document.save()

    config = Config(images=ImageConfig(enabled=False))
    result = convert(source, config=config)

    blocks = result.document.pages[0].blocks
    assert [block.type for block in blocks] == ["heading", "paragraph"]
    assert blocks[0].text == "Section heading"
    assert blocks[1].text == (
        "Body text starts after the heading. The paragraph continues on the next line. "
        "The paragraph has enough body text."
    )


def test_fast_path_splits_inline_bullet_markers_into_list_items(tmp_path: Path) -> None:
    source = tmp_path / "inline-bullets.pdf"
    document = canvas.Canvas(str(source), pagesize=letter)
    document.setFont("Helvetica", 10)
    document.drawString(72, 700, "- first requirement - second requirement - third requirement")
    document.save()

    config = Config(images=ImageConfig(enabled=False))
    result = convert(source, config=config)

    blocks = result.document.pages[0].blocks
    assert len(blocks) == 1
    assert blocks[0].type == "list"
    assert blocks[0].markdown == "- first requirement\n- second requirement\n- third requirement"


def test_full_vision_uses_one_cached_page_call_per_page(text_pdf: Path, tmp_path: Path) -> None:
    backend = CountingVisionBackend()
    context = SimpleNamespace(vision=backend, hard=DoclingExtractor())
    config = Config(
        cache=CacheConfig(enabled=True, dir=str(tmp_path / "cache")),
        images=ImageConfig(enabled=False),
        vision=VisionConfig(backend="fake"),
    )

    first = convert(
        source=text_pdf,
        out_dir=tmp_path / "first",
        pipeline="full-vision",
        config=config,
        context=context,
    )
    second = convert(
        source=text_pdf,
        out_dir=tmp_path / "second",
        pipeline="full-vision",
        config=config,
        context=context,
    )

    assert backend.transcribe_calls == 3
    assert all(page.method == "vision" for page in first.document.pages)
    assert second.stats.vision_calls == 0
    assert second.stats.total_tokens == 0
    assert second.stats.cache_hits >= 3

    run = json.loads((tmp_path / "first" / "fixture" / "run.json").read_text(encoding="utf-8"))
    assert run["totals"]["vision"]["total_tokens"] == sum(
        call["total_tokens"] for call in run["calls"]
    )
    assert run["totals"]["vision"]["estimated"] is True


def test_no_cache_repeats_vision_calls(text_pdf: Path, tmp_path: Path) -> None:
    backend = CountingVisionBackend()
    context = SimpleNamespace(vision=backend, hard=DoclingExtractor())
    config = Config(
        cache=CacheConfig(enabled=True, dir=str(tmp_path / "cache")),
        images=ImageConfig(enabled=False),
        vision=VisionConfig(backend="fake"),
    )

    convert(text_pdf, tmp_path / "first", pipeline="full-vision", config=config, context=context)
    result = convert(
        text_pdf,
        tmp_path / "second",
        pipeline="full-vision",
        config=config,
        context=context,
        no_cache=True,
    )

    assert backend.transcribe_calls == 6
    assert result.stats.vision_calls == 3
    assert result.stats.cache_hits == 0


def test_output_affecting_config_invalidates_page_cache(text_pdf: Path, tmp_path: Path) -> None:
    backend = CountingVisionBackend()
    context = SimpleNamespace(vision=backend, hard=DoclingExtractor())
    base = Config(
        cache=CacheConfig(enabled=True, dir=str(tmp_path / "cache")),
        images=ImageConfig(enabled=False),
        vision=VisionConfig(backend="fake", page_dpi=150),
    )
    changed = base.model_copy(update={"vision": base.vision.model_copy(update={"page_dpi": 151})})

    convert(text_pdf, pipeline="full-vision", config=base, context=context)
    result = convert(text_pdf, pipeline="full-vision", config=changed, context=context)

    assert backend.transcribe_calls == 6
    assert result.stats.cache_hits == 0


def test_docling_only_forces_hard_without_vision(text_pdf: Path, tmp_path: Path) -> None:
    hard = CountingHardExtractor()
    backend = CountingVisionBackend()
    context = SimpleNamespace(vision=backend, hard=hard)
    config = Config(
        cache=CacheConfig(enabled=False),
        images=ImageConfig(enabled=False),
        hard=HardConfig(artifacts_path=str(tmp_path)),
    )

    result = convert(text_pdf, pipeline="docling-only", config=config, context=context)

    assert [page.method for page in result.document.pages] == ["docling"] * 3
    assert len(hard.calls) == 3
    assert backend.transcribe_calls == 0
    assert result.stats.total_tokens == 0


def test_image_description_cache_skips_the_second_kelpie_call(tmp_path: Path) -> None:
    source = Path("tests/fixtures/synthetic/phase5_embedded_images.pdf")
    backend = CountingVisionBackend()
    context = SimpleNamespace(vision=backend, hard=DoclingExtractor())
    config = Config(
        cache=CacheConfig(enabled=True, dir=str(tmp_path / "cache")),
        router=RouterConfig(complex_image_ratio=1.0),
        vision=VisionConfig(backend="fake"),
    )

    convert(source, tmp_path / "first", config=config, context=context)
    second = convert(source, tmp_path / "second", config=config, context=context)

    assert backend.describe_calls == 1
    assert second.stats.vision_calls == 0
    assert second.stats.cache_hits >= 1
