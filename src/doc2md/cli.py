from __future__ import annotations

from pathlib import Path

import typer

from .api import convert as convert_document
from .api import inspect_pdf
from .bench.judge import judge_run
from .bench.report import write_report
from .bench.review import write_review_sheet
from .bench.runner import run_benchmark
from .config import Config, with_overrides

app = typer.Typer(help="Convert PDF documents to provenance-rich Markdown.")
bench_app = typer.Typer(help="Run benchmark suites and build reports.")
app.add_typer(bench_app, name="bench")


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


@bench_app.command("run")
def bench_run_command(
    suite: Path = typer.Option(..., "--suite", exists=True, readable=True),
    pipelines: str | None = typer.Option(None, "--pipelines"),
    repetitions: int | None = typer.Option(None, "--reps", min=1),
    output_dir: Path = typer.Option(Path("bench_runs"), "--out", file_okay=False),
) -> None:
    selected = pipelines.split(",") if pipelines else None
    run_dir = run_benchmark(
        suite,
        output_dir=output_dir,
        pipelines=selected,
        repetitions=repetitions,
    )
    typer.echo(str(run_dir))


@bench_app.command("report")
def bench_report_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    typer.echo(str(write_report(run_dir)))


@bench_app.command("review-sheet")
def bench_review_sheet_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    sample_size: int = typer.Option(30, "--n", min=1),
    seed: int = typer.Option(42, "--seed"),
) -> None:
    paths = write_review_sheet(run_dir, n=sample_size, seed=seed)
    typer.echo(str(paths.csv_path))


@bench_app.command("judge")
def bench_judge_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    typer.echo(str(judge_run(run_dir)))


def main() -> None:
    app()
