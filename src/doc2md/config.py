from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field


class RenderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    page_markers: bool = True
    block_anchors: bool = False


class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    render: RenderConfig = Field(default_factory=RenderConfig)


def config_hash(config: Config) -> str:
    payload = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
