# task-001 - Improve Fast-Path Semantic Blocks

## What to build
Improve the pdfplumber fast extractor so it separates headings, paragraphs,
and lists using the word geometry and font metadata already available, while
preserving reading order and normalization. Consecutive bullet markers must
become list items even when pdfplumber returns several markers on one extracted
line. The implementation must be document-agnostic and must not recognize the
supplied Lamborghini document by page number or text.

## Why
The current extractor merges a heading with the first paragraph and collapses
many bullet lists into one paragraph. This loses Markdown structure even when
the PDF text layer is usable.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/fast.py` - current line grouping, heading, and list logic.
- `src/doc2md/converters/pdf/normalize.py` - the only character-normalization boundary.
- `src/doc2md/config.py` - existing fast-path thresholds.
- `tests/test_phase6.py` - current semantic fast-path coverage.

Modify:
- `src/doc2md/converters/pdf/fast.py` - add generic boundary and list segmentation.
- `src/doc2md/config.py` - add only thresholds required by the generic algorithm.
- `tests/test_phase6.py` or a focused fast-path test module - add regression tests.

## Steps
1. Add failing tests for a heading followed by body text, paragraph spacing, and multi-item bullets returned on one line.
2. Split semantic line groups at heading transitions and list-marker transitions without changing word reading order.
3. Normalize bullet markers into Markdown list items while preserving continuation lines and item text.
4. Keep table line exclusion and block IDs deterministic.
5. Run the focused tests, full tests, Ruff, and mypy.

## Acceptance criteria
- [ ] A heading and its following paragraph are separate blocks when font/geometry identifies the heading.
- [ ] A paragraph remains one block across ordinary wrapped lines and starts a new block after a meaningful vertical gap.
- [ ] Inline and line-leading bullet markers become separate Markdown list items with no dropped text.
- [ ] Existing two-column and simple-table behavior remains green.
- [ ] No sample-specific words, page numbers, or PDF paths occur in production code.

## Edge cases to handle
- When a list item wraps: continuation lines remain attached to that item.
- When a page has no font-size metadata: retain the existing paragraph behavior.
- When a bullet glyph is garbled: preserve the text and mark the block as garbled rather than deleting it.

## Do not touch
- Docling routing or Kelpie behavior.
- Character mappings outside `normalize.py`.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests` passes.
- [ ] `mypy src` completes without errors.
- [ ] All acceptance criteria are checked.
- [ ] No debug statements or sample-specific branches remain.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/converters/pdf/fast.py` - added geometry-aware semantic boundaries and inline list-marker parsing; fixed table metadata typing.
- `tests/test_phase6.py` - added heading/body and inline-list regression coverage.

Deviations from spec (if any):
- None.

Suggestions for follow-up (do not act on these):
- Running-margin filtering remains task-003.
