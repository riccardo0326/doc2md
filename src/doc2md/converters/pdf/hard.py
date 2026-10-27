from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any

from ...config import HardConfig
from ...errors import HardExtractionError
from ...models import Block, BlockType, Provenance
from ...vision.base import VisionBackend, VisionResult
from .headings import normalize_heading
from .normalize import normalize_text

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+\u2022\u25cf]|\d+[.)])\s+(.+?)\s*$")


def _table_meta(markdown: str) -> dict[str, str | int | float | bool]:
    rows = [line for line in markdown.splitlines() if line.strip().startswith("|")]
    data_rows = [line for line in rows if not re.match(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$", line)]
    columns = max((line.count("|") - 1 for line in rows), default=0)
    return {"table_rows": len(data_rows), "table_cols": columns}


def blocks_from_transcription(page: int, markdown: str) -> list[Block]:
    """Map Kelpie's Markdown transcription into the common block model."""
    normalized = normalize_text(markdown, preserve_lines=True)
    lines = normalized.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

    blocks: list[Block] = []
    paragraph: list[str] = []
    index = 0

    def append_block(
        block_type: BlockType,
        value: str,
        *,
        level: int | None = None,
        meta: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        nonlocal index
        text = value.strip()
        if not text:
            return
        rendered = text
        normalized_level = level
        if block_type == "heading":
            rendered, text, normalized_level = normalize_heading(text, level or 2)
        index += 1
        blocks.append(
            Block(
                block_id=f"p{page:04d}-b{index:03d}",
                type=block_type,
                markdown=rendered,
                text=text,
                level=normalized_level,
                provenance=Provenance(page=page, source="vision"),
                meta=meta or {},
            )
        )

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            append_block("paragraph", " ".join(paragraph))
            paragraph = []

    while lines:
        line = lines.pop(0)
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        heading = _HEADING_RE.match(stripped)
        if heading:
            flush_paragraph()
            append_block("heading", stripped, level=len(heading.group(1)))
            continue
        if stripped.startswith("|"):
            flush_paragraph()
            table_lines = [stripped]
            while lines and lines[0].strip().startswith("|"):
                table_lines.append(lines.pop(0).strip())
            table_markdown = "\n".join(table_lines)
            append_block("table", table_markdown, meta=_table_meta(table_markdown))
            continue
        list_match = _LIST_RE.match(stripped)
        if list_match:
            flush_paragraph()
            list_lines = [f"- {list_match.group(1)}"]
            while lines:
                next_match = _LIST_RE.match(lines[0].strip())
                if next_match is None:
                    break
                lines.pop(0)
                list_lines.append(f"- {next_match.group(1)}")
            append_block("list", "\n".join(list_lines))
            continue
        paragraph.append(stripped)
    flush_paragraph()
    if not blocks:
        raise HardExtractionError(f"Kelpie returned no transcribed content for page {page}")
    return blocks


class KelpieHardExtractor:
    """Render selected pages and transcribe them through the Kelpie vision backend."""

    name = "kelpie"

    def __init__(
        self,
        vision: VisionBackend,
        *,
        page_dpi: int,
        prompt_id: str,
    ) -> None:
        self.vision = vision
        self.page_dpi = page_dpi
        self.prompt_id = prompt_id
        self._calls: list[tuple[str, VisionResult]] = []

    def drain_calls(self) -> list[tuple[str, VisionResult]]:
        calls = self._calls
        self._calls = []
        return calls

    def extract(
        self,
        source: Path,
        pages: list[int] | tuple[int, ...],
        context: object | None = None,
    ) -> dict[int, list[Block]]:
        del context
        try:
            import pypdfium2 as pdfium
        except ImportError as error:
            raise HardExtractionError("pypdfium2 is required for Kelpie hard pages") from error

        document = pdfium.PdfDocument(str(source))
        extracted: dict[int, list[Block]] = {}
        try:
            for page_number in sorted(set(pages)):
                page = document[page_number - 1]
                try:
                    bitmap = page.render(scale=self.page_dpi / 72.0)
                    image = bitmap.to_pil().convert("RGB")
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    result = self.vision.transcribe_page(
                        buffer.getvalue(), prompt_id=self.prompt_id
                    )
                    self._calls.append((f"p{page_number:04d}", result))
                    extracted[page_number] = blocks_from_transcription(
                        page_number, result.text
                    )
                except Exception as error:  # noqa: BLE001 - page isolation belongs to caller
                    if isinstance(error, HardExtractionError):
                        raise
                    raise HardExtractionError(
                        f"Kelpie hard transcription failed on page {page_number}: {error}"
                    ) from error
                finally:
                    page.close()
        finally:
            document.close()
        return extracted


class DoclingExtractor:
    """Lazy Docling adapter that converts selected original page numbers."""

    name = "docling"

    def __init__(self, config: HardConfig | None = None) -> None:
        self.config = config or HardConfig()
        self._converter: Any | None = None

    def _get_converter(self) -> Any:
        if self._converter is not None:
            return self._converter
        if self.config.engine != "docling-dev-only":
            raise HardExtractionError(
                "Docling is a disposable development adapter; enterprise hard pages use Kelpie."
            )
        if not self.config.artifacts_path and not self.config.allow_remote_download:
            raise HardExtractionError(
                "Disposable development Docling artifacts are unavailable; enterprise hard "
                "pages use Kelpie."
            )
        if self.config.artifacts_path and not Path(self.config.artifacts_path).is_dir():
            raise HardExtractionError(
                "Disposable development Docling artifacts are unavailable at the configured path."
            )
        try:
            from docling.datamodel.accelerator_options import AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                OcrAutoOptions,
                PdfPipelineOptions,
                TableFormerMode,
            )
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as error:
            raise HardExtractionError(
                "Docling is required for hard-path extraction; install doc2md[hard]."
            ) from error

        options = PdfPipelineOptions(
            accelerator_options=AcceleratorOptions(
                num_threads=self.config.threads,
                device="cpu",
            ),
            artifacts_path=self.config.artifacts_path,
            do_ocr=self.config.ocr,
            do_table_structure=True,
            do_picture_classification=False,
            do_picture_description=False,
        )
        table_options: Any = options.table_structure_options
        table_options.mode = TableFormerMode.ACCURATE
        if self.config.ocr:
            options.ocr_options = OcrAutoOptions(lang=list(self.config.languages))
        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        return self._converter

    @staticmethod
    def _page_number(item: Any, fallback: int) -> int:
        provenance = getattr(item, "prov", None) or []
        return int(getattr(provenance[0], "page_no", fallback)) if provenance else fallback

    @staticmethod
    def _block(item: Any, level: int, page: int, number: int, document: Any) -> Block | None:
        label = getattr(getattr(item, "label", None), "value", str(getattr(item, "label", "")))
        label = str(label).lower()
        if "picture" in label or "figure" in label:
            return None

        if "table" in label:
            markdown = item.export_to_markdown(doc=document)
            table_data = getattr(item, "data", None)
            meta: dict[str, str | int | float | bool] = {}
            if table_data is not None:
                for key in ("num_rows", "num_cols"):
                    value = getattr(table_data, key, None)
                    if value is not None:
                        meta[f"table_{key.removeprefix('num_')}"] = int(value)
            text = markdown
            block_type: BlockType = "table"
        else:
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                return None
            if "section_header" in label:
                block_type = "heading"
                markdown = f"{'#' * max(level, 1)} {text}"
            elif "list" in label:
                block_type = "list"
                markdown = f"- {text}"
            else:
                block_type = "paragraph"
                markdown = text
            meta = {}

        return Block(
            block_id=f"p{page:04d}-b{number:03d}",
            type=block_type,
            markdown=markdown,
            text=text,
            level=level if block_type == "heading" else None,
            provenance=Provenance(page=page, source="docling"),
            meta=meta,
        )

    def extract(
        self,
        source: Path,
        pages: list[int] | tuple[int, ...],
        context: object | None = None,
    ) -> dict[int, list[Block]]:
        del context
        converter = self._get_converter()
        extracted: dict[int, list[Block]] = {}
        for page in sorted(set(pages)):
            try:
                result = converter.convert(source, page_range=(page, page))
                blocks: list[Block] = []
                for item, level in result.document.iterate_items():
                    original_page = self._page_number(item, page)
                    if original_page != page:
                        continue
                    block = self._block(item, level, page, len(blocks) + 1, result.document)
                    if block is not None:
                        blocks.append(block)
                extracted[page] = blocks
            except Exception as error:  # noqa: BLE001 - caller isolates page failures
                raise HardExtractionError(f"Docling failed on page {page}: {error}") from error
        return extracted
