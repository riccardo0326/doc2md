# task-013 - Fix Markdown Parser Layout Artifacts

## What to build
Improve the generic PDF-to-Markdown output for running margins, HTML whitespace
artifacts, section-heading levels, table/list fallback structure, and optional
page markers. Preserve page provenance in the JSON sidecar and avoid any
document-specific text, page, or filename rules.

## Why
The current Lamborghini quality run shows that repeated furniture, Kelpie HTML
entities, inconsistent heading levels, and irregular-table list flattening make
otherwise recoverable content difficult to consume as Markdown.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/normalize.py` - shared text normalization boundary.
- `src/doc2md/converters/pdf/margins.py` - current repeated-margin filter.
- `src/doc2md/converters/pdf/fast.py` - fast headings, lists, and table fallback.
- `src/doc2md/converters/pdf/hard.py` - Kelpie Markdown mapping.
- `src/doc2md/api.py` - extraction order and document assembly.
- `src/doc2md/render/markdown.py` - page-marker rendering.
- `src/doc2md/config.py` - output-affecting defaults.
- `tests/test_normalize.py`, `tests/test_margins.py`, `tests/test_phase6.py`, `tests/test_hard.py` - regressions.

Modify:
- Production parser and renderer files listed above.
- `docs/decisions.md`, `PROJECT-SPEC.md`, and `ARCHITECTURE.md` for the marker contract and parser decisions.
- Focused synthetic tests; do not add confidential PDFs or generated outputs.

## Acceptance criteria
- [ ] Repeated headers, footers, and printed page numbers are removed from both fast and vision-derived blocks before final Markdown assembly.
- [ ] `&nbsp;` and non-breaking spaces do not appear in Markdown or sidecar text.
- [ ] Numbered section headings at every depth render as `##`, with wrapped heading fragments joined correctly.
- [ ] Irregular-table fallback preserves source text without inventing top-level list blocks from cell bullets.
- [ ] Page markers are off by default but remain available through explicit configuration/CLI opt-in; JSON page provenance is unchanged.
- [ ] Existing provenance, failure isolation, caching, and deterministic-output tests remain green.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests` passes.
- [ ] `mypy src` passes.
- [ ] The supplied external quality run is checked without committing confidential files.

## Status
dev-complete

### Dev notes
Files created:
- `src/doc2md/converters/pdf/headings.py`
- `workflow/tasks/task-013-parser-fixes.md`

Files modified:
- Parser normalization, margin filtering, heading mapping, table rendering, CLI/config, tests, and source-of-truth documentation.

Deviations from spec (if any):
- Markdown page markers are now opt-in; JSON provenance remains unchanged.
- The external quality runner with `FakeVisionBackend` cannot meet reference token coverage on Kelpie hard pages; structural checks pass and real Kelpie output remains environment-dependent.

Suggestions for follow-up (do not act on these):
- Run the external quality check with the approved Kelpie backend when configured to evaluate hard-page text fidelity.
