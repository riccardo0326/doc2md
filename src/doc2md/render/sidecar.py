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
    page_counts = {
        "total": len(stats.pages),
        "text": sum(page.page_class == "TEXT" for page in stats.pages),
        "complex": sum(page.page_class == "COMPLEX" for page in stats.pages),
        "scanned": sum(page.page_class == "SCANNED" for page in stats.pages),
        "failed": stats.pages_failed,
    }
    payload = {
        "run_id": stats.run_id,
        "started_at": stats.started_at.isoformat(),
        "finished_at": stats.finished_at.isoformat(),
        "pipeline": stats.pipeline,
        "source": {
            "name": stats.source.name,
            "sha256": stats.source.sha256,
            "pages": stats.source.page_count,
        },
        "config_hash": stats.config_hash,
        "totals": {
            "wall_time_s": stats.wall_time_s,
            "pages": page_counts,
            "vision": {
                "calls": stats.vision_calls,
                "input_tokens": stats.input_tokens,
                "output_tokens": stats.output_tokens,
                "total_tokens": stats.total_tokens,
                "estimated": stats.tokens_estimated,
            },
            "docling": {
                "pages": stats.docling_pages,
                "time_s": stats.docling_time_s,
            },
            "cache": {"hits": stats.cache_hits, "misses": stats.cache_misses},
        },
        "pages": [
            {
                "page": page.page,
                "class": page.page_class,
                "method": page.method,
                "duration_s": page.duration_s,
                "reasons": page.reasons,
            }
            for page in stats.pages
        ],
        "calls": stats.model_dump(mode="json")["calls"],
        "warnings": stats.warnings,
    }
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _write_utf8(path, payload_text)
