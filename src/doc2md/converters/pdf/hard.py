from __future__ import annotations

from pathlib import Path
from typing import Any

from ...config import HardConfig
from ...errors import HardExtractionError
from ...models import Block, BlockType, Provenance


class DoclingExtractor:
    """Lazy Docling adapter that converts selected original page numbers."""

    name = "docling"

    def __init__(self, config: HardConfig | None = None) -> None:
        self.config = config or HardConfig()
        self._converter: Any | None = None

    def _get_converter(self) -> Any:
        if self._converter is not None:
            return self._converter
        if not self.config.artifacts_path and not self.config.allow_remote_download:
            raise HardExtractionError(
                "Docling artifacts are not provisioned locally; set hard.artifacts_path "
                "or explicitly enable remote downloads for controlled development only."
            )
        if self.config.artifacts_path and not Path(self.config.artifacts_path).is_dir():
            raise HardExtractionError(
                f"Docling artifacts path does not exist: {self.config.artifacts_path}"
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
