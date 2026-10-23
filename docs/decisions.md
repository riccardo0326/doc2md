# Design Decisions

This file records decisions made while resolving the gaps between
`PROJECT-SPEC.md` and `ARCHITECTURE.md` on 2026-10-22. The project specification
remains the source of truth when the two documents disagree.

## ADR-001: Incremental delivery and Phase 0 gate

**Decision:** Deliver the project as vertical slices. The first implementation
target is the `tiered` pipeline, using `FakeVisionBackend` where needed. Do not
scaffold future phases. Start feature implementation only after Phase 0
discovery is complete and the human confirms `go`.

**Reason:** Kelpie, Docling, the environment, licenses, and the current EDAG
baseline must be verified before their concrete integrations are implemented.

## ADR-002: Pipeline semantics

**Decision:**

- `tiered` uses the router: `TEXT` uses pdfplumber; `COMPLEX` and `SCANNED`
  use Docling.
- `SCANNED` pages use Docling OCR with `en+de`.
- `full-vision` sends every page to vision and disables the image stage.
- `docling-only` sends every page to Docling, extracts and saves images, but
  never calls vision. Saved images are linked without descriptions and are
  marked `vision_disabled`.
- `baseline_current` remains an optional benchmark adapter until the EDAG
  software is available.

`page_class` always reports the actual page classification from the signals;
forced pipelines change the extraction method, not the classification.

The full-page raster of a scanned page is not treated as an embedded figure.
Only distinct pictures reported by Docling may enter the image stage for such
a page.

## ADR-003: Vision contracts

**Decision:** Keep image description and page transcription as separate
contracts. `describe_image()` returns descriptive text and usage;
`transcribe_page()` returns validated structured blocks and usage. Vision page
blocks use the common block model and carry `source="vision"`.

Vision prompts must request the versioned structured schema. Invalid structured
responses become isolated failures; the core does not contain an implicit
free-text parser.

The real Kelpie contract must be discovered from the reference implementation
and verified by the Phase 0 probe. It must not be invented.

## ADR-004: Deterministic content versus run metrics

**Decision:** Markdown and the JSON sidecar are deterministic for the same
source, configuration, and backends. `run.json` is an operational manifest and
may contain UUID4 `run_id`, UTC ISO-8601 timestamps, wall times, and per-page
durations.

`PageResult` does not contain `duration_s`; timing belongs in a dedicated
`RunStats` structure inside `run.json`. Page and call ordering remains stable.

Page markers and block anchors are enabled by default. Block anchors may be
disabled explicitly.

## ADR-005: In-memory and file output

**Decision:** With `out_dir=None`, `ConversionResult` keeps assets in an
API-only `image_id -> bytes` map and renders kept images as data URIs. With an
output directory, images are written under `images/` and Markdown uses relative
paths.

Binary data is never serialized into the sidecar JSON. The sidecar contains
image metadata, paths where applicable, descriptions, and usage only.

`--no-images` disables image extraction, saving, and description without
changing text extraction or page routing. It also means the tiered pipeline does
not need to initialize a vision backend.

## ADR-006: Image identity, provenance, and placement

**Decision:** The first occurrence of an image is canonical. Duplicate
occurrences receive their own `ImageRecord` and figure block, but reference the
canonical image through `canonical_image_id`, path, and description. A duplicate
is described and saved only once.

Every described occurrence produces a `figure` block with its own stable block
ID and page provenance. Image records retain asset identity, dimensions, hash,
status, canonical reference, and usage.

Image placement is deterministic: sort by page, vertical position, and stable
source index; insert after the last preceding block vertically. An image above
all blocks is inserted at the start of the page. An image without a bounding
box is inserted at the end.

Image handling has these outcomes:

- `too_small` and `bad_aspect`: record only, no Markdown link;
- `duplicate`: reuse the canonical figure path and description;
- `vision_disabled`: save and link the image with an explicit no-description
  note;
- `failed`: create a figure placeholder and warning.

## ADR-007: Failure isolation and strict mode

