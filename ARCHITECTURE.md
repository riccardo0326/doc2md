# ARCHITECTURE — `doc2md`

> Companion to `PROJECT-SPEC.md`. If the two disagree, the spec's requirements win and this file must be fixed (record it in `docs/decisions.md`).
> Library API names for third-party packages (pdfplumber, Docling) reflect their documented surface at time of writing; **verify against the installed versions in Phase 0** and record differences.

---

## 1. Principles

1. **Tiered by page, not by document.** Cheap method first; expensive method only where signals say it is needed.
2. **One data model for every method.** pdfplumber, Docling and vision all produce the same `Block` objects, so rendering, caching, metrics and benchmarks do not care where content came from.
3. **Pure core, impure edges.** Signals extraction, routing, normalisation and Markdown rendering are pure functions over data. I/O (files, Kelpie, Docling, cache) lives in thin adapters behind protocols.
4. **Explicit dependencies.** No globals, no singletons except one lazily created Docling converter *owned by its adapter instance*. Everything is passed via a `RunContext`.
5. **Provenance is not optional.** Every block carries `page` and `block_id`.
6. **Small.** Target < ~1,500 lines in `src/`. Prefer a library over custom code.
7. **Replaceable edges.** Kelpie, Docling, pdfplumber and the cache can each be swapped without touching the core.

## 2. High-level flow

```
                    ┌──────────────────────── RunContext ────────────────────────┐
                    │ config · vision backend · hard extractor · cache · metrics   │
                    └──────────────────────────────────────────────────────────────┘
 input.pdf
    │
    ▼
┌────────────┐   per page    ┌─────────┐   TEXT      ┌──────────────┐
│ PdfSource  │──────────────▶│ inspect │────────────▶│ FastExtractor│──┐
│ (pdfplumber│  PageSignals  │ +router │             │ (pdfplumber) │  │
│  + pdfium) │               └─────────┘   COMPLEX/  ├──────────────┤  │ list[Block]
└────────────┘                             SCANNED   │ HardExtractor│──┤ per page
    │                                      ──────────▶│ (Docling)    │  │
    │ images per page                                 └──────────────┘  │
    ▼                                                                   ▼
┌────────────┐   keep/skip   ┌──────────────┐  describe   ┌─────────────────────┐
│ ImageFinder│──────────────▶│ ImageFilter  │────────────▶│ VisionBackend(Kelpie)│
└────────────┘               └──────────────┘             └─────────────────────┘
                                                                   │ ImageRecord
                                                                   ▼
                                           ┌──────────────────────────────────────┐
                                           │ assemble ConvertedDocument (pure)     │
                                           └──────────────────────────────────────┘
                                                      │
                          ┌───────────────────────────┼─────────────────────────┐
                          ▼                           ▼                         ▼
                   render_markdown()           write sidecar JSON         write run.json
                      (pure)                   (Pydantic dump)         (metrics, per-call)
```

`full-vision` and `docling-only` pipelines reuse the same stages with a different **routing policy** (`always_vision`, `always_hard`) — see §6.6. They are not separate code paths. `docling-only` is a disposable development diagnostic; it is not an enterprise deployment mode.

## 3. Folder and file structure

