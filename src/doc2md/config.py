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


class HardConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    engine: str = "docling"
    languages: list[str] = Field(default_factory=lambda: ["en", "de"])
    threads: int = 4
    artifacts_path: str | None = None
    ocr: bool = True


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    render: RenderConfig = Field(default_factory=RenderConfig)
    router: RouterConfig = Field(default_factory=RouterConfig)
    hard: HardConfig = Field(default_factory=HardConfig)


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
        if section != "router" or not hasattr(config.router, key):
            raise ValueError(f"unknown configuration override: {path}")
        current = getattr(config.router, key)
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
