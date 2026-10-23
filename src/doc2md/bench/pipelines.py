from __future__ import annotations

PIPELINES = ("tiered", "full-vision", "docling-only", "baseline_current")


def validate_pipelines(names: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    unknown = sorted(set(names) - set(PIPELINES))
    if unknown:
        raise ValueError(f"unknown benchmark pipeline(s): {', '.join(unknown)}")
    return tuple(dict.fromkeys(names))
