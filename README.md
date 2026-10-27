# doc2md

`doc2md` converts PDF files to provenance-rich Markdown using a tiered,
CPU-oriented pipeline.

## Install

```bash
pip install .[bench]
pip install .[hard]
```

Use `.[dev]` for tests, Ruff, and mypy. The optional `[hard]` extra is for
disposable development diagnostics only. Enterprise PCs must not install or
download OCR/layout/model artifacts; supported hard processing requires an
approved remote adapter, otherwise the affected page is reported as failed.

## Convert

```bash
doc2md convert report.pdf --out out/
doc2md inspect report.pdf
doc2md convert report.pdf --out out/ --pipeline full-vision --no-cache
```

The Python API returns the same document and metrics held by the CLI:

```python
from doc2md import convert

result = convert("report.pdf", out_dir="out")
print(result.markdown_path)
print(result.stats.vision_tokens_total)
```

## Pipelines

- `tiered`: pdfplumber for text pages, then the approved hard adapter for hard pages.
- `full-vision`: renders and transcribes every page through Kelpie.
- `docling-only`: disposable development diagnostic; sends every page to Docling and does not call vision.

## Token Efficiency

The tiered pipeline avoids vision on ordinary text pages, routes hard pages only
to the configured hard adapter, deduplicates images, caches descriptions, and records
input/output/total token usage in `run.json`. `full-vision` is the explicit
comparison baseline. `--no-cache` is available for fair timing.

## Benchmark And Quality Review

Run the committed synthetic corpus, or generate a manifest that also discovers
PDFs from the read-only reference repository without copying them:

```bash
doc2md bench corpus --external-root C:\Users\rp99480\dev\ai4tc_webapp
doc2md bench run --suite bench/suite.toml --pipelines tiered,full-vision --reps 1
doc2md bench report bench_runs/<timestamp>
doc2md bench review-sheet bench_runs/<timestamp> --n 30 --seed 42
doc2md bench judge bench_runs/<timestamp>
```

The real EDAG OCR baseline is intentionally outside the Phase 9 implementation
scope. It can be run manually against the same corpus for parallel comparison.
Review outputs and PDF bytes are not committed.

For a local, path-driven Markdown quality check, pass any PDF and optionally
an external reference Markdown. The runner uses the fake vision backend by
default, writes output outside Git, validates the JSON sidecar, and reports
Docling/Kelpie environment status without embedding sample paths:

```bash
python scripts/check_quality.py --source path/to/input.pdf --out path/to/check-out
python scripts/check_quality.py --source path/to/input.pdf --out path/to/check-out --reference path/to/reference.md --json path/to/report.json
```

## Output

Conversion writes `<stem>.md`, `<stem>.json`, `run.json`, and kept images. The
Markdown uses page markers, optional block anchors, GFM tables, and inline image
descriptions. The JSON sidecar preserves page, block, and source provenance.

## Development

```bash
pytest
ruff check src tests
mypy src
```