```
doc2md/                              # repo root
├─ AGENTS.md                         # short agent rules, points to PROJECT-SPEC.md and this file
├─ PROJECT-SPEC.md
├─ ARCHITECTURE.md
├─ README.md                         # written in Phase 9
├─ THIRD_PARTY_NOTICES.md            # Phase 9
├─ pyproject.toml                    # extras: [hard] docling, [bench] extras, [dev]
├─ .gitignore                        # samples/, out/, bench_runs/, .doc2md_cache/, .env
├─ config/
│  └─ default.toml                   # all defaults (see §9)
├─ prompts/
│  ├─ describe_image.v1.txt          # versioned prompt files, never inline strings
│  ├─ transcribe_page.v1.txt         # used by full-vision pipeline
│  └─ judge.v1.txt                   # LLM-as-judge prompt
├─ src/doc2md/
│  ├─ __init__.py                    # exports: convert, ConversionResult, Config
│  ├─ api.py                         # public facade: convert(), inspect_pdf()
│  ├─ cli.py                         # Typer app: convert / inspect / bench ...
│  ├─ config.py                      # Pydantic settings: defaults.toml + user toml + env + CLI overrides
│  ├─ context.py                     # RunContext (dependency container) + build_context()
│  ├─ models.py                      # ALL Pydantic data models (§5)
│  ├─ errors.py                      # exception hierarchy (§10)
│  ├─ metrics.py                     # MetricsCollector (thread-safe), UsageRecord
│  ├─ cache.py                       # DiskCache (get/put by key), key builders
│  ├─ converters/
│  │  ├─ __init__.py
│  │  ├─ base.py                     # Converter protocol (§6.1)
│  │  ├─ registry.py                 # extension -> Converter lookup
│  │  └─ pdf/
│  │     ├─ __init__.py              # PdfConverter: orchestrates the page loop
│  │     ├─ source.py                # opens PDF, yields pdfplumber pages, renders page images (pypdfium2)
│  │     ├─ signals.py               # compute_signals(page) -> PageSignals   (pure given page object)
│  │     ├─ router.py                # classify(signals, cfg) -> RouteDecision  (pure)
│  │     ├─ fast.py                  # FastExtractor: pdfplumber page -> list[Block]
│  │     ├─ hard.py                  # HardExtractor protocol + DoclingExtractor (lazy import)
│  │     ├─ images.py                # find, filter, hash, save images
│  │     └─ normalize.py             # text normalisation (ligatures, hyphens, whitespace)   (pure)
│  ├─ vision/
│  │  ├─ base.py                     # VisionBackend protocol, VisionResult, Usage
│  │  ├─ kelpie.py                   # KelpieVisionBackend (shaped by Phase 0 discovery)
│  │  └─ fake.py                     # FakeVisionBackend (deterministic, for tests)
│  ├─ render/
│  │  ├─ markdown.py                 # render_markdown(doc, opts) -> str  (pure)
│  │  └─ sidecar.py                  # write_json(doc), write_run_json(stats)
│  └─ bench/
│     ├─ suite.py                    # suite.toml loader (Pydantic)
│     ├─ pipelines.py                # pipeline registry: tiered, full-vision, docling-only, baseline_current
│     ├─ baseline_current.py         # adapter for the existing EDAG system (shaped by Phase 0)
│     ├─ runner.py                   # runs (doc x pipeline x repetition) -> results.csv
│     ├─ report.py                   # results.csv (+scores) -> report.md
│     ├─ review.py                   # stratified sampling, blind review sheet, unblinding map
│     └─ judge.py                    # LLM-as-judge client + robust parser
├─ bench/
│  ├─ suite.toml                     # which docs, tags, pipelines (paths point into samples/)
│  └─ rubric.md                      # manual scoring rubric (0-2 per criterion)
├─ docs/
│  ├─ discovery.md                   # Phase 0 output
│  ├─ decisions.md                   # ADR-style log
│  ├─ licenses.md                    # pip-licenses output
│  ├─ kelpie-example.md              # working Kelpie call, no secrets
│  └─ FINDINGS.md                    # Phase 9
├─ samples/                          # CONFIDENTIAL, git-ignored (Oz/Hannes documents)
├─ out/                              # outputs of `convert`, git-ignored
├─ bench_runs/                       # outputs of `bench run`, git-ignored
└─ tests/
   ├─ conftest.py                    # fixtures: synthetic PDF builders, FakeVisionBackend, tmp cache
   ├─ fixtures/                      # tiny committed PDFs / golden files (no confidential data)
   ├─ unit/                          # normalize, router, markdown render, cache keys, metrics, config
   ├─ integration/                   # pdf end-to-end with fake vision; docling (@slow); kelpie (@kelpie)
   └─ test_licenses.py
```

Dependency direction (enforced by a simple import test): `models` ← `normalize/router/render` ← `converters` ← `api/cli`; `bench` may import everything; nothing in `converters` imports `bench`; `vision` and `hard` implementations are only imported by `context.build_context()`.

## 4. Public contracts

### 4.1 Python API (`doc2md.api`)

```python
def convert(
    source: str | os.PathLike[str],
    out_dir: str | os.PathLike[str] | None = None,   # None -> do not write files, return in memory
    *,
    pipeline: Literal["tiered", "full-vision", "docling-only"] = "tiered",
    config: Config | None = None,                     # None -> defaults (+ env)
    pages: PageSelection | None = None,               # e.g. "1-5,9"
    context: RunContext | None = None,                # inject fakes in tests / reuse across docs
    strict: bool = False,                             # raise ConversionFailed if any page failed
) -> ConversionResult: ...

def inspect_pdf(source, *, config: Config | None = None) -> list[PageDecision]: ...
```

```python
class ConversionResult(BaseModel):
    document: ConvertedDocument          # full in-memory data model (§5)
    markdown: str
    markdown_path: Path | None
    json_path: Path | None
    run_path: Path | None
    stats: RunStats                      # same content as run.json
```

Rules: `convert` never mutates global state; same input + same config + same backends ⇒ byte-identical Markdown and JSON (vision outputs cached; vision `temperature=0`). Public API additions require a `decisions.md` entry.

### 4.2 CLI (Typer; `doc2md --help` must be accurate)

| Command | Purpose |
|---------|---------|
| `doc2md convert INPUT [-o OUTDIR] [--pipeline P] [--config FILE] [--set KEY=VALUE ...] [--pages SPEC] [--no-images] [--no-cache] [--page-markers/--no-page-markers] [--strict]` | Convert one file |
| `doc2md inspect INPUT [--config FILE] [--set ...]` | Print per-page signals and class; no conversion |
| `doc2md bench run --suite FILE [--pipelines a,b] [--reps N] [--out DIR]` | Run benchmark |
| `doc2md bench report RUN_DIR` | Build `report.md` from `results.csv` (+ scores if present) |
| `doc2md bench review-sheet RUN_DIR [--n 30] [--seed 42]` | Create blind manual-review sheet |
| `doc2md bench judge RUN_DIR [--model M]` | LLM-as-judge scoring |
| `doc2md kelpie ping` | Check Kelpie connectivity, list models (added in Phase 5) |

