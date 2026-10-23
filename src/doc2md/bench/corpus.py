from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import pdfplumber
from pydantic import BaseModel, ConfigDict


class CorpusDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    sha256: str
    size_bytes: int
    page_count: int | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _page_count(path: Path) -> int | None:
    try:
        with pdfplumber.open(str(path)) as pdf:
            return len(pdf.pages)
    except Exception:  # noqa: BLE001 - a corrupt corpus file remains listed
        return None


def discover_pdfs(roots: Sequence[str | Path]) -> list[CorpusDocument]:
    paths: dict[str, Path] = {}
    for root_value in roots:
        root = Path(root_value)
        candidates = [root] if root.is_file() else root.rglob("*") if root.is_dir() else []
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() == ".pdf":
                resolved = candidate.resolve()
                paths[str(resolved).casefold()] = resolved
    return [
        CorpusDocument(
            path=path,
            sha256=_sha256(path),
            size_bytes=path.stat().st_size,
            page_count=_page_count(path),
        )
        for path in sorted(paths.values(), key=lambda item: (len(item.parts), str(item).casefold()))
    ]


def write_manifest(documents: list[CorpusDocument], path: str | Path) -> Path:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "documents": [
            {
                "path": document.path.as_posix(),
                "sha256": document.sha256,
                "size_bytes": document.size_bytes,
                "page_count": document.page_count,
            }
            for document in documents
        ]
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path
