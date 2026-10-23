from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ..models import Usage


class VisionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    usage: Usage
    model: str
    latency_s: float
    request_id: str | None = None


class VisionBackend(Protocol):
    name: str
    model: str

    def describe_image(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult: ...

    def transcribe_page(
        self, image_png: bytes, *, prompt_id: str, lang: str = "auto"
    ) -> VisionResult: ...