**Decision:** Normal conversion isolates page and image failures, records them,
continues, and renders placeholders. Strict conversion treats any page or image
failure as fatal, raises `ConversionFailed`, and publishes no final artifacts.

Output publication is atomic in strict mode. If a multi-page Docling batch
fails, the converter retries pages individually so only pages that still fail
are marked failed.

## ADR-008: Page selection

**Decision:** Validate page selections before extraction. Invalid, out-of-range,
or malformed page numbers are configuration errors. Valid pages are
deduplicated and processed in numeric order.

Unselected pages appear in the sidecar as `status="skipped"`, with
`page_class=null`, `method=null`, no blocks, zero duration, and a
`page_not_selected` warning. They are omitted from Markdown.

## ADR-009: Public models and immutability

**Decision:** Define all public models before feature implementation:

- `SourceInfo`: `name`, `sha256`, `size_bytes`, `page_count`;
- `ToolInfo`: doc2md, pdfplumber, Docling, pypdfium2 versions, and
  `config_hash`;
- `PageSelection`: immutable 1-based page sequence;
- `RunStats`: run identity, timestamps, pipeline, source, config hash, derived
  totals, page and call details, cache data, and warnings.

Models flowing between stages are deeply immutable. Frozen Pydantic models use
immutable nested collections rather than relying only on top-level
`frozen=True`.

## ADR-010: Routing and fast-path fallback

**Decision:** If reading order cannot confidently identify columns, the fast
path keeps pdfplumber order and emits a warning; it does not silently activate
Docling. If table detection is unreliable in Phase 0, any page with at least
one table is conservatively routed to `COMPLEX`.

## ADR-011: Cache and metrics semantics

**Decision:** Metrics describe the current run only. A cache hit increments the
cache-hit counters but does not create a call record or add cached historical
usage to current token totals. A second identical run therefore makes zero
external vision and Docling calls.

Cache entries are JSON only. Binary assets are regenerated or copied from the
source, never stored as pickle or Python objects. Vision keys include the image
hash, versioned prompt, model, relevant vision configuration, and schema
version.

## ADR-012: Configuration, inspection, and context ownership

**Decision:**

- `inspect` prints a human-readable table by default and supports `--json`;
  the Python API always returns structured models.
- Configuration is fully typed. Unknown keys fail validation.
- `--set section.key=value` parses TOML literals; environment variables remain
  strings and are converted by Pydantic.
- Only output-affecting configuration fields enter the effective config hash.
- A caller-provided `RunContext` is not closed or globally mutated by
  `convert()`. Internally created contexts are owned and closed by the API.

## ADR-013: Benchmark behavior and evaluation

**Decision:** Docling warm-up runs are recorded separately and excluded from
repetitions and medians. Cold-cache repetitions use isolated caches, and each
`results.csv` row represents one document, pipeline, and repetition.

The benchmark works without `baseline_current`, compares at least `tiered` with
`full-vision`, and never invents missing baseline token usage. Judge failures
are recorded as `judge_error`, excluded from numeric averages, and shown in the
report. Manual review, judge scores, and their agreement are reported
separately; the judge does not determine go/no-go by itself.

The proposed go/no-go thresholds remain provisional until stakeholder approval
before Phase 9.

## ADR-014: Token-efficiency documentation

**Decision:** The README must include a prominent token-efficiency section that
explicitly calls out:

- avoiding vision on `TEXT` pages;
- routing Docling only to hard pages;
- image deduplication;
- cached descriptions;
- no vision calls in `docling-only`;
- `full-vision` as the explicit comparison baseline.

The section should include a metrics example so the savings are immediately
visible to users.

## Remaining Phase 0 facts

The following are discovery tasks, not unresolved design decisions:

- Python and operating-system details on the target machine;
- installed dependency versions, APIs, model downloads, performance, and
  licenses;
- Kelpie request/response shape, authentication variable names, models,
  usage reporting, limits, and safe concurrency;
- Docling page-range support and page-number mapping;
- the EDAG baseline invocation and token-usage source when delivered;
- the sample document set and offline token-estimation capability.

