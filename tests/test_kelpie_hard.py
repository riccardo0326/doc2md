from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from doc2md import Config, convert
from doc2md.config import CacheConfig, HardConfig, ImageConfig, VisionConfig
from doc2md.errors import VisionError
from doc2md.models import Usage
from doc2md.vision.base import VisionResult


class MarkdownVisionBackend:
    model = "DARE-NoCloud-Helios"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.transcribe_calls = 0

    def describe_image(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult:
        del image_png, prompt_id, lang
        return VisionResult(
            text="image",
            usage=Usage(input_tokens=1, output_tokens=1, total_tokens=2, estimated=True),
            model=self.model,
            latency_s=0.0,
        )

    def transcribe_page(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult:
        del image_png, prompt_id, lang
        self.transcribe_calls += 1
        if self.fail:
            raise VisionError("hard transcription failed")
        return VisionResult(
            text=(
                "# Scanned heading\n\n"
                "Recovered paragraph.\n\n"
                "- first item\n- second item\n\n"
                "| A | B |\n| --- | --- |\n| 1 | 2 |"
            ),
            usage=Usage(input_tokens=10, output_tokens=20, total_tokens=30, estimated=False),
            model=self.model,
            latency_s=0.25,
        )


def _config(cache_dir: Path | None = None) -> Config:
    return Config(
        hard=HardConfig(engine="kelpie"),
        images=ImageConfig(enabled=False),
        vision=VisionConfig(backend="fake"),
        cache=CacheConfig(enabled=cache_dir is not None, dir=str(cache_dir or ".cache")),
    )


def test_tiered_scanned_page_uses_kelpie_hard_path() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")
    backend = MarkdownVisionBackend()
    context = SimpleNamespace(vision=backend)

    result = convert(source, config=_config(), context=context)

    page = result.document.pages[0]
    assert page.status == "ok"
    assert page.page_class == "SCANNED"
    assert page.method == "vision"
    assert [block.type for block in page.blocks] == ["heading", "paragraph", "list", "table"]
    assert all(block.provenance.source == "vision" for block in page.blocks)
    assert result.stats.vision_calls == 1
    assert result.stats.total_tokens == 30
    assert backend.transcribe_calls == 1


def test_kelpie_hard_page_cache_avoids_second_call(tmp_path: Path) -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")
    backend = MarkdownVisionBackend()
    context = SimpleNamespace(vision=backend)
    config = _config(tmp_path / "cache")

    convert(source, config=config, context=context)
    second = convert(source, config=config, context=context)

    assert backend.transcribe_calls == 1
    assert second.stats.vision_calls == 0
    assert second.stats.total_tokens == 0
    assert second.stats.cache_hits >= 1


def test_kelpie_hard_failure_isolated_to_page() -> None:
    source = Path("tests/fixtures/synthetic/phase1_image_only.pdf")
    context = SimpleNamespace(vision=MarkdownVisionBackend(fail=True))

    result = convert(source, config=_config(), context=context)

    page = result.document.pages[0]
    assert page.status == "failed"
    assert page.error is not None
    assert "Kelpie hard transcription failed" in page.error
