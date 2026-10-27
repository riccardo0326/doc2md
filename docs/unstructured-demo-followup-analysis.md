# Unstructured Demo Follow-up Analysis

Status: analysis only. No production code was changed during this follow-up.

The six PDFs under `samples/unstructured-demo/` were converted through the
CLI with the `tiered` pipeline, `vision.backend=fake`, and `--no-cache`. Outputs
were written outside the repository under the user's Desktop:

```text
C:\Users\rp99480\Desktop\out\unstructured-demo
```

Each output was inspected as Markdown, JSON sidecar, and `run.json`. The
quality runner was also executed per sample. The fake vision backend validates
image-stage wiring and deterministic output, but it does not measure the
semantic quality of a real Kelpie description.

## Corpus Results

| Sample | Runtime result | Quality result | Main observation |
|---|---|---|---|
| `embedded-images.pdf` | 1 `TEXT` page, 0 failed, 3 vision calls | Pass for pipeline mechanics | Text and three inline image records are present. |
| `embedded-images-tables.pdf` | 1 `TEXT` page, 0 failed, 1 vision call | Partial | Image is handled, but the visible table is emitted as paragraphs rather than a GFM table. |
| `multi-column-2p.pdf` | 2 `TEXT` pages, 0 failed | Fail for reading order | Text from both columns is interleaved before Markdown blocks are formed. |
| `list-item-example.pdf` | 2 `COMPLEX` pages, pdfplumber fallback | Fail for structure | Each page becomes one simplified table block; list items are not emitted as Markdown lists. |
| `layout-parser-paper-with-empty-pages.pdf` | 2 `TEXT`, 2 `SCANNED`, 2 failed | Fail for completeness | The two empty pages are routed to OCR and fail because the Kelpie-backed hard path is not implemented. The text pages also contain control/glyph artifacts. |
| `table-multi-row-column-cells.pdf` | 1 `SCANNED` page, 1 failed | Fail for completeness | The table is image-only and needs the Kelpie-backed hard path. |

All generated sidecars validated and block provenance matched the containing
page. The CLI returned success because normal mode isolates page failures;
the quality runner reports those failures explicitly.

## Root Causes

### R1 - OCR and hard-path artifacts are not available

`table-multi-row-column-cells.pdf` has no text layer and no detectable table;
the only recoverable content is in an image. Pages 2 and 3 of the LayoutParser
sample are similarly textless. The current behavior is contract-consistent: the
hard adapter is unavailable and the page failure is isolated. It is not
sufficient for a complete demo, however.

Fix boundary: use Kelpie with models hosted locally on EDAG servers, reusing the
discovered `VisionBackend`/`transcribe_page` contract. Local Docling/OCR model
installation, provisioning, and runtime downloads are permanently out of
scope. Do not add a sample-specific vision branch.

### R2 - Truly empty pages are misclassified as scanned

The LayoutParser file is explicitly named as containing empty pages. A page
with zero text, zero images, and zero tables is currently caught by the
`not has_text_layer` rule and routed to OCR. Empty layout pages should be
represented as successful empty pages, not as OCR failures.

Fix boundary: add an early generic empty-page route while preserving the
existing three page classes. It should produce a page marker, zero blocks, and
an `empty_page` reason without invoking Docling.

### R3 - Same-Y words from separate columns are merged too early

`fast._word_lines()` groups words when their top coordinates are close, without
requiring horizontal overlap. In `multi-column-2p.pdf`, words from the left and
right columns therefore become a single `_Line`; `_reading_order()` cannot
recover the original columns afterward. The output shows fragments such as
`imple-Open-domain` and interleaves abstract text.

Fix boundary: make line formation column-aware before paragraph grouping. Words
on the same baseline must remain separate when their horizontal gap indicates
different columns. Full-width title/author lines and footnotes need an explicit
exception based on geometry, not document strings.

### R4 - Borderless tables are invisible to table detection

`embedded-images-tables.pdf` reports no `find_tables()` result even though its
text layer contains a structured data table. The current fast path therefore
emits the table as ordinary paragraphs. This is a detection gap, not just a
Markdown rendering gap.

Fix boundary: add a confidence-scored borderless-table detector using repeated
baselines, aligned x-columns, and header/data consistency. Route uncertain
cases to the Kelpie-backed hard path when available; otherwise preserve a clear
best-effort structure instead of silently flattening it.

### R5 - Lists inside irregular table cells are flattened

`list-item-example.pdf` contains module descriptions with bullet-like entries
inside a two-column layout. pdfplumber detects an irregular table, and the
current fallback renders the whole cell contents as one long GFM row. This
preserves much of the text but destroys the intended list structure.

Fix boundary: normalize cell content independently, split recognized bullet
markers into Markdown list lines inside the cell, preserve merged-cell text,
and never invent values for blank spans. When table confidence is too low,
emit ordered headings/paragraphs/lists rather than one synthetic table.

### R6 - Control and glyph artifacts survive normalization

The LayoutParser Markdown contains three NUL characters and 29 other control
characters. The sidecar includes visible artifacts such as `di\\u0000cult` and
font-encoding fragments (`o↵the-shelf`, isolated `X`, `V`, and `C`). The current
garbled detection focuses on `(cid:N)`, replacement characters, and private-use
characters, so NUL/control contamination is not consistently reported.

Fix boundary: extend the normalization/garbled contract for disallowed control
characters and known extraction artifacts, preserving meaningful whitespace,
Unicode math, umlauts, and symbols. The output must remain valid UTF-8 text and
must never contain NUL bytes.

## Priority Order

1. Integrate and verify the Kelpie-backed hard-processing path. This unlocks
   the scanned table and pages without installing models on the PC.
2. Fix empty-page routing so blank pages do not consume OCR or become failures.
3. Fix column-aware line formation, because every later paragraph/list decision
   depends on correct lines.
4. Add borderless-table detection and a conservative table confidence policy.
5. Preserve lists and merged-cell content in irregular tables and fallback output.
6. Harden control/glyph normalization and garbled reporting.

## Acceptance Targets

- `table-multi-row-column-cells.pdf`: one successful page with a structured table
  through the Kelpie-backed hard path; no placeholder in normal mode.
- `layout-parser-paper-with-empty-pages.pdf`: empty pages complete with zero
  blocks; non-empty pages contain no NUL/control artifacts.
- `multi-column-2p.pdf`: left-column text precedes right-column text for each
  page, with no same-line cross-column concatenation.
- `list-item-example.pdf`: module headings and bullet entries are represented
  as headings/paragraphs/lists, not one table block per page.
- `embedded-images-tables.pdf`: the data table is represented by a table block
  with stable rows/columns, and the figure remains an inline image block.
- Every sample has valid sidecar provenance and zero unexplained page failures.
- All checks use synthetic committed fixtures plus runtime paths; no sample
  filename, page number, or phrase is hardcoded in production code.

## Verification Matrix

Run after each task:

```text
pytest -q
ruff check src tests scripts
mypy src
doc2md inspect <sample.pdf>
doc2md convert <sample.pdf> --out <desktop-out> --set vision.backend=fake --no-cache
python scripts/check_quality.py --source <sample.pdf> --out <desktop-out>
```

Once the Kelpie-backed hard path is available, repeat the scanned cases and
record hard-adapter pages, OCR status, and table cell counts in `run.json`.