Exit codes: `0` success (warnings allowed) · `1` unexpected error · `2` usage/config error · `3` `--strict` and ≥ 1 page failed · `4` Kelpie unreachable when the pipeline requires it. Logs go to stderr; stdout is reserved for machine-readable output (`inspect --json`, paths).

Output layout of `convert`:

```
out/<stem>/
├─ <stem>.md
├─ <stem>.json            # sidecar, schema §5.3
├─ run.json               # metrics §11
└─ images/
   └─ p0003-i01.png       # kept images only
```

## 5. Data model

All models live in `models.py`, are Pydantic v2, **frozen** (immutable) where they flow between stages, and serialisable to JSON. Page numbers are **1-based and always refer to the original document**, never to a sub-PDF.

### 5.1 Models

```python
PageClass   = Literal["TEXT", "COMPLEX", "SCANNED"]
Method      = Literal["pdfplumber", "docling", "vision"]
BlockType   = Literal["heading", "paragraph", "list", "table", "figure", "code", "other"]
PageStatus  = Literal["ok", "failed", "skipped"]

class BBox(BaseModel):                       # PDF points, origin top-left, as pdfplumber reports
    x0: float; y0: float; x1: float; y1: float

class Provenance(BaseModel):
    page: int
    bbox: BBox | None = None                 # optional in v1
    source: Method

class Block(BaseModel):
    block_id: str                            # "p0003-b002": zero-padded page, per-page counter, stable
    type: BlockType
    markdown: str                            # already-rendered Markdown for this block
    text: str                                # plain text version (for search / judge)
    level: int | None = None                 # heading level
    provenance: Provenance
    meta: dict[str, str | int | float | bool] = {}   # e.g. {"table_rows": 4, "table_cols": 3}

class PageSignals(BaseModel):
    chars: int
    words: int
    image_area_ratio: float                  # sum of image bbox areas / page area, 0..1
    image_count: int
    table_count: int
    table_irregular: bool                    # merged/None cells or ragged rows detected
    garbled_ratio: float                     # share of "(cid:N)", U+FFFD, private-use chars
    has_text_layer: bool

class RouteDecision(BaseModel):
    page: int
    page_class: PageClass
    reasons: list[str]                       # human-readable, e.g. ["chars<50", "image_area>0.6"]
    signals: PageSignals

class PageResult(BaseModel):
    page: int
    status: PageStatus
    page_class: PageClass
    method: Method | None                    # None if failed/skipped
    blocks: list[Block]
    warnings: list[str] = []
    error: str | None = None                 # short message if failed
    duration_s: float

class ImageRecord(BaseModel):
    image_id: str                            # "p0003-i01"
    page: int
    bbox: BBox | None
    width_px: int; height_px: int
    sha256: str
    status: Literal["described", "skipped", "failed"]
    skip_reason: Literal["too_small", "bad_aspect", "duplicate"] | None = None
    path: str | None                         # relative path under out dir, if saved
    description: str | None
    usage: Usage | None

class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated: bool                          # True if not reported by Kelpie

class ConvertedDocument(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    source: SourceInfo                       # name, sha256, size_bytes, page_count
    pipeline: str
    pages: list[PageResult]
    images: list[ImageRecord]
    tool: ToolInfo                           # doc2md version, pdfplumber/docling versions, config hash
```

### 5.2 Markdown conventions (the citation contract)

- Each page starts with `<!-- page: N -->` on its own line (config `render.page_markers`, default **on**).
- Each block is preceded by `<!-- block: p0003-b002 -->` only when `render.block_anchors` is on (default **off** in Markdown, always present in JSON). Rationale: anchors cost tokens; page markers are enough for page-level citation, and JSON gives block-level.
- Tables use GFM pipe tables. Where a table cannot be rendered as GFM (merged cells), render the best-effort GFM plus a `<!-- table: simplified -->` comment.
- Images: `![Figure p3-i01](images/p0003-i01.png)` followed by a blockquote `> **Image description (p3-i01):** …`.
- A failed page renders as `<!-- page: N failed: <reason> -->`.
- Encoding UTF-8, `\n` line endings, single trailing newline.

### 5.3 Sidecar JSON (`<stem>.json`)

Serialisation of `ConvertedDocument` (`model_dump(mode="json")`), keys in model order, 2-space indent, UTF-8, no NaN. Excerpt:

```json
{
  "schema_version": "1.0",
  "source": {"name": "report.pdf", "sha256": "…", "size_bytes": 482113, "page_count": 12},
  "pipeline": "tiered",
  "pages": [
    {
      "page": 3, "status": "ok", "page_class": "COMPLEX", "method": "docling",
      "duration_s": 6.41, "warnings": [], "error": null,
      "blocks": [
        {"block_id": "p0003-b001", "type": "heading", "level": 2,
         "markdown": "## 3. Results", "text": "3. Results",
         "provenance": {"page": 3, "bbox": null, "source": "docling"}, "meta": {}}
      ]
    }
  ],
  "images": [
    {"image_id": "p0003-i01", "page": 3, "status": "described", "skip_reason": null,
     "width_px": 1024, "height_px": 640, "sha256": "…", "path": "images/p0003-i01.png",
     "description": "Bar chart comparing …",
     "usage": {"input_tokens": 812, "output_tokens": 96, "total_tokens": 908, "estimated": false}}
  ],
  "tool": {"doc2md": "0.1.0", "pdfplumber": "…", "docling": "…", "config_hash": "…"}
}
```

