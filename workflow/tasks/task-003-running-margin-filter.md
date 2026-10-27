# task-003 - Remove Repeated Running Margins

## What to build
Add an opt-in or default-configured, document-agnostic pass that removes
repeated running headers and footers from fast-path content when the same
normalized line occurs in the same top or bottom margin across multiple pages.
Do not remove unique body text, first-page cover content, or footnotes merely
because they are near a margin. Preserve page provenance and make the behavior
visible in warnings or configuration when enabled.

## Why
The current output repeats the regulation title and printed page number on all
pages, while the reference conversion treats them as layout furniture rather
than document content.

## Relevant files

Read before starting:
- `src/doc2md/api.py` - document-level page loop and assembly.
- `src/doc2md/converters/pdf/fast.py` - geometry of extracted lines.
- `src/doc2md/config.py` - fast/render configuration.
- `src/doc2md/render/markdown.py` - page/block rendering contract.

Modify:
- `src/doc2md/api.py` or a new pure helper under `src/doc2md/converters/pdf/` - cross-page margin detection.
- `src/doc2md/config.py` - threshold and enable flag if needed.
- `tests/test_phase6.py` or a focused fast-path test module - synthetic repeated-margin cases.

## Steps
1. Add a synthetic multi-page fixture with a repeated header/footer and unique body text.
2. Add a failing test proving only repeated margin furniture is removed.
3. Detect candidates by normalized content plus relative vertical position and require repetition across pages.
4. Remove only complete semantic blocks identified as margin furniture.
5. Preserve first-page cover metadata and any line that is unique to one page.
6. Run the full quality checks.

## Acceptance criteria
- [ ] Repeated headers and printed page numbers are absent when the filter is enabled.
- [ ] Unique body lines and first-page metadata remain unchanged.
- [ ] The filter does not depend on a title string, page number, or source filename.
- [ ] Markdown page markers and JSON block provenance remain valid.

## Edge cases to handle
- When a repeated line appears in the body rather than a margin: do not remove it.
- When a document has no repeated margins: output is byte-identical to the pre-filter result.
- When only one page exists: no line is removed solely due to position.

## Do not touch
- Hard-path Docling output.
- External reference Markdown.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests` passes.
- [ ] `mypy src` completes without errors.

## Status
dev-complete

### Dev notes
Files created:
- `src/doc2md/converters/pdf/margins.py` - pure repeated-margin detection and filtering.
- `tests/test_margins.py` - synthetic multi-page regression tests.

Files modified:
- `src/doc2md/config.py` - added configurable margin filtering and repetition threshold.
- `src/doc2md/api.py` - applies the filter after page extraction and before image assembly.
- `docs/decisions.md` - recorded ADR-034.

Deviations from spec (if any):
- Numeric footer recognition is intentionally limited to final all-digit blocks repeated across pages; other footer formats remain untouched.

Suggestions for follow-up (do not act on these):
- Validate the default threshold against additional documents with legitimate numeric content at page bottoms.
