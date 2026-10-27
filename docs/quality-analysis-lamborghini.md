# PDF Quality Analysis

Status: Phase 0 investigation complete; no production code or tests were
changed by this analysis.

The user-supplied 23-page PDF and the reference Markdown are external files.
They were read from their existing Desktop locations and were not copied into
this repository. The reference Markdown is treated as a quality oracle for
text and tables only; no reference output is embedded in production logic.

## Reproduction

The following commands were run from the repository with the temporary
environment documented in `docs/discovery.md`:

```text
python -m doc2md inspect <external-source.pdf>
python -m doc2md convert <external-source.pdf> --out <external-output> --no-images --no-cache
python -m doc2md convert <external-source.pdf> --out <external-output> --no-cache
python -m pytest -q
python -m ruff check src tests
python -m mypy src
```

Observed results:

- `inspect`: 23 pages, 18 `TEXT`, 5 `COMPLEX`, 0 `SCANNED`.
- The five complex pages are pages 7, 8, 9, 11, and 22, all for
  `irregular_table`.
- The fresh text-only conversion completes in about 2 seconds, but all five
  complex pages are recorded as failed because local Docling artifacts are not
  provisioned.
- The fresh default conversion also completes, but the page-1 logo is saved
  and receives an image-description failure placeholder because Kelpie is not
  configured in that environment.
- The existing test suite passes: `56 passed, 1 skipped, 4 deselected`.
- Ruff passes.
- Mypy reports an existing invariant-dictionary type error at
  `src/doc2md/converters/pdf/fast.py:237` and did not complete within the
  five-minute command limit. The fix work must leave mypy both error-free and
  terminating.

The configured enterprise behavior is intentional: Docling refuses to download
models by default. A controlled development run with
`hard.allow_remote_download=true` converted page 7 through Docling and returned
a 5-row, 2-column table, confirming that the hard adapter itself can handle the
merged table when its artifacts are available. This opt-in is not a production
default.

## Findings

### F1 - Recoverable complex pages become empty failures (high)

`src/doc2md/api.py` dispatches every non-`TEXT` page to Docling. When
`DoclingExtractor` raises because artifacts are missing, the page loop records a
failed page and emits only a placeholder. The PDF still has a text layer on all
five pages. Direct calls to the existing fast extractor recover substantial
content on pages 7, 8, 9, and 22, including rectangular table data; page 11
recovers the table text as a paragraph because its detected table has only one
row.

Root cause: the hard path is correctly preferred, but there is no transparent
degraded path for a text-backed page when the hard dependency is unavailable.

Recommended fix: keep Docling first, then use pdfplumber only for a text-backed
hard-path failure, with `method="pdfplumber"` and a prominent fallback warning.
Keep textless scanned pages failed. This is a generic capability fallback, not
a route for this PDF.

### F2 - Heading and paragraph boundaries are too coarse (high)

`src/doc2md/converters/pdf/fast.py` groups lines using only a vertical-gap
rule. On the supplied document this merges headings such as `I. Purpose` with
the first paragraph and merges section labels with following body text. It
also leaves the repeated running title and printed page number in the content.

Root cause: the extractor already collects font size and word geometry, but the
block boundary decision does not use heading transitions or cross-page margin
signals.

Recommended fix: split blocks at geometry/font heading transitions, meaningful
vertical gaps, and list transitions. Add a separate generic repeated-margin
pass based on repeated normalized text at the same relative top/bottom
position. Do not use document-specific headings or page numbers.

### F3 - Bullet lists collapse into paragraphs (high)

The current list detector accepts a block only when every extracted line
matches `_LIST_RE`. The PDF text layer returns multiple bullet markers in one
logical line or in a block that also contains continuation text, so the
detector leaves sequences such as the confidentiality requirements as one
paragraph. The reference output preserves them as individual list items.

Recommended fix: recognize marker boundaries inside an extracted line, emit
one list item per marker, and attach wrapped continuation lines to the current
item. Keep bullet normalization in the fast structural parser; keep character
normalization in `normalize.py`.

### F4 - Irregular table detection is useful, but extraction loses the fallback

`signals.py` marks pages 7, 8, 9, 11, and 22 as irregular because pdfplumber
returns merged cells as blank cells. That is a valid reason to prefer Docling;
lowering `router.table_none_ratio` makes all these pages `TEXT`, but produces
wide best-effort tables with empty columns and is not a reliable fix.

`fast.py` can already render most of the rectangular rows when called directly,
but it rejects a one-row table and the API never calls it after a hard-path
failure. The targeted fix is to retain recoverable cell text, annotate
simplification for merged cells, and use the explicit fallback only when
Docling is unavailable. When Docling is provisioned, its 2-column result remains
the preferred output.

### F5 - Decorative logo passes the absolute image filter (medium)

The page-1 image occupies approximately 85 by 92 PDF points. At the default
150 DPI it exceeds the current absolute pixel thresholds, so it is saved and
sent to vision. With no Kelpie configuration, the result is a failed image
placeholder. The image is decorative and the reference Markdown contains no
meaningful image content.

Recommended fix: add a configurable page-relative area signal to the existing
generic filter, test it with a synthetic decorative image and a larger figure,
and record the skip decision. Do not detect the word `logo`, the filename, or
page 1.

### F6 - External quality behavior is not covered by tests (medium)

The 56 passing tests cover synthetic simple text, simple tables, fake images,
and isolated phase contracts. They do not cover the combination of repeated
margins, font transitions, inline bullets, merged tables, missing hard
artifacts, or a page-relative decorative image. No confidential PDF should be
committed to close this gap.

Recommended fix: add synthetic geometry/table fixtures plus a path-driven local
quality runner. The runner accepts an arbitrary PDF/reference path at runtime,
checks generated Markdown and sidecar structure, and keeps all outputs outside
Git.

## Targeted implementation order

1. `task-001`: semantic fast-path block and list segmentation.
2. `task-002`: hard-path degraded fallback and best-effort irregular tables.
3. `task-003`: repeated header/footer filtering.
4. `task-004`: generic decorative-image filtering and vision degradation checks.
5. `task-005`: reusable external quality run and Markdown checks.

Provisioning Docling artifacts remains a prerequisite for measuring the normal
hard path and should be done before claiming final table fidelity. The fallback
is for continuity and development ergonomics, not a substitute for Docling in
the enterprise path.

## Explicit non-goals

- No branch keyed to the Lamborghini filename, page numbers, section names, or
  reference Markdown.
- No literal copy of the online converter output.
- No global rewrite of the pipeline or replacement of pdfplumber/Docling.
- No network/model dependency in the default test suite.
- No confidential PDF, reference Markdown, model response, or token value in
  the repository.

## Verification after implementation

The external run should be repeated with both modes:

```text
doc2md inspect <external-source.pdf>
doc2md convert <external-source.pdf> --out <external-output> --no-images --no-cache
doc2md convert <external-source.pdf> --out <external-output> --set vision.backend=fake --no-cache
python scripts/check_quality.py --source <external-source.pdf> --reference <external-reference.md> --out <external-output>
```

The report must distinguish these cases:

- normal Docling extraction with locally provisioned artifacts;
- explicit development-only remote Docling extraction;
- transparent pdfplumber fallback for text-backed complex pages;
- an actual page with no usable extraction, which remains failed.
