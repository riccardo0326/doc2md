from __future__ import annotations

import json
import tomllib
from pathlib import Path

from doc2md.bench.corpus import discover_pdfs, write_manifest


def test_corpus_discovery_is_recursive_deduplicated_and_does_not_copy(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one.pdf"
    nested = tmp_path / "nested" / "two.PDF"
    nested.parent.mkdir()
    first.write_bytes(b"one")
    nested.write_bytes(b"two")

    discovered = discover_pdfs([tmp_path, nested.parent])

    assert [item.path for item in discovered] == [first, nested]
    manifest = write_manifest(discovered, tmp_path / "manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(payload["documents"]) == 2
    assert not (tmp_path / "manifest" / "one.pdf").exists()
    assert all(item["sha256"] for item in payload["documents"])


def test_packaging_declares_final_extras_and_docs() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "hard" in pyproject["project"]["optional-dependencies"]
    assert "bench" in pyproject["project"]["optional-dependencies"]
    assert Path("README.md").is_file()
    assert Path("docs/FINDINGS.md").is_file()
    assert Path("THIRD_PARTY_NOTICES.md").is_file()
