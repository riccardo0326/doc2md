# task-009 - Detect Borderless Text Tables

## What to build
Add a confidence-scored detector for tables without drawn borders using
repeated baselines, aligned word columns, stable row widths, and header/data
consistency. Emit confident cases as GFM table blocks with correct metadata;
route uncertain cases to the hard path when available and preserve readable
paragraphs when it is not.

## Why
The embedded-images-tables sample has a visible data table but
`pdfplumber.find_tables()` reports none, so the current output loses table
structure while still preserving raw text.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/signals.py` - current table signals.
- `src/doc2md/converters/pdf/fast.py` - table extraction and Markdown rendering.
- `src/doc2md/config.py` - router/fast thresholds.
- `tests/test_signals.py` and `tests/test_phase6.py` - existing table tests.

Modify:
- `src/doc2md/converters/pdf/signals.py` - expose a generic borderless-table signal.
- `src/doc2md/converters/pdf/fast.py` - reconstruct high-confidence rows/cells.
- `src/doc2md/config.py` - make confidence thresholds configurable.
- `tests/test_signals.py` and focused integration tests - borderless table cases.

## Acceptance criteria
- [ ] The synthetic borderless table is detected and rendered as a table block.
- [ ] `embedded-images-tables.pdf` produces structured rows/columns without hardcoding.
- [ ] Ordinary multi-column prose is not falsely converted to a table.
- [ ] Low-confidence layouts remain readable and are routed/marked transparently.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] Ruff and mypy pass.
- [ ] Table cell counts and provenance are asserted in JSON.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/converters/pdf/signals.py` - added conservative aligned-row borderless-table detection.
- `src/doc2md/converters/pdf/fast.py` - reuses the detected rows for GFM rendering.
- `tests/test_phase6.py` - added a synthetic borderless table acceptance test.

Deviations from spec (if any):
- The detector is intentionally conservative and requires three numeric-bearing rows.

Suggestions for follow-up (do not act on these):
- Tune the confidence heuristic against additional borderless tables after the full corpus rerun.
