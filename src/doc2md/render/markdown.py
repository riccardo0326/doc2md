from __future__ import annotations

from ..models import ConvertedDocument


def render_markdown(
    document: ConvertedDocument,
    *,
    page_markers: bool = True,
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
        if page.status == "ok" and page.page_class != "TEXT" and not page.blocks:
            lines.append(f"<!-- page {page.page}: routed to hard path (not yet implemented) -->")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
