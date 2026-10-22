from __future__ import annotations

from pathlib import Path

import typer

from .api import convert as convert_document
from .api import inspect_pdf
from .config import Config, with_overrides

app = typer.Typer(help="Convert PDF documents to provenance-rich Markdown.")


@app.callback()
def root() -> None:
    """Run a doc2md command."""


@app.command("convert")
def convert_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    out_dir: Path = typer.Option(..., "--out", "-o", file_okay=False),
) -> None:
    result = convert_document(input_path, out_dir)
    typer.echo(str(result.markdown_path))


@app.command("inspect")
def inspect_command(
    input_path: Path = typer.Argument(..., exists=True, readable=True),
    set_values: list[str] = typer.Option([], "--set"),
) -> None:
    config = with_overrides(Config(), set_values)
    decisions = inspect_pdf(input_path, config=config)
    typer.echo("page chars words image_area tables garbled class reason")
    for decision in decisions:
        signals = decision.signals
        typer.echo(
            f"{decision.page} {signals.chars} {signals.words} "
            f"{signals.image_area_ratio:.3f} {signals.table_count} "
            f"{signals.garbled_ratio:.3f} {decision.page_class} "
            f"{','.join(decision.reasons)}"
        )


def main() -> None:
    app()
