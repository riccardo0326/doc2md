# task-006 - Route Truly Empty Pages Without OCR

## What to build
Classify a PDF page with no text characters, no images, and no detected tables
as an empty successful `TEXT` page with reason `empty_page`. It must emit the
normal page marker, no blocks, no hard-path call, and no failure placeholder.
Pages with any image or table signal remain eligible for the existing scanned
or complex routes.

## Why
The LayoutParser sample contains intentionally empty pages. Treating every
textless page as scanned causes avoidable failures when OCR artifacts are not
needed.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/router.py` - first-match routing rules.
- `src/doc2md/converters/pdf/signals.py` - text/image/table signals.
- `tests/test_router.py` - router contract tests.
- `tests/test_phase3.py` - PDF routing integration coverage.

Modify:
- `src/doc2md/converters/pdf/router.py` - add the generic empty-page rule.
- `tests/test_router.py` and/or `tests/test_phase3.py` - add empty-page cases.

## Acceptance criteria
- [ ] A page with zero chars, zero images, and zero tables is `TEXT` with `empty_page` reason.
- [ ] Conversion produces `status="ok"`, zero blocks, and no Docling call for that page.
- [ ] A scanned page containing a full-page image remains `SCANNED`.
- [ ] A table/image page is not misclassified as empty.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests scripts` passes.
- [ ] `mypy src` passes.
- [ ] No sample-specific conditions are added.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/converters/pdf/router.py` - added generic `empty_page` routing before scanned detection.
- `tests/test_router.py` - added empty-page and content-signal regression coverage.
- `tests/test_phase3.py` - added blank-PDF end-to-end coverage.

Deviations from spec (if any):
- Empty pages retain the existing `TEXT` page class with zero blocks to avoid widening the page-class contract.

Suggestions for follow-up (do not act on these):
- Re-run the LayoutParser sample after the remaining parser and OCR tasks.
