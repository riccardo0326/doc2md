from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest

from doc2md.config import KelpieConfig, VisionConfig
from doc2md.converters.pdf.hard import KelpieHardExtractor
from doc2md.vision.kelpie import KelpieVisionBackend


@pytest.mark.kelpie
@pytest.mark.skipif(
    not os.environ.get("KELPIE_PROXY_BASE_URL"),
    reason="KELPIE_PROXY_BASE_URL is not configured",
)
def test_real_kelpie_describes_image() -> None:
    backend = KelpieVisionBackend(
        VisionConfig(
            backend="kelpie",
            kelpie=KelpieConfig(
                base_url=os.environ["KELPIE_PROXY_BASE_URL"],
                model=os.environ.get("KELPIE_MODEL", "DARE-NoCloud-Helios"),
            ),
        )
    )

    image_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
        "AScY42YAAAAASUVORK5CYII="
    )
    result = backend.describe_image(image_png, prompt_id="describe_image.v1")

    assert result.usage.total_tokens >= 0


@pytest.mark.kelpie
@pytest.mark.skipif(
    not os.environ.get("KELPIE_PROXY_BASE_URL"),
    reason="KELPIE_PROXY_BASE_URL is not configured",
)
def test_real_kelpie_transcribes_scanned_page() -> None:
    backend = KelpieVisionBackend(
        VisionConfig(
            backend="kelpie",
            kelpie=KelpieConfig(
                base_url=os.environ["KELPIE_PROXY_BASE_URL"],
                model=os.environ.get("KELPIE_MODEL", "DARE-NoCloud-Helios"),
            ),
        )
    )
    extractor = KelpieHardExtractor(
        backend,
        page_dpi=120,
        prompt_id="transcribe_page.v1",
    )

    blocks = extractor.extract(Path("tests/fixtures/synthetic/phase1_image_only.pdf"), [1])[1]

    assert blocks
    assert all(block.provenance.page == 1 for block in blocks)
    assert all(block.provenance.source == "vision" for block in blocks)
