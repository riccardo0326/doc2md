# task-002 - Preserve Text When the Remote Hard Path Is Unavailable

## What to build
Keep the approved remote hard adapter as the preferred extractor for `COMPLEX`
and `SCANNED` pages, but add a transparent degraded fallback for a complex page
that still has a usable text layer when the hard adapter is unavailable.
Reuse the existing pdfplumber extractor, mark the page method and warning
accurately, and leave textless scanned pages failed. Improve best-effort GFM
rendering for merged or one-row tables so recoverable cells are not silently
dropped. Do not hide a hard-path failure or claim that fallback output has
Docling-level table fidelity.

## Why
The supplied PDF has five complex pages with recoverable text, but the current
enterprise environment has no approved remote hard adapter. The API currently turns
each such page into a failure and drops all page content.

## Relevant files

Read before starting:
- `src/doc2md/api.py` - page failure isolation and hard-path dispatch.
- `src/doc2md/converters/pdf/hard.py` - hard-adapter availability boundary.
- `src/doc2md/converters/pdf/fast.py` - table rendering and fallback extraction.
- `src/doc2md/models.py` - allowed methods and warning fields.
- `docs/decisions.md` - failure-isolation and artifact-boundary decisions.

Modify:
- `src/doc2md/api.py` - invoke fallback only for eligible text-backed hard failures.
- `src/doc2md/converters/pdf/fast.py` - preserve unrenderable table text and mark simplified tables.
- `tests/test_hard.py` and/or a focused integration test - test fallback and scanned behavior.
- `docs/decisions.md` - record the approved fallback semantics.

## Steps
1. Add a failing integration test with a digital table page and a fake hard extractor that raises `HardExtractionError`.
2. Add the fallback only after hard extraction fails; retain `page_class=COMPLEX` and record a warning identifying the degraded method.
3. Keep a page with no usable text layer as `failed` with the existing placeholder behavior.
4. Render rectangular merged-cell tables as best-effort GFM with `<!-- table: simplified -->` and preserve single-row table text as a non-table block when GFM headers are impossible.
5. Add assertions for sidecar provenance, warnings, and absence of dropped source text.
6. Run focused tests, full tests, Ruff, and mypy.

## Acceptance criteria
- [ ] A text-backed complex page remains `ok` with `method="pdfplumber"` and an explicit fallback warning when Docling is unavailable.
- [ ] A scanned page without usable text is not falsely reported as successfully extracted.
- [ ] Merged-cell table content is retained in Markdown and the simplification is visible.
- [ ] A one-row table no longer causes all of its text to disappear.
- [ ] When Docling is available, the normal hard path still wins and fallback is unused.

## Edge cases to handle
- When the fallback returns no blocks: preserve the original page failure and error.
- When the remote hard adapter raises a non-availability extraction error: do not silently mask it unless the approved policy explicitly includes that class.
- When a fallback table has blank cells: never invent repeated cell values.

## Do not touch
- The enterprise rule that local models and model downloads are unsupported.
- Page routing thresholds as a workaround for missing artifacts.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests` passes.
- [ ] `mypy src` completes without errors.
- [ ] The fallback policy is recorded in `docs/decisions.md`.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/api.py` - added the transparent text-backed complex-page fallback and run warning.
- `src/doc2md/converters/pdf/fast.py` - marks blank-cell tables as simplified GFM.
- `tests/test_hard.py` - added fallback, scanned-page, merged-table, and one-row-table coverage.
- `docs/decisions.md` - recorded ADR-033 for fallback semantics.

Deviations from spec (if any):
- The fallback is an explicit degraded mode for digital `COMPLEX` pages only; Docling remains preferred and scanned pages still fail when unavailable.

Suggestions for follow-up (do not act on these):
- Integrate the approved remote hard adapter and compare its output with the fallback on the external corpus.