No production integration should be implemented until these facts are recorded
and Phase 0 receives human sign-off.

## ADR-015: Kelpie adapter boundary

**Decision:** After Phase 0 sign-off, implement `KelpieVisionBackend` as a thin
native client in `src/doc2md/vision/kelpie.py`. It will use `kelpie-sdk` for the
refreshing service-account token and the OpenAI SDK Responses API for text and
image-plus-text requests. It will not import `ai4tc_webapp`, copy its source,
or depend on its LangChain wrapper.

**Reason:** The reference implementation isolates Kelpie authentication in
`utils/kelpie_client.py`, while the doc2md architecture requires a replaceable
`VisionBackend` edge and explicit usage metrics. A native adapter keeps that
boundary small and allows doc2md to apply its own timeout, 429/5xx retry, usage
fallback, redaction, and concurrency rules.

**Status:** The local proxy path is verified for both calls and is the confirmed
primary transport. The direct service-account path remains static-reference
evidence.

## ADR-016: Phase 0 license exception

**Decision:** Accept the BSL-1.0 component reported inside the CPU `torch`
dependency tree of the verified Docling environment as a documented Phase 0
exception.

**Reason:** The human explicitly accepted the exception on 2026-10-22. The
exception applies to the discovered environment only and must remain visible in
`docs/licenses.md`; it does not authorize adding other non-allow-listed
dependencies without review.

## ADR-017: Verified Kelpie runtime choices

**Decision:** Use the authenticated local Kelpie proxy as the primary Phase 5
transport. Use `DARE-NoCloud-Helios` for vision, `DARE-NoCloud-Nova` for the
text-only judge, and start with `vision.max_workers=1`.

**Reason:** The foreground proxy at `127.0.0.1:18080` returned the model list.
Helios completed both text and image probes with usage; Nova completed text but
returned an image-input validation error. A single worker is the conservative
initial setting until a dedicated load test changes it.

## ADR-018: Temporary sample-set exception

**Decision:** The current sample set contains two confidential five-page PDFs.
Phase 1 may use synthetic fixtures while four additional real documents are
pending. The real set must be completed before benchmark work.

**Status:** Accepted by the human as a Phase 0 exception on 2026-10-22. The
exception ends before benchmark work.

## ADR-019: Phase 1 fast-path scope

**Decision:** Phase 1 implements only the deterministic digital-text fast path
with pdfplumber. Each non-empty extracted line becomes an ordered paragraph
block with page provenance; dynamic timing and run identity stay in `run.json`,
while Markdown and the sidecar remain deterministic.

**Reason:** This is the smallest walking skeleton that proves the public API,
CLI, page markers, provenance, and artifact layout without loading Docling or
calling Kelpie. Routing, normalization, images, and hard-path extraction remain
for their specified later phases.

## ADR-020: Synthetic fixture set

**Decision:** Keep four generated, non-confidential PDFs under
`tests/fixtures/synthetic/` for repeatable demos and future phase tests. They
cover English text, German text, a text-layer table, and an image-only page.

**Reason:** These fixtures make local verification reproducible without putting
confidential Oz/Hannes documents in tests. They do not count toward the real
sample-set requirement for benchmarking.

## ADR-021: Phase 2 normalization boundary

**Decision:** Keep all character and line-break normalization in
`src/doc2md/converters/pdf/normalize.py`. The fast extractor normalizes the
whole page while preserving line boundaries, then creates blocks. Garbled
`(cid:NN)`, replacement, and private-use glyphs are preserved in text and
flagged in block metadata.

**Reason:** A single pure normalization boundary prevents special-character
fixes from spreading into routing, rendering, or future hard-path adapters.

## ADR-023: Phase 4 Docling adapter

**Decision:** Configure Docling lazily through `PdfFormatOption` and
`PdfPipelineOptions`, force CPU execution, keep table structure enabled,
disable picture enrichment, and convert each selected original page with
`page_range=(N, N)`. Map section headers, lists, text, and tables into the
common `Block` model with `source="docling"`.

