from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from doc2md import Config, convert
from doc2md.config import ImageConfig, VisionConfig
from doc2md.models import ConvertedDocument

_TOKEN_RE = re.compile(r"[^\W_]{3,}", re.UNICODE)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_REFERENCE_COVERAGE_MIN = 0.9


@dataclass
class QualityReport:
    source: str
    output_dir: str
    markdown_path: str | None = None
    json_path: str | None = None
    page_count: int = 0
    failed_pages: list[int] = field(default_factory=list)
    page_classes: dict[str, int] = field(default_factory=dict)
    block_counts: dict[str, int] = field(default_factory=dict)
    repeated_margin_residue: list[str] = field(default_factory=list)
    reference_path: str | None = None
    reference_token_coverage: float | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tokens(text: str) -> set[str]:
    cleaned = _COMMENT_RE.sub(" ", text)
    cleaned = _IMAGE_RE.sub(" ", cleaned)
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(cleaned)}


def _normal_key(text: str) -> str:
    return " ".join(text.split()).casefold()


def _margin_residue(document: ConvertedDocument) -> list[str]:
    occurrences: dict[tuple[str, str], set[int]] = defaultdict(set)
    for page in document.pages:
        if page.status != "ok":
            continue
        blocks = [
            block
            for block in page.blocks
            if block.provenance.source == "pdfplumber" and block.text.strip()
        ]
        if not blocks:
            continue
        candidates = [("header", blocks[0])]
        if len(blocks) > 1:
            candidates.append(("footer", blocks[-1]))
        for role, block in candidates:
            occurrences[(role, _normal_key(block.text))].add(page.page)
    return sorted(
        f"{role}:{text}"
        for (role, text), pages in occurrences.items()
        if len(pages) >= 2
    )


def _environment(config: Config) -> dict[str, Any]:
    artifact_path = config.hard.artifacts_path
    kelpie_model = (
        os.environ.get("KELPIE_MODEL", "")
        or os.environ.get("LLM_VISION_DEPLOYMENT", "")
        or os.environ.get("LLM_CHAT_DEPLOYMENT", "")
    )
    return {
        "docling_installed": importlib.util.find_spec("docling") is not None,
        "enterprise_hard_adapter_configured": False,
        "development_docling_artifacts_present": bool(
            artifact_path and Path(artifact_path).is_dir()
        ),
        "vision_backend": config.vision.backend,
        "kelpie_configured": bool(
            config.vision.kelpie.base_url or os.environ.get("KELPIE_PROXY_BASE_URL")
        )
        and bool(config.vision.kelpie.model or kelpie_model),
    }


def run_quality(
    source: Path,
    output_dir: Path,
    *,
    reference: Path | None = None,
    pipeline: str = "tiered",
    vision_backend: str = "fake",
    no_images: bool = False,
) -> QualityReport:
    config = Config(
        images=ImageConfig(enabled=not no_images),
        vision=VisionConfig(backend=vision_backend),
    )
    report = QualityReport(
        source=str(source),
        output_dir=str(output_dir),
        reference_path=str(reference) if reference is not None else None,
        environment=_environment(config),
    )
    result = convert(
        source,
        output_dir,
        pipeline=pipeline,
        config=config,
        no_cache=True,
    )
    if result.markdown_path is None or result.json_path is None:
        report.errors.append("conversion did not publish Markdown and JSON paths")
        return report

    report.markdown_path = str(result.markdown_path)
    report.json_path = str(result.json_path)
    markdown = result.markdown_path.read_text(encoding="utf-8")
    try:
        document = ConvertedDocument.model_validate_json(
            result.json_path.read_text(encoding="utf-8")
        )
    except Exception as error:  # noqa: BLE001 - report validation failures
        report.errors.append(f"sidecar validation failed: {type(error).__name__}: {error}")
        return report

    report.page_count = document.source.page_count
    report.failed_pages = [page.page for page in document.pages if page.status == "failed"]
    report.page_classes = dict(
        Counter(page.page_class or "NONE" for page in document.pages)
    )
    report.block_counts = dict(
        Counter(block.type for page in document.pages for block in page.blocks)
    )
    report.repeated_margin_residue = _margin_residue(document)

    if len(document.pages) != document.source.page_count:
        report.errors.append(
            f"sidecar has {len(document.pages)} pages; source has {document.source.page_count}"
        )
    seen_block_ids: set[str] = set()
    for page in document.pages:
        for block in page.blocks:
            if block.block_id in seen_block_ids:
                report.errors.append(f"duplicate block id: {block.block_id}")
            seen_block_ids.add(block.block_id)
            if block.provenance.page != page.page:
                report.errors.append(
                    f"block {block.block_id} provenance page does not match page {page.page}"
                )
    if report.failed_pages:
        report.errors.append(f"failed pages: {report.failed_pages}")
    if report.repeated_margin_residue:
        report.errors.append("repeated margin residue detected")

    if reference is not None:
        reference_tokens = _tokens(reference.read_text(encoding="utf-8"))
        output_tokens = _tokens(markdown)
        report.reference_token_coverage = (
            len(reference_tokens & output_tokens) / len(reference_tokens)
            if reference_tokens
            else 1.0
        )
        if report.reference_token_coverage < _REFERENCE_COVERAGE_MIN:
            report.errors.append(
                "reference token coverage below "
                f"{_REFERENCE_COVERAGE_MIN:.0%}: {report.reference_token_coverage:.2%}"
            )

    report.passed = not report.errors
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check doc2md output quality for an arbitrary PDF."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", dest="output_dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--pipeline", default="tiered")
    parser.add_argument("--vision-backend", choices=("fake", "kelpie"), default="fake")
    parser.add_argument("--no-images", action="store_true")
    parser.add_argument("--json", dest="json_path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run_quality(
            args.source,
            args.output_dir,
            reference=args.reference,
            pipeline=args.pipeline,
            vision_backend=args.vision_backend,
            no_images=args.no_images,
        )
    except Exception as error:  # noqa: BLE001 - CLI reports conversion failures
        print(f"quality run failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
