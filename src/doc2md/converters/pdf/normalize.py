from __future__ import annotations

import re

_LIGATURES = str.maketrans(
    {
        "ﬀ": "ff",
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "st",
        "ﬆ": "st",
    }
)
_GARBLED_RE = re.compile(r"\(cid:\d+\)|\ufffd|[\ue000-\uf8ff]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _join_hyphenated_lines(text: str) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    joined: list[str] = []
    index = 0
    while index < len(lines):
        current = lines[index].rstrip()
        if current.endswith("-") and index + 1 < len(lines):
            following = lines[index + 1].lstrip()
            if following:
                left = current[:-1].rstrip()
                word_before_hyphen = left.rsplit(None, 1)[-1]
                first = following[0]
                remove_hyphen = first.islower() and len(word_before_hyphen) > 2
                joined.append(left + ("" if remove_hyphen else "-") + following)
                index += 2
                continue
        joined.append(current)
        index += 1
    return "\n".join(joined)


def normalize_text(text: str, *, preserve_lines: bool = False) -> str:
    """Normalize PDF text without changing language-specific characters."""
    normalized = text.translate(_LIGATURES).replace("\u00ad", "")
    normalized = _CONTROL_RE.sub(" ", normalized)
    normalized = _join_hyphenated_lines(normalized)
    if preserve_lines:
        lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in normalized.split("\n")]
        return "\n".join(lines).strip()
    return re.sub(r"\s+", " ", normalized).strip()


def is_garbled(text: str) -> bool:
    """Return whether text contains common PDF glyph-decoding artifacts."""
    return _GARBLED_RE.search(text) is not None or _CONTROL_RE.search(text) is not None
