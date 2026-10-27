from __future__ import annotations

import re

_HEADING_MARKER_RE = re.compile(r"^#{1,6}\s+")


def normalize_heading(text: str, level: int) -> tuple[str, str, int]:
    """Return Markdown, plain text, and a stable heading level."""
    plain = _HEADING_MARKER_RE.sub("", text.strip()).strip()
    normalized_level = 1 if level == 1 else 2
    return f"{'#' * normalized_level} {plain}", plain, normalized_level