Any breaking change bumps `schema_version`.

## 6. Components

### 6.1 `Converter` protocol and registry (extensibility for other formats)

```python
class Converter(Protocol):
    name: str
    extensions: tuple[str, ...]              # (".pdf",)
    def convert(self, source: Path, ctx: RunContext, pages: PageSelection | None) -> ConvertedDocument: ...
```

`registry.get_converter(path)` looks up by lowercase extension; unknown extension ⇒ `UnsupportedFormat`. Future converters (docx, xlsx, eml) implement the same protocol and must emit `Block`s with `provenance.page` replaced by the format's natural location unit (sheet+cell range, paragraph index, email part); this requires widening `Provenance` with an optional `location: str` — **do not implement now**, but do not hard-code "page" assumptions in `render/` beyond reading `provenance.page`.

### 6.2 PDF converter: inspect → route → extract

`PdfConverter.convert` loop (sequential over pages; see §8 for concurrency):

```
open source (pdfplumber.open) and pdfium handle (for page rendering)
for each selected page:
    signals  = compute_signals(page)                     # pure given page object
    decision = router.classify(signals, cfg.router, policy)   # pure
    result   = extract(page, decision)                   # fast | hard | vision, with try/except -> PageResult
images = find_images(...) -> filter -> save -> describe (bounded thread pool)
doc    = assemble(...)
```

**Signals (pdfplumber only):**
- `chars`, `words`: from `page.chars` / `extract_words`.
- `image_area_ratio`: sum of `page.images` bounding boxes clipped to page / page area.
- `table_count`, `table_irregular`: `page.find_tables()`; irregular if any extracted table has `None`/empty merged cells above `cfg.router.table_none_ratio` or inconsistent column counts.
- `garbled_ratio`: share of characters that are U+FFFD, private-use area, or matched `\(cid:\d+\)` in extracted text.
- `has_text_layer`: `chars >= cfg.router.min_chars_text_layer`.

**Router rules (first match wins; thresholds in config):**

| Order | Condition | Class |
|-------|-----------|-------|
| 1 | `not has_text_layer` **or** (`chars < min_chars` and `image_area_ratio >= scan_image_ratio`) | `SCANNED` |
| 2 | `garbled_ratio >= max_garbled` | `COMPLEX` (reason `garbled_text`) |
| 3 | `table_irregular` | `COMPLEX` (reason `irregular_table`) |
| 4 | `image_area_ratio >= complex_image_ratio` and `chars < image_page_min_chars` | `COMPLEX` (reason `image_dominant`) |
| 5 | otherwise | `TEXT` |

Defaults (to be tuned in Phase 9 on real documents): `min_chars=50`, `min_chars_text_layer=10`, `scan_image_ratio=0.6`, `max_garbled=0.02`, `table_none_ratio=0.15`, `complex_image_ratio=0.4`, `image_page_min_chars=400`. `RouteDecision.reasons` must always name the rule(s) that fired so misclassifications are debuggable.

**Policies** (what `pipeline` maps to): `tiered` uses the router as is; `docling-only` overrides every page to hard; `full-vision` overrides every page to vision (§6.6).

**Fast extractor** (`fast.py`): from pdfplumber page → `list[Block]`: words grouped into lines by `top` tolerance, lines into paragraphs by vertical gap, multi-column handled by a simple column split when a clear vertical gutter exists (otherwise single column, flagged by a warning); headings by font-size relative to page median (config `fast.heading_ratio`, default 1.25); bullet/number prefixes → list; simple tables via `page.extract_tables()` → GFM. All text passes through `normalize.normalize_text()`.

**Normalisation** (`normalize.py`, pure, table-driven tests): explicit mapping for U+FB00–FB06 (ﬀ→ff, ﬁ→fi, ﬂ→fl, ﬃ→ffi, ﬄ→ffl, ﬅ/ﬆ→st); remove soft hyphen U+00AD; repair end-of-line hyphenation: a hyphen at the end of a line followed by a line starting with a **lowercase** letter is removed and the halves joined (`exam-\nple` → `example`, `Ober-\nflächen` → `Oberflächen`); keep the hyphen when the next line starts with an uppercase letter or a digit, or when the part before the hyphen is ≤ 2 characters (e.g. `E-\nMail` stays `E-Mail`); mid-line hyphens are never touched (`state-of-the-art`). Known limitation: a genuine compound that happens to break at its hyphen before a lowercase letter will be joined — log such joins at DEBUG so they can be reviewed; collapse repeated spaces; do **not** apply blanket NFKC (it would damage `²`, `½`, `™`); do not alter umlauts/ß. This module is the **only** place where character fixes may live.

### 6.3 Hard extractor — Docling adapter

