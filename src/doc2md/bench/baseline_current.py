from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

import pdfplumber
from pydantic import BaseModel, ConfigDict

from ..models import Usage


class BaselineResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    markdown_path: Path
    wall_time_s: float
    usage: Usage | None = None
    pages: int | None = None


class BaselineAdapter(Protocol):
    def run(self, source: Path, out_dir: Path) -> BaselineResult: ...


class FakeBaselineAdapter:
    """Offline adapter used by tests until the current EDAG system is available."""

    def run(self, source: Path, out_dir: Path) -> BaselineResult:
        started = time.perf_counter()
        markdown_path = out_dir / f"{source.stem}.md"
        with pdfplumber.open(str(source)) as pdf:
            lines = [
                f"<!-- page: {page_number} -->\n{page.extract_text() or ''}"
                for page_number, page in enumerate(pdf.pages, start=1)
            ]
            pages = len(pdf.pages)
        markdown_path.write_text("\n\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return BaselineResult(
            markdown_path=markdown_path,
            wall_time_s=time.perf_counter() - started,
            pages=pages,
        )
