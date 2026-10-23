from __future__ import annotations

from ..config import VisionConfig
from ..errors import ConfigError
from .base import VisionBackend
from .fake import FakeVisionBackend
from .kelpie import KelpieVisionBackend


def build_vision_backend(config: VisionConfig) -> VisionBackend:
    if config.backend == "fake":
        return FakeVisionBackend()
    if config.backend == "kelpie":
        return KelpieVisionBackend(config)
    raise ConfigError(f"unknown vision backend: {config.backend}")