The enterprise hard path is Kelpie-backed: it renders the selected page and
uses the discovered `VisionBackend.transcribe_page()` contract to call models
hosted locally on EDAG servers. No model file is installed on the enterprise
PC. The Kelpie hard-page adapter is a follow-up implementation seam; until it
exists, hard pages fail in isolation or use the text-backed fallback where
eligible.

```python
class HardExtractor(Protocol):
    def extract(self, source: Path, pages: Sequence[int], ctx: RunContext) -> dict[int, list[Block]]: ...
        # keys are ORIGINAL page numbers; raises HardExtractionError per page via result wrapper
```

`DoclingExtractor` rules:
- `import docling` **inside** `__init__`/first call only (lazy). One `DocumentConverter` instance per `DoclingExtractor`, created on first use, reused for all pages of the run (and across documents if the same `RunContext` is reused by the benchmark).
- Docling is a disposable development/diagnostic adapter only. Enterprise PCs must not install, copy, provision, or download its OCR/layout model artifacts. Pipeline options remain CPU, table structure enabled, and **picture description/classification off** when the adapter is explicitly exercised outside the enterprise runtime.
- If the development adapter is unavailable, or if the enterprise Kelpie-backed hard path is not implemented, raise `HardExtractionError` before initializing the pipeline. The converter records the affected page as failed and continues; it never disables TLS verification or suggests local model provisioning.
- Page selection: preferred is Docling's page-range option of `convert(...)`; if unavailable in the installed version, create a temporary sub-PDF containing only routed pages (pypdfium2 `import_pages`) and keep a `sub_index -> original_page` map. Whichever is used, **map back to original page numbers**. Phase 0 records which one works.
- Batch all routed pages of a document in **one** call where contiguous ranges allow, to amortise overhead; otherwise one call per contiguous range.
- Map Docling items to `Block`: section headers → `heading` (level from Docling), text → `paragraph`, list items → `list`, tables → `table` (Markdown via Docling table export, `meta` holds rows/cols), pictures → handled by the image stage (no `figure` block created here, to avoid double work). `Provenance.source="docling"`, `bbox` copied if available.
- Cache key per page: `sha256(file) + page + "docling" + docling_version + hard-config-hash`.

### 6.4 Image stage (`images.py`)

1. **Find:** per page, from pdfplumber `page.images` (bbox) and pixel data via pdfium rendering of that bbox region (render at `cfg.images.render_dpi`, default 150) — consistent across scanned and digital pages. *Scanned pages:* the full-page image is not an "embedded figure": skip image extraction on `SCANNED` pages unless Docling reports distinct pictures (v1: skip, note in decisions).
2. **Filter (pure, config-driven):** `min_width_px=64`, `min_height_px=64`, `min_area_px=10_000`, aspect ratio within `[1/8, 8]`, duplicate by SHA-256 of pixel bytes (describe once, reference many). Skipped images are recorded with `skip_reason`.
3. **Save:** PNG to `images/p{page:04d}-i{n:02d}.png`.
4. **Describe:** `VisionBackend.describe_image()` using `prompts/describe_image.v1.txt` (+ language hint `en|de|auto`), bounded `ThreadPoolExecutor(cfg.vision.max_workers)`; each call recorded in metrics; failures yield `status="failed"`.
5. **Placement:** the image record is inserted after the block that precedes it vertically (by bbox `top`); if no bbox, at the end of the page.

### 6.5 Vision backend and the Kelpie adapter

```python
class Usage(BaseModel): ...   # §5.1

class VisionResult(BaseModel):
    text: str
    usage: Usage
    model: str
    latency_s: float
    request_id: str | None = None

class VisionBackend(Protocol):
    name: str
    model: str
    def describe_image(self, image_png: bytes, *, prompt_id: str, lang: str = "auto") -> VisionResult: ...
    def transcribe_page(self, image_png: bytes, *, prompt_id: str, lang: str = "auto") -> VisionResult: ...
```

Contract rules for every implementation:
- Deterministic settings (`temperature=0`, fixed `max_tokens` from config).
- Timeouts and **retry with exponential backoff + jitter** (default 3 attempts) on transient errors only (timeouts, 429, 5xx); permanent errors raise `VisionError` immediately.
- Never logs image bytes or full prompts at INFO level.
- Fills `Usage` from the service response; if the service does not report usage, estimate (A5 in the spec) and set `estimated=True`.
- Raises `VisionUnavailable` (→ exit code 4 if the pipeline requires vision) when unreachable.

`KelpieVisionBackend` is written **after Phase 0**, following the calling convention found in the reference implementation (`C:\Users\rp99480\dev\ai4tc_webapp`, read-only) and confirmed by `scripts/kelpie_probe.py` and `docs/kelpie-example.md`. Default approach: a **thin own client** (≈ 100 lines) reproducing that convention, not an import of the reference project; any reuse of its code needs the human's confirmation. Until Phase 0 is signed off only `FakeVisionBackend` exists (returns `"[fake description of <sha8>]"` with deterministic fake usage, can be told to fail on chosen inputs). Config for Kelpie (`[vision.kelpie]` in toml): `base_url`, `model`, `timeout_s`, `max_retries`; **secrets (API key/token) only via environment variables** named in Phase 0. A `doc2md kelpie ping` command validates connectivity and lists vision-capable models.

