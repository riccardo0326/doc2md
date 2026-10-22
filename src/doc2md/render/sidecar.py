from __future__ import annotations

import json
from pathlib import Path

from ..models import ConvertedDocument, RunStats


def _write_utf8(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_document(path: Path, document: ConvertedDocument) -> None:
    payload = json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    _write_utf8(path, payload)


def write_run(path: Path, stats: RunStats) -> None:
    payload = json.dumps(stats.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    _write_utf8(path, payload)