**Reason:** The installed Docling API supports page ranges and preserves the
original page number in provenance. Keeping the converter inside the adapter
avoids importing or loading Docling for text-only conversions.

**Environment note:** OCR integration is implemented and tested, but the local
RapidOCR model download is currently blocked by the workstation's corporate TLS
certificate chain; the slow OCR test records this as an environment skip.

## ADR-025: Phase 5 vision transport and image identity

**Decision:** Use the verified local Kelpie OpenAI-compatible proxy through the
native OpenAI Responses API. Keep `FakeVisionBackend` as the deterministic test
edge. Image duplicates are identified from the embedded PDF stream when
available, while rendered PNG bytes are used for the actual vision request and
artifact hash.

**Reason:** This matches the Phase 0 evidence without importing LangChain or
depending on remote services. The image stage can therefore be tested fully
offline and the real proxy integration remains a replaceable adapter.

## ADR-026: Fast-path Markdown enrichment remains pending

**Decision:** Treat the current line-oriented Markdown as the Phase 1 walking
skeleton only. Before benchmark or final demo claims, enrich the pdfplumber fast
path with semantic headings, paragraph grouping, lists, and simple GFM tables as
required by FR3.

**Reason:** The current output is valid Markdown with provenance, but it is not
yet a semantically rich document representation. This is product work distinct
from the completed Phase 5 image/vision pipeline.

## ADR-024: Enterprise Docling artifact boundary

**Decision:** Runtime Docling model downloads are outside the enterprise
product perimeter. `DoclingExtractor` requires a local `hard.artifacts_path` by
default; remote downloads are available only through an explicit
`allow_remote_download=true` setting for controlled development or provisioning.
Missing local artifacts fail the affected hard page without aborting the
document. OCR for scanned pages is not a guaranteed capability until OCR
artifacts are provisioned locally.

**Reason:** The target corporate machines reject the model-download TLS chain
and do not have a local Tesseract alternative. A production conversion must
never depend on an unverified external download or silently disable TLS.

## ADR-022: Phase 3 routing boundary

**Decision:** Compute page signals with pdfplumber, classify them with a pure
router using typed configuration, and keep `COMPLEX`/`SCANNED` pages as explicit
hard-path placeholders until Phase 4. `inspect` exposes the signals and route
reasons; CLI `--set router.key=value` changes only the in-memory inspection
configuration.

**Reason:** This makes routing decisions observable and testable without
loading Docling or calling Kelpie, while preserving the later replaceable hard
path boundary.

## ADR-027: Phase 6 fast-path representation

**Decision:** Build the pdfplumber fast path from word geometry rather than from
the flattened `extract_text()` string. Words are grouped into lines, lines into
paragraphs by vertical gap, and clear two-column pages are read left column then
right column. A line whose font size is above the configured median ratio becomes
an inferred heading. Consecutive list lines become one Markdown list block, and
rectangular tables become GFM pipe tables. Unsupported or ragged tables remain
on the existing hard-path route.

**Reason:** Geometry is the smallest deterministic seam that can preserve
reading order and distinguish headings without introducing a layout dependency
on TEXT pages. Normalisation remains exclusively in `normalize.py`.

## ADR-028: Phase 6 cache and metrics

**Decision:** Use a JSON-only disk cache rooted by source SHA-256. Docling page
entries and vision image/page entries include their stage, input identity,
versioned prompt/model, and output-affecting configuration in the key. Cache
hits restore deterministic content but do not create current-run call records or
add historical tokens to current-run totals. `--no-cache` disables reads and
writes for that conversion.

`run.json` derives vision token totals and call counts from the recorded calls;
missing service usage remains marked `estimated` by the backend. The forced
`full-vision` and `docling-only` policies reuse the same page loop: the former
transcribes every rendered page and disables image extraction, while the latter
uses Docling for every page and saves images without vision calls.

**Reason:** Keeping cache state and operational metrics at adapter boundaries
prevents stale usage totals and keeps benchmark measurements comparable. The
Docling adapter continues to reject missing local artifacts unless the explicit
controlled-development remote-download opt-in is set.