### 6.6 Pipelines

| Pipeline | Routing policy | Page extraction | Images stage |
|----------|---------------|-----------------|--------------|
| `tiered` | router | TEXT→fast, COMPLEX/SCANNED→hard | on (filter + describe) |
| `full-vision` | all pages → vision | render page at `cfg.vision.page_dpi` (default 150) → `transcribe_page` → Markdown block(s) with `source="vision"` | **off** (page transcription already describes images; avoids double counting) |
| `docling-only` | all pages → hard | Docling development diagnostic only | on |
| `baseline_current` (bench only) | external | black-box adapter, see §7.3 | n/a |

A `Pipeline` is a small dataclass `(name, policy, images_enabled)`; `bench/pipelines.py` registers them. No subclassing.

## 7. Benchmark architecture

### 7.1 Suite file (`bench/suite.toml`)

```toml
[suite]
name = "oz-hannes-sample-v1"
repetitions = 3                    # for time; median reported
cold_cache = true

[[documents]]
id = "doc01"
path = "samples/doc01.pdf"
tags = ["digital", "tables", "en"]

[[documents]]
id = "doc02"
path = "samples/doc02_scan.pdf"
tags = ["scanned", "de"]

[[pipelines]]
name = "tiered"
[[pipelines]]
name = "full-vision"
[[pipelines]]
name = "docling-only"
[[pipelines]]
name = "baseline_current"
```

### 7.2 Output layout and `results.csv`

```
bench_runs/<YYYYMMDD-HHMMSS>/
├─ suite.toml                       # copy for reproducibility
├─ env.json                         # versions, machine info (cores/RAM), config hash, Kelpie model names
├─ results.csv                      # one row per (doc, pipeline, rep)
├─ outputs/<doc_id>/<pipeline>/rep1/…   # md, json, run.json, images
├─ review/                          # Phase 8: review_sheet.csv, unblind_map.json
├─ scores_manual.csv                # filled by human
├─ scores_judge.json
└─ report.md
```

`results.csv` columns (exact, in this order):

```
run_id, doc_id, pipeline, rep, pages_total, pages_text, pages_complex, pages_scanned,
pages_failed, images_found, images_described, images_skipped,
vision_calls, input_tokens, output_tokens, total_tokens, tokens_estimated,
docling_pages, wall_time_s, time_easy_pages_s, time_hard_pages_s,
output_chars, cache_hits, error
```

`time_easy_pages_s`/`time_hard_pages_s` are the summed per-page durations of `TEXT` vs hard/vision pages (empty for `baseline_current`). Tokens for `baseline_current` come from whatever the adapter can read (§7.3); if unavailable the column is empty and the report states that comparison is time/quality only. `output_chars` is informational; downstream-token estimation of the Markdown is optional and flagged `estimated`.

### 7.3 `baseline_current` adapter

```python
class BaselineAdapter(Protocol):
    def run(self, source: Path, out_dir: Path) -> BaselineResult: ...

class BaselineResult(BaseModel):
    markdown_path: Path            # whatever text it produced, saved as .md
    wall_time_s: float
    usage: Usage | None            # None if cannot be read
    pages: int | None
```

The existing software is delivered to Riccardo next week, so the real implementation (subprocess CLI, HTTP call, or Python import) is decided then; until that time only a `FakeBaselineAdapter` exists and `baseline_current` is optional in the suite. It is configured in `bench/suite.toml` (`[baseline_current] command = "..."` or similar). The harness treats it as a black box and never modifies it. The benchmark must run it under the same conditions (same machine, same documents, same Kelpie model where possible; record any difference in `env.json`).

### 7.4 Manual review and judge

