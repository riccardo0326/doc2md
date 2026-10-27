from __future__ import annotations

import pytest

from doc2md import convert
from doc2md.converters.pdf.fast import extract_page
from doc2md.converters.pdf.normalize import is_garbled, normalize_text


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("ﬀ", "ff"),
        ("ﬁ", "fi"),
        ("ﬂow", "flow"),
        ("ﬃ", "ffi"),
        ("ﬄ", "ffl"),
        ("ﬅ", "st"),
        ("ﬆ", "st"),
    ],
)
def test_normalize_ligatures(source: str, expected: str) -> None:
    assert normalize_text(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("exam-\nple", "example"),
        ("Über-\ngröße", "Übergröße"),
        ("E-\nMail", "E-Mail"),
        ("foo-\nBar", "foo-Bar"),
        ("state-of-the-art", "state-of-the-art"),
        ("hello\n  world", "hello world"),
    ],
)
def test_normalize_line_breaks_and_whitespace(source: str, expected: str) -> None:
    assert normalize_text(source) == expected


def test_normalize_removes_soft_hyphen_and_preserves_german_characters() -> None:
    assert normalize_text("Straße Über­größe") == "Straße Übergröße"


def test_normalize_removes_disallowed_control_characters() -> None:
    assert normalize_text("di\x00cult\x01 text\twith\nspacing") == "di cult text with spacing"


def test_garbled_cid_text_is_flagged() -> None:
    assert is_garbled("value (cid:12)(cid:45)")
    assert is_garbled("di\x00cult")
    assert not is_garbled("Straße")


def test_fast_extractor_normalizes_the_whole_page_before_splitting() -> None:
    class FakePage:
        def extract_text(self, **_: object) -> str:
            return "ﬂow\nexam-\nple\n(cid:12)"

    blocks = extract_page(FakePage(), 1)  # type: ignore[arg-type]

    assert [block.text for block in blocks] == ["flow", "example", "(cid:12)"]
    assert blocks[-1].meta == {"garbled": True}


def test_ligature_fixture_is_normalized_through_pdf_extraction() -> None:
    result = convert("tests/fixtures/synthetic/phase2_ligatures.pdf")

    assert "flow office fi fl ff ffi ffl st st" in result.markdown
