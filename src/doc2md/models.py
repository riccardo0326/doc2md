from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PageClass = Literal["TEXT", "COMPLEX", "SCANNED"]
Method = Literal["pdfplumber", "docling", "vision"]
BlockType = Literal["heading", "paragraph", "list", "table", "figure", "code", "other"]
PageStatus = Literal["ok", "failed", "skipped"]


class SourceInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    sha256: str
    size_bytes: int
    page_count: int


class ToolInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    doc2md: str
    pdfplumber: str
    docling: str | None = None
    pypdfium2: str | None = None
    config_hash: str


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int
    source: Method
    bbox: dict[str, float] | None = None


class Block(BaseModel):
    model_config = ConfigDict(frozen=True)

    block_id: str
    type: BlockType
    markdown: str
    text: str
    level: int | None = None
    provenance: Provenance
    meta: dict[str, str | int | float | bool] = Field(default_factory=dict)


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated: bool


class ImageRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_id: str
    page: int
    status: Literal["described", "skipped", "failed"]
    width_px: int = 0
    height_px: int = 0
    sha256: str = ""
    path: str | None = None
    description: str | None = None
    usage: Usage | None = None


class PageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int
    status: PageStatus
    page_class: PageClass | None
    method: Method | None
    blocks: list[Block] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ConvertedDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    source: SourceInfo
    pipeline: str
    pages: list[PageResult]
    images: list[ImageRecord] = Field(default_factory=list)
    tool: ToolInfo


class PageStat(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int
    status: PageStatus
    page_class: PageClass | None
    method: Method | None
    duration_s: float


class RunStats(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime
    finished_at: datetime
    pipeline: str
    source: SourceInfo
    config_hash: str
    wall_time_s: float
    pages: list[PageStat] = Field(default_factory=list)
    pages_failed: int = 0
    vision_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tokens_estimated: bool = False
    warnings: list[str] = Field(default_factory=list)

    @property
    def vision_tokens_total(self) -> int:
        return self.total_tokens


class ConversionResult(BaseModel):
    document: ConvertedDocument
    markdown: str
    markdown_path: Path | None
    json_path: Path | None
    run_path: Path | None
    stats: RunStats