- `review.select_pages(run_dir, n, seed)` → stratified by page class (from the `tiered` run's `RouteDecision`), reproducible with the seed.
- `review_sheet.csv` columns: `sample_id, doc_id, page, page_class, page_image_path, output_A, output_B, output_C, output_D, text_A_score, special_A_score, table_A_score, figure_A_score, order_A_score, …` (one score group per label). Labels are shuffled per sample with the seed; `unblind_map.json` maps `sample_id → {A: pipeline, …}`. The reviewer never sees pipeline names.
- `bench/rubric.md` defines criteria and 0/1/2 anchors (e.g. table fidelity 2 = all cells and headers correct, 1 = minor cell errors, 0 = unusable).
- `judge.py`: sends page image (if the judge model is vision-capable) or the extracted text of the reference page plus candidate output, the rubric and a strict JSON answer schema; parses with tolerant extraction (first JSON object), validates with Pydantic, returns `{"judge_error": "..."}` for unparseable output; temperature 0; results cached.
- Report: mean score per criterion and pipeline (manual and judge separately), agreement between manual and judge on the overlap, confidence note about sample size.

## 8. State management and concurrency

The system is a **batch pipeline**, not a long-running service, so state is deliberately minimal.

1. **Immutable data flows between stages.** Pydantic frozen models; stages return new objects. No stage mutates another's output.
2. **`RunContext` is the only carrier of cross-cutting state.** Contains: `config` (frozen), `vision: VisionBackend`, `hard: HardExtractor`, `cache: DiskCache`, `metrics: MetricsCollector`, `clock` (injectable for tests), `logger`. Built once by `build_context()`; fakes are injected in tests by constructing the context manually.
3. **The disk cache is the only persistent state** (`.doc2md_cache/`, §11). Keys are content-addressed; entries are immutable JSON written atomically (write to temp file in same directory, `os.replace`). No locking needed for single-process use; concurrent writers of the same key are harmless (same content).
4. **Heavy objects are owned by their adapter and created lazily:** the optional development Docling `DocumentConverter` (expensive model load) stays inside `DoclingExtractor`; the HTTP client for approved remote services stays inside its adapter. Both are closed via `RunContext.close()` / context manager.
5. **Concurrency model:**
   - Page loop: **sequential** (pdfplumber page objects are not thread-safe and Docling on CPU is already multi-threaded internally).
   - Vision calls (images, and pages in `full-vision`): **bounded `ThreadPoolExecutor`** (`vision.max_workers`, default 4; tune to what the local Kelpie model tolerates — Phase 0 records the safe value). Results are re-ordered by page/image index before assembly so output is deterministic.
   - `MetricsCollector` is thread-safe (a lock around appends).
6. **Page-level failure isolation:** each page's extraction is wrapped; exceptions become `PageResult(status="failed", error=...)`. Image-level failures become `ImageRecord(status="failed")`.
7. **Determinism:** fixed seeds in benchmark sampling, `temperature=0`, sorted iteration, no timestamps inside Markdown/JSON content (timestamps only in `run.json`/`env.json`).
8. **Benchmark isolation:** each (doc, pipeline, rep) uses a fresh output dir and, when `cold_cache=true`, a fresh cache directory. Any disposable development Docling load is measured separately and never treated as an enterprise runtime requirement.

## 9. Configuration

Layering (later wins): `config/default.toml` → user file (`--config`) → env vars `DOC2MD_<SECTION>__<KEY>` → CLI `--set section.key=value`. Pydantic validates; unknown keys are errors. The effective config is hashed (`config_hash`) and stored in outputs and cache keys (only fields that affect output are hashed — mark with `Field(json_schema_extra={"affects_output": True})`).

```toml
[router]
min_chars = 50
min_chars_text_layer = 10
scan_image_ratio = 0.6
max_garbled = 0.02
table_none_ratio = 0.15
complex_image_ratio = 0.4
image_page_min_chars = 400

[fast]
heading_ratio = 1.25
column_gutter_min_pt = 20

[hard]
engine = "docling-dev-only"        # enterprise target: Kelpie-backed hard path
languages = ["en", "de"]
threads = 4
page_dpi = 200
# No enterprise model/artifact path exists. Hard processing uses Kelpie/Helios on EDAG servers.

[images]
enabled = true
render_dpi = 150
min_width_px = 64
min_height_px = 64
min_area_px = 10000
max_aspect = 8.0
dedupe = true

[vision]
backend = "kelpie"             # "fake" for tests
max_workers = 4
page_dpi = 150
max_tokens = 800
transcribe_max_tokens = 1600
temperature = 0.0
timeout_s = 120
max_retries = 3
describe_prompt = "describe_image.v1"
transcribe_prompt = "transcribe_page.v1"

[vision.kelpie]                # shaped by Phase 0
base_url = ""
model = ""
# secrets: environment variables only (names recorded in docs/discovery.md)

[render]
page_markers = true
block_anchors = false

[cache]
enabled = true
dir = ".doc2md_cache"

[bench]
repetitions = 3
review_sample_size = 30
seed = 42
```

## 10. Error handling

Exception hierarchy (`errors.py`): `Doc2MdError` ← `ConfigError`, `UnsupportedFormat`, `SourceError` (cannot open/corrupt/encrypted PDF), `PageExtractionError`, `HardExtractionError`, `VisionError` ← `VisionUnavailable`, `CacheError`, `ConversionFailed` (raised by `strict`).

| Situation | Behaviour |
|-----------|-----------|
| File missing/unreadable/encrypted | `SourceError`, exit 1 (encrypted: message says password unsupported in v1) |
| One page fails in fast or hard path | page `failed`, placeholder in Markdown, continue; warning in `run.json` |
| Docling unavailable or Kelpie hard path not implemented | `HardExtractionError` for those pages with a clear enterprise-boundary message; pages still marked failed, others continue |
| Kelpie unreachable | image stage: images marked `failed`, document completes, warning; `full-vision` pipeline: exit 4 |
| Kelpie transient error | retry with backoff; then failed record |
| Invalid config | `ConfigError`, exit 2, message names the key |
| Cache corrupt entry | treated as miss, entry deleted, warning |

Never swallow exceptions silently: each caught exception is logged at WARNING with page/image id and stored in the result.

## 11. Metrics and cache

### 11.1 `run.json`

```json
{
  "run_id": "…", "started_at": "…", "pipeline": "tiered",
  "source": {"name": "report.pdf", "sha256": "…", "pages": 12},
  "config_hash": "…",
  "totals": {
    "wall_time_s": 41.7,
    "pages": {"total": 12, "text": 8, "complex": 3, "scanned": 1, "failed": 0},
    "vision": {"calls": 5, "input_tokens": 4120, "output_tokens": 410, "total_tokens": 4530, "estimated": false},
    "docling": {"pages": 4, "time_s": 28.3},
    "cache": {"hits": 0, "misses": 9}
  },
  "pages": [{"page": 1, "class": "TEXT", "method": "pdfplumber", "duration_s": 0.09, "reasons": []}],
  "calls": [{"kind": "describe_image", "id": "p0003-i01", "model": "…", "latency_s": 3.2,
             "input_tokens": 812, "output_tokens": 96, "estimated": false, "cache_hit": false}],
  "warnings": []
}
```

`MetricsCollector` API: `record_page(...)`, `record_call(...)`, `record_cache(hit: bool)`, `snapshot() -> RunStats`. Totals are **derived** from the per-call records (never separately incremented) so they cannot drift.

### 11.2 Cache

- Directory `.doc2md_cache/<sha256(file)[:2]>/<sha256(file)>/<stage>/<key>.json`.
- Stages and keys: `docling/page{N:04d}-<hard_cfg_hash>-<docling_version>`; `vision-image/<image_sha256>-<prompt_id>-<model>-<vision_cfg_hash>`; `vision-page/page{N:04d}-<dpi>-<prompt_id>-<model>-<vision_cfg_hash>`.
- API: `get(stage, key) -> dict | None`, `put(stage, key, value)`. JSON only (no pickle).
- Disabled with `--no-cache` / `cache.enabled=false` (benchmarks use a fresh directory per run when `cold_cache`).
- Changing any `affects_output` config field changes the hash ⇒ different key ⇒ no stale hits.

## 12. Testing strategy

- **Framework:** pytest, `ruff` (lint+format), `mypy` (strict on `models`, `router`, `normalize`, `render`).
- **Synthetic fixtures built in code** (`conftest.py`): text PDF with N pages; PDF with real fl/fi ligature glyphs; table PDF (simple and with merged cells); PDF with an embedded raster image (large, tiny logo, duplicate); scanned PDF created by rasterising a text page and re-embedding it as an image-only page. Use a permissive PDF-generation library (e.g. reportlab BSD, or pypdfium2/Pillow) — confirm license in Phase 0.
- **Pure-function tests dominate:** router (table-driven with `PageSignals` dicts), normalizer (table-driven), Markdown renderer (golden files), config layering, cache keys, metrics derivation, review sampling/unblinding, report rendering from fixture CSV.
- **Integration:** full `convert()` with `FakeVisionBackend` and a fake `HardExtractor`; the real Docling test is `@pytest.mark.slow` (run explicitly); real Kelpie test is `@pytest.mark.kelpie` (skipped without env vars).
- **Architecture tests:** (a) `import doc2md; convert(text_pdf)` does not import `docling` (`sys.modules` check); (b) import-direction test per §3; (c) license test (`tests/test_licenses.py`).
- **Determinism test:** convert the same fixture twice, assert byte equality.
- **No confidential data in tests.** CI runs on synthetic fixtures only.

## 13. Dependencies (verify versions and licenses in Phase 0)

| Package | Use | Expected license |
|---------|-----|------------------|
| `pdfplumber` | fast path, signals | MIT |
| `pypdfium2` | page/region rendering, sub-PDF | BSD-3 / Apache-2.0 |
| `docling` (extra `[hard]`) | hard path | MIT |
| `pydantic` (v2) + `pydantic-settings` | models, config | MIT |
| `typer` | CLI | MIT |
| `httpx` (or Kelpie's own SDK) | Kelpie HTTP | BSD |
| `tenacity` | retry/backoff | Apache-2.0 |
| `Pillow` | image handling | HPND (permissive) |
| `tiktoken` (optional) | token estimation fallback | MIT |
| `pytest`, `ruff`, `mypy`, `pip-licenses` (dev) | quality | MIT/Apache/BSD |

Explicitly **excluded:** PyMuPDF / pymupdf4llm (AGPL), any GPL/AGPL package. Any addition requires a `docs/decisions.md` entry with its license.

## 14. Open architecture items (resolved in Phase 0, then recorded in `docs/decisions.md`)

1. Kelpie calling convention and whether usage is returned (shapes `kelpie.py`, `Usage.estimated`) — read from the `ai4tc_webapp` reference implementation and verified with `scripts/kelpie_probe.py`. Add `scripts/` to the folder tree when created.
2. Docling page selection mechanism in the installed version (page range vs sub-PDF) (§6.3).
3. Whether pdfplumber's `find_tables()` is reliable enough for the `table_irregular` signal on real samples; fallback is to route every page with ≥ 1 table to the hard path.
4. Safe `vision.max_workers` for the local Kelpie model.
5. How the `baseline_current` adapter is invoked and where its token usage can be read (§7.3) — blocked until the software is delivered next week; not needed before Phase 7.
6. Whether `SCANNED` pages should be sent to Docling OCR or directly to the vision model by default (v1 default: Docling; benchmark may compare both by adding a `scanned_engine` option if time allows).
