from __future__ import annotations

import hashlib

from ..errors import VisionError
from ..models import Usage
from .base import VisionResult


class FakeVisionBackend:
    name = "fake"

    def __init__(self, *, model: str = "fake-vision", fail_on: set[str] | None = None) -> None:
        self.model = model
        self.fail_on = fail_on or set()

    def describe_image(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult:
        del prompt_id, lang
        digest = hashlib.sha256(image_png).hexdigest()
        if digest[:4] in self.fail_on:
            raise VisionError(f"fake vision failure for {digest[:8]}")
        return VisionResult(
            text=f"[fake description of {digest[:8]}]",
            usage=Usage(input_tokens=12, output_tokens=8, total_tokens=20, estimated=True),
            model=self.model,
            latency_s=0.0,
        )

    def transcribe_page(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult:
        return self.describe_image(image_png, prompt_id=prompt_id, lang=lang)
