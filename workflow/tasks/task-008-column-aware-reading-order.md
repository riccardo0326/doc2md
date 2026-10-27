# task-008 - Preserve Multi-Column Reading Order

## What to build
Change fast-path word-to-line formation so words from separate columns on the
same baseline do not become one `_Line`. Detect column bands from horizontal
geometry, keep full-width title/author lines intact, and emit blocks in normal
column order. Preserve footnotes and superscripts without treating isolated
glyph fragments as headings or lists.

## Why
The current midpoint ordering runs after same-Y words have already been merged.
The multi-column sample therefore contains interleaved sentences and malformed
fragments even though every page is classified as `TEXT`.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/fast.py` - `_word_lines` and `_reading_order`.
- `src/doc2md/config.py` - fast geometry thresholds.
- `tests/test_phase6.py` - semantic fast-path tests.
- `tests/fixtures/synthetic/` - existing generated PDF conventions.

Modify:
- `src/doc2md/converters/pdf/fast.py` - geometry-aware line and column grouping.
- `src/doc2md/config.py` - only generic column thresholds required by the algorithm.
- `tests/test_phase6.py` or a focused column-order test - synthetic two-column acceptance cases.

## Acceptance criteria
- [ ] Same-baseline words in distinct columns are never concatenated into one line.
- [ ] Full-width title/author/header lines remain single blocks.
- [ ] Column 1 content is emitted before column 2 content on each page.
- [ ] Existing single-column, heading, list, and table tests remain green.
- [ ] Superscripts and footnotes do not create bogus headings or list blocks.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] Ruff and mypy pass.
- [ ] No source-specific x coordinates, text, or page numbers are used.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/converters/pdf/fast.py` - keeps same-baseline words in separate lines and splits paragraph groups at column transitions.
- `tests/test_phase6.py` - added a synthetic two-column regression.

Deviations from spec (if any):
- None.

Suggestions for follow-up (do not act on these):
- Re-run the multi-column corpus after borderless-table and glyph fixes to validate mixed scientific layouts.
