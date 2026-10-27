from __future__ import annotations

from ..models import ConvertedDocument


def render_markdown(
    document: ConvertedDocument,
    *,
    page_markers: bool = False,
    block_anchors: bool = False,
) -> str:
    lines: list[str] = []
    for page in document.pages:
        if page_markers:
            marker = f"<!-- page: {page.page} -->"
            if page.status == "failed":
                marker = f"<!-- page: {page.page} failed: {page.error or 'unknown error'} -->"
            lines.append(marker)
        for block in page.blocks:
            if block_anchors:
                lines.append(f"<!-- block: {block.block_id} -->")
            lines.append(block.markdown)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
