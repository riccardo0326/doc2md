from __future__ import annotations

from pathlib import Path

import typer

from .api import convert as convert_document

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


def main() -> None:
    app()
