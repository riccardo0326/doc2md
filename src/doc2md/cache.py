from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class DiskCache:
    """Small JSON-only content-addressed cache used by one conversion source."""

    def __init__(self, directory: str | Path, source_hash: str, *, enabled: bool = True) -> None:
        self.directory = Path(directory)
        self.source_hash = source_hash
        self.enabled = enabled

    def _path(self, stage: str, key: str) -> Path:
        parts = [part for part in (*stage.split("/"), *key.split("/")) if part]
        safe_parts = [part.replace("..", "_").replace("\\", "_") for part in parts]
        return (
            self.directory
            / self.source_hash[:2]
            / self.source_hash
            / Path(*safe_parts).with_suffix(".json")
        )

    def get(self, stage: str, key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        path = self._path(stage, key)
        try:
            with path.open(encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError, TypeError):
            return None

    def put(self, stage: str, key: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(stage, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, path)


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def docling_cache_key(page: int, config: object, version: str = "unknown") -> str:
    return f"page{page:04d}-{_digest({'config': config, 'version': version})}"


def vision_cache_key(
    image_or_page: str,
    prompt_id: str,
    model: str,
    config: object,
) -> str:
    return _digest(
        {
            "input": image_or_page,
            "prompt": prompt_id,
            "model": model,
            "config": config,
        }
    )
