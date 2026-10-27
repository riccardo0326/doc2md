# task-011 - Remove Control and Font-Encoding Artifacts

## What to build
Extend the normalization and garbled-text contract to remove or safely replace
disallowed control characters such as NUL while preserving valid whitespace,
Unicode punctuation, mathematical symbols, umlauts, and German characters.
Report unrecoverable font-encoding artifacts as `garbled` instead of emitting
binary/control bytes in Markdown or JSON.

## Why
The LayoutParser output contains NUL bytes and control characters, plus
isolated font fragments that make the Markdown unreadable and cause tools to
classify the file as binary.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/normalize.py` - current normalization rules.
- `src/doc2md/converters/pdf/fast.py` - normalization boundary and block metadata.
- `tests/test_normalize.py` - table-driven normalization tests.
- `tests/test_phase2.py` or relevant normalization fixture tests.

Modify:
- `src/doc2md/converters/pdf/normalize.py` - control-character handling and garbled detection.
- `tests/test_normalize.py` - NUL/control and artifact regressions.

## Acceptance criteria
- [ ] Generated Markdown and sidecar text contain no NUL or forbidden control characters.
- [ ] Existing ligature, hyphenation, umlaut, beta, and symbol behavior remains green.
- [ ] Unrecoverable artifacts are marked `garbled` without deleting surrounding text.
- [ ] No blanket NFKC or document-specific character replacement is introduced.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] Ruff and mypy pass.
- [ ] The LayoutParser sample's text pages contain no NUL/control bytes in the quality run.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/converters/pdf/normalize.py` - replaces disallowed C0/C1 controls with spaces and flags them as garbled.
- `tests/test_normalize.py` - added NUL/control regressions.

Deviations from spec (if any):
- None.

Suggestions for follow-up (do not act on these):
- Review isolated font fragments remaining after normalization on multi-column research papers.
