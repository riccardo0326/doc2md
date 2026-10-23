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
    pipeline: str = typer.Option("tiered", "--pipeline"),
    set_values: list[str] = typer.Option([], "--set"),
    no_images: bool = typer.Option(False, "--no-images"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    strict: bool = typer.Option(False, "--strict"),
) -> None:
    config = with_overrides(Config(), set_values)
    if no_images:
        config = config.model_copy(
            update={"images": config.images.model_copy(update={"enabled": False})}
        )
    result = convert_document(
        input_path,
        out_dir,
        pipeline=pipeline,
        config=config,
        no_cache=no_cache,
        strict=strict,
    )
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
