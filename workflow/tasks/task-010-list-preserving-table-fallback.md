# task-010 - Preserve Lists Inside Irregular Tables

## What to build
Improve irregular-table fallback rendering so each cell is normalized
independently, bullet markers become list lines inside the cell, merged blank
cells do not create invented values, and low-confidence table layouts can be
rendered as ordered headings/paragraphs/lists instead of one oversized GFM
row.

## Why
The list-item sample is routed to the complex path and currently falls back to
one simplified table per page, destroying the document's module/list structure.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/fast.py` - `_table_markdown` and list parsing.
- `src/doc2md/converters/pdf/hard.py` - preferred Docling table mapping.
- `tests/test_hard.py` and `tests/test_phase6.py` - fallback/table coverage.

Modify:
- `src/doc2md/converters/pdf/fast.py` - cell-level list and fallback rendering.
- `tests/test_hard.py` or a focused table/list integration test - module/list fixture.

## Acceptance criteria
- [ ] Bullet entries in a table cell are preserved as separate Markdown list items.
- [ ] Module titles and explanatory text remain separate semantic blocks where geometry supports it.
- [ ] Merged cells retain all text without duplicated or invented values.
- [ ] A low-confidence fallback is visibly marked and never silently reported as high-fidelity Docling output.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] Ruff and mypy pass.
- [ ] The list-item sample has no table-only page blocks in the quality run.

## Status
ready
