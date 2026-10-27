from __future__ import annotations

import hashlib
import json
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field


class RenderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_markers: bool = True
    block_anchors: bool = False


class RouterConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_chars: int = 50
    min_chars_text_layer: int = 10
    scan_image_ratio: float = 0.6
    max_garbled: float = 0.02
    table_none_ratio: float = 0.15
    complex_image_ratio: float = 0.4
    image_page_min_chars: int = 400


class FastConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    heading_ratio: float = 1.25
    column_gutter_min_pt: float = 20.0
    strip_repeated_margins: bool = True
    repeated_margin_min_pages: int = Field(default=2, ge=2)


class HardConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine: str = "docling"
    languages: list[str] = Field(default_factory=lambda: ["en", "de"])
    threads: int = 4
    artifacts_path: str | None = None
    ocr: bool = True
    allow_remote_download: bool = False


class ImageConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    render_dpi: int = 150
    min_width_px: int = 64
    min_height_px: int = 64
    min_area_px: int = 10000
    min_page_area_ratio: float = Field(default=0.02, ge=0.0, le=1.0)
    max_aspect: float = 8.0


class KelpieConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str = ""
    model: str = ""


class VisionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str = "kelpie"
    max_workers: int = 1
    page_dpi: int = 150
    max_tokens: int = 800
    temperature: float = 0.0
    timeout_s: float = 120.0
    max_retries: int = 3
    describe_prompt: str = "describe_image.v1"
    transcribe_prompt: str = "transcribe_page.v1"
    kelpie: KelpieConfig = Field(default_factory=KelpieConfig)


class CacheConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    dir: str = ".doc2md_cache"


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    render: RenderConfig = Field(default_factory=RenderConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    fast: FastConfig = Field(default_factory=FastConfig)
    hard: HardConfig = Field(default_factory=HardConfig)
    images: ImageConfig = Field(default_factory=ImageConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


def config_hash(config: Config) -> str:
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def with_overrides(config: Config, overrides: Sequence[str]) -> Config:
    data = config.model_dump()
    for override in overrides:
        try:
            path, raw_value = override.split("=", 1)
            section, key = path.split(".", 1)
        except ValueError as error:
            message = f"invalid override: {override!r}; expected section.key=value"
            raise ValueError(message) from error
        section_config = getattr(config, section, None)
        if section_config is None or not hasattr(section_config, key):
            raise ValueError(f"unknown configuration override: {path}")
        current = getattr(section_config, key)
        if isinstance(current, bool):
            value: object = raw_value.lower() in {"1", "true", "yes", "on"}
        elif isinstance(current, int):
            value = int(raw_value)
        elif isinstance(current, float):
            value = float(raw_value)
        else:
            value = raw_value
        data[section][key] = value
    return Config.model_validate(data)
