from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.pdfgen import canvas


@pytest.fixture
def text_pdf(tmp_path: Path) -> Path:
    source = tmp_path / "fixture.pdf"
    document = canvas.Canvas(str(source))
    for page_number in range(1, 4):
        document.setFont("Helvetica", 12)
        document.drawString(72, 720, f"Page {page_number} heading")
        document.drawString(72, 690, f"Page {page_number} paragraph.")
        document.showPage()
    document.save()
    return source
