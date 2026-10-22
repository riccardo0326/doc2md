"""Create the non-confidential PDF fixtures used by local demos and tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic"


def _new_canvas(path: Path) -> canvas.Canvas:
    path.parent.mkdir(parents=True, exist_ok=True)
    return canvas.Canvas(str(path), pagesize=letter)


def _text_fixture(path: Path, lines: list[tuple[str, str]]) -> None:
    document = _new_canvas(path)
    for heading, paragraph in lines:
        document.setFont("Helvetica", 14)
        document.drawString(72, 720, heading)
        document.setFont("Helvetica", 11)
        document.drawString(72, 690, paragraph)
        document.showPage()
    document.save()


def _table_fixture(path: Path) -> None:
    document = _new_canvas(path)
    document.setFont("Helvetica-Bold", 14)
    document.drawString(72, 720, "Synthetic table fixture")
    columns = [72, 230, 390]
    rows = [650, 610, 570, 530]
    for y in rows:
        document.line(72, y, 520, y)
    for x in [72, 230, 390, 520]:
        document.line(x, 530, x, 650)
    document.setFont("Helvetica", 10)
    values = [
        ("Item", "Language", "Status"),
        ("alpha", "English", "ready"),
        ("beta", "German", "ready"),
    ]
    for row, values_row in enumerate(values):
        for column, value in enumerate(values_row):
            document.drawString(columns[column] + 8, rows[row + 1] + 14, value)
    document.showPage()
    document.save()


def _image_only_fixture(path: Path) -> None:
    image = Image.new("RGB", (640, 360), "white")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((40, 40, 600, 320), outline="black", width=5)
    drawing.ellipse((190, 100, 450, 280), fill="steelblue", outline="black", width=4)
    drawing.text((220, 20), "Synthetic image-only page", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    document = _new_canvas(path)
    document.drawImage(ImageReader(buffer), 72, 300, width=468, height=263)
    document.showPage()
    document.save()


def _ligature_fixture(path: Path) -> None:
    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
    if not font_path.is_file():
        raise FileNotFoundError(f"Unicode fixture font not found: {font_path}")
    pdfmetrics.registerFont(TTFont("FixtureArial", str(font_path)))
    document = _new_canvas(path)
    document.setFont("FixtureArial", 14)
    document.drawString(72, 720, "ﬂow ofﬁce ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ")
    document.showPage()
    document.save()


def main() -> None:
    _text_fixture(
        FIXTURE_DIR / "phase1_text_en.pdf",
        [
            ("Synthetic English page one", "A deterministic paragraph for the fast path."),
            ("Synthetic English page two", "Page provenance must remain stable."),
            ("Synthetic English page three", "The CLI writes Markdown and JSON artifacts."),
        ],
    )
    _text_fixture(
        FIXTURE_DIR / "phase1_text_de.pdf",
        [
            ("Deutsche Testseite eins", "Straße und Übergröße bleiben erhalten."),
            ("Deutsche Testseite zwei", "Ein deterministischer Absatz für den Schnellpfad."),
        ],
    )
    _table_fixture(FIXTURE_DIR / "phase1_table.pdf")
    _image_only_fixture(FIXTURE_DIR / "phase1_image_only.pdf")
    _ligature_fixture(FIXTURE_DIR / "phase2_ligatures.pdf")
    print(FIXTURE_DIR)


if __name__ == "__main__":
    main()
