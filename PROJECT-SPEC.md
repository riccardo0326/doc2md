# PROJECT-SPEC — `doc2md`: tiered document-to-Markdown converter + benchmark

> Status: draft v1 · Owner: Riccardo Palazzi · Stakeholders: Amro Moustafa (receives findings), Shachar Oz (AI evangelist, provides sample documents), Hannes (product lead)
> Companion file: `ARCHITECTURE.md` (contracts, folder structure, state handling). Read both before writing any code.
> Language of code, comments, tests, commit messages: English.

---

## 0. How the agent must work (read first)

This project is built with an agentic coding workflow (opencode, GPT 5.6, vertical-slice / TDD style). Rules:

1. **One phase at a time.** Phases in section 7 are vertical slices. Finish a phase (all acceptance criteria green, tests passing) before starting the next. Do not scaffold future phases.
2. **Tests first.** For every acceptance criterion, write the failing test, then the minimum code to pass, then refactor.
3. **Never invent the Kelpie API.** Kelpie is an internal, undocumented-on-the-internet LLM gateway. Phase 0 discovers its real interface on the target machine. Until Phase 0 is signed off by the human, only `FakeVisionBackend` may be used.
4. **Stop and ask the human** when: a Phase 0 discovery item cannot be resolved, a library API differs from `ARCHITECTURE.md`, a threshold needs a business decision, or a requirement here is ambiguous. Record the question and answer in `docs/decisions.md`.
5. **Keep it small.** Target: the whole `src/` under ~1,500 lines of Python excluding tests. Prefer a maintained open-source library over custom code. No frameworks beyond those listed in `ARCHITECTURE.md`.
6. **Confidential data never leaves the EDAG machine and is never committed.** See section 5.
7. Update `docs/decisions.md` (short ADR-style entries) whenever a design choice deviates from or fills a gap in these files.

---

## 1. Context and problem

EDAG has a live system that converts PDFs to text for LLM use by **rendering every page as a screenshot and sending it to a vision model**. Known issues (from the discussion with Amro and Oz, 19 Oct 2026):

- Screenshot-for-every-page is **not cost/token efficient**: many pages are plain text and do not need vision.
- Special-character problems (example reported: the letter *f* followed by *l*, i.e. the **fl ligature**) are currently **hard-coded** around.
- Two PDF kinds exist: **digital** (has a text layer, plus images) and **scanned** (every page is an image).
- The current system extracts embedded images, gives each a textual description, and uses a rule to skip images not worth the effort (e.g. tiny logos). A smarter "is this image worth describing?" classifier was discussed but not built.
- Performance and licensing of libraries matter: heavy libraries have caused slowness before; licenses must be checked.

Hypothesis to test (Riccardo's proposal): **a tiered pipeline** — cheap per-page text extraction by default, expensive methods (OCR / layout analysis / vision) only on pages that need them — reads documents **better, faster and more cheaply** than the current all-vision approach.

Also raised in the call's summary (future, partly in scope as groundwork): a summary of any document type (xls, eml, doc, docx, pdf…) **with evidence**, i.e. the ability to cite the exact place in the document a claim came from.

## 2. Goals

| # | Goal | Measured by |
|---|------|-------------|
| G1 | Convert PDF → Markdown (+ JSON sidecar) with a tiered pipeline | Phases 1–6 |
| G2 | Handle text, tables, embedded images and scanned documents | Phases 3–5 |
| G3 | Preserve provenance (page number per block) so summaries can cite the source | Phase 1 (base), contract in ARCHITECTURE.md |
| G4 | Benchmark tiered vs current system vs full-vision, on **token consumption, time and quality** | Phases 7–9 |
| G5 | Deliver a go/no-go recommendation to Amro/Oz with numbers | Phase 9 |
| G6 | Leave a codebase that can become a reusable internal library | Package layout + `Converter` protocol |

## 3. Non-goals (v1)

- Other input formats (docx, xlsx, eml, …). **Only** the `Converter` protocol and registry exist so they can be added later; no implementation.
- Summarization itself. v1 only produces the provenance-rich Markdown/JSON that a summarizer would consume.
- Web service / FastAPI / Docker. (Library + CLI only. A service can wrap the library later.)
- GPU support, distributed processing, UI.
- Training or fine-tuning a classifier for "is this image worth describing". v1 uses simple rules (size/area/aspect thresholds, duplicate detection).
- Perfect output for every PDF. v1 must be *measurably better or cheaper*, not flawless.

## 4. Users and usage

- **Primary user now:** Riccardo (developer) running the CLI and the benchmark on an EDAG PC, **CPU only**.
- **Future users:** other EDAG products importing `doc2md` as a Python library.

Typical use:

```bash
doc2md convert report.pdf -o out/            # tiered pipeline, default config
doc2md inspect report.pdf                    # show per-page classification, no conversion
doc2md bench run --suite bench/suite.toml    # compare pipelines on sample docs
```

```python
from doc2md import convert
result = convert("report.pdf", out_dir="out/")
print(result.markdown_path, result.stats.vision_tokens_total)
```

## 5. Constraints

### 5.1 Environment
- Runs on an EDAG Windows or Linux PC (**assume Windows paths must work**; use `pathlib` everywhere). `pip`/`uv` allowed, Hugging Face model download allowed, **CPU only**.
- Python version: determined in Phase 0 (target ≥ 3.11).
- LLM access **only through Kelpie**, and only through **models that run locally on the EDAG server** (no external APIs, no public LLM endpoints). Credentials come from environment variables, never from files in the repo.

### 5.2 Data confidentiality
- Sample PDFs from Oz/Hannes and all outputs are confidential. They live in `samples/` and `out/`, both in `.gitignore`.
- Tests use only **synthetic PDFs generated in code** or public-domain PDFs committed deliberately as small fixtures.
- Disable third-party telemetry (`HF_HUB_DISABLE_TELEMETRY=1`, `DO_NOT_TRACK=1`); no network calls except package/model download (Phase 0/4) and Kelpie.
- Enterprise runtime machines must not depend on external model downloads at conversion time. Heavy model artifacts used by Docling must be provisioned locally; an unavailable artifact is an isolated hard-page failure, not a reason to disable TLS or abort the document.
- Benchmark reports shared with stakeholders contain metrics and short anonymised excerpts only, unless the human says otherwise.

### 5.3 Licensing
- Allowed: MIT, BSD, Apache-2.0, ISC, MPL-2.0 (as a library dependency).
- **Forbidden: GPL / AGPL / LGPL / SSPL or any non-commercial license** — in particular **PyMuPDF / pymupdf4llm are not allowed** (AGPL).
- Phase 0 produces `docs/licenses.md` from `pip-licenses` for the full dependency tree (including transitive). CI/test `tests/test_licenses.py` fails if a forbidden license appears.
- Keep each dependency's copyright/license notice (`THIRD_PARTY_NOTICES.md`, generated in Phase 9).

### 5.4 Performance and weight
- Heavy libraries (Docling and its models) must be **lazy-imported** and only loaded when a page actually routes to the hard path.
- Import time of `doc2md` for a text-only PDF must not load Docling (tested).

### 5.5 Languages
- Documents are in **English and German**. OCR configured for `en` + `de`. Text normalisation must keep umlauts and ß intact. The tokenizer/estimation must not assume English only.

## 6. Functional requirements

**FR1 — Per-page inspection.** For each page compute cheap signals (text length, image area ratio, table presence and quality, garbled-text ratio, text-layer presence) with pdfplumber only.

**FR2 — Page routing.** Classify every page as one of: `TEXT` (fast path OK), `COMPLEX` (tables/figures/garbled text → hard path), `SCANNED` (no usable text layer → hard path with OCR). Thresholds are configurable and printed by `doc2md inspect`.

**FR3 — Fast path.** `TEXT` pages: extract with pdfplumber, reconstruct reading order, headings (heuristic by font size), paragraphs, lists, simple tables → Markdown. Normalise ligatures (ﬁ ﬂ ﬀ ﬃ ﬄ ﬅ ﬆ), soft hyphens and line-break hyphenation **without hard-coded character special cases elsewhere**.

**FR4 — Hard path.** `COMPLEX` and `SCANNED` pages: converted by Docling (layout analysis, table structure, OCR en+de), **only for those pages**, producing Markdown blocks with the same data model as the fast path.

**FR5 — Image handling.** Extract embedded images from every page; skip images below configurable thresholds (min width/height/area, extreme aspect ratio, exact duplicates by hash); save kept images to `images/`; send them to the Kelpie vision model for a description; insert the description **inline** in the Markdown next to an image link. Descriptions are cached.

**FR6 — Provenance.** Every block in the JSON sidecar has `page` (1-based), `block_id`, `source` (`pdfplumber` | `docling` | `vision`), and optionally `bbox`. The Markdown contains page markers (`<!-- page: N -->`) and block anchors so a downstream summarizer can cite "page N, block X". Bounding boxes are **not required in v1** but the model has the field.

**FR7 — Failure isolation.** A failing page (exception, Kelpie timeout) never aborts the document: it is recorded with status `failed`, a placeholder is written in the Markdown, and conversion continues. `--strict` turns any failed page into a non-zero exit code.

**FR8 — Metrics.** Every run records: per-page route, method used, wall time, Kelpie calls, **input/output/total tokens per call** (reported by Kelpie, or estimated and flagged `estimated`), cache hits, and totals. Written to `run.json`.

**FR9 — Caching.** Results of expensive steps (Docling per page, Kelpie per image/page) are cached on disk, keyed by file hash + page/image + config hash. Benchmarks can disable the cache for fair timing.

**FR10 — Pipelines (for benchmark).** The same CLI/library can run:
- `tiered` — the proposal (default).
- `full-vision` — every page rendered to an image and transcribed by the Kelpie vision model (re-implementation of the current approach, used as an in-house baseline).
- `docling-only` — Docling on all pages (informational: tests the claim that Docling for everything is "overpowered").
- The **current EDAG system** is a black-box external pipeline (`baseline_current`) invoked by the benchmark harness via a configured command or adapter (Phase 0 defines how).

**FR11 — Benchmark.** A harness runs selected pipelines over a suite of documents and produces: metrics table (tokens, time, calls), quality review material (manual review sheet + LLM-as-judge scores), and a Markdown report with a go/no-go section.

## 7. Phases (vertical slices)

Each phase ends with: tests green, `ruff` + `mypy`/`pyright` clean, `docs/decisions.md` updated, short demo command in the phase's "Demo" line.

### Phase 0 — Environment & discovery (human + agent, no feature code)
Produce `docs/discovery.md` answering every item below with evidence (command output, short notes). **The agent stops here for human sign-off.**

- [ ] Python version, `uv`/`pip` availability, Windows vs Linux, CPU cores, RAM.
- [ ] Install `pdfplumber`, `docling`, `pypdfium2`; verify the Docling API on CPU with locally provisioned artifacts. Runtime model downloads are not an enterprise prerequisite; record missing-artifact/TLS limitations, time per page, RAM, and installed versions.
- [ ] **Kelpie discovery — from the existing reference implementation.** An EDAG project that already integrates Kelpie is checked out locally at `C:\Users\rp99480\dev\ai4tc_webapp` (outside this repo). Treat it as **read-only reference**: never modify it, never commit anything from it, never copy secrets/`.env` values. The agent must:
  1. Locate the Kelpie client code (search for `kelpie` case-insensitively in source, config, docs and env templates) and summarise in `docs/discovery.md`: file paths, how it is called (HTTP OpenAI-compatible, proprietary REST, or SDK), base URL and auth mechanism (names of env vars/config keys only, **no values**), how models are selected, request/response shape for text and for **image + text** inputs, whether and where **token usage** is returned, timeouts/retries/rate-limit handling, max image size.
  2. List the models the project uses or configures, and mark which are **vision-capable and locally hosted**.
  3. **Verify it works**: write a minimal standalone script (`scripts/kelpie_probe.py`, in this repo) that reproduces one text call and one image+text call using the same convention; run it; record request/response shape (redacted) and observed latency/token usage in `docs/kelpie-example.md`. If it fails, stop and ask the human.
  4. Recommend and record in `docs/decisions.md` how `KelpieVisionBackend` will reuse it: **reimplement a thin client following the same convention (default)**, import it, or copy a small part. Copying code requires the human's confirmation that internal reuse is allowed; the reference project's dependencies must not be pulled into this one without a license check.
  5. Note any quirks found (special headers, proxy settings, certificate handling, message format for images such as base64 data URLs).
- [ ] Pick the default vision model (and, if different, the judge model) from the local ones. Record context window, observed latency.
- [ ] **Current system as baseline:** the existing EDAG software **will be handed to Riccardo next week**; it is not available during Phases 0–6. Phase 0 only records this as pending. When it arrives: how to run it on a file (CLI, API, script), what it outputs, where its token usage can be read (ask Amro if unclear), then complete the `baseline_current` adapter (Phase 7). Until then the benchmark runs without `baseline_current`, using `full-vision` as the in-house baseline.
- [ ] Obtain the sample set from Oz/Hannes. Target ≥ 6 documents: digital text-heavy, table-heavy, figure-heavy, scanned, EN and DE, at least one with many images. Record page counts. Place under `samples/` (git-ignored).
- [ ] `pip-licenses` report saved to `docs/licenses.md`; confirm no forbidden licenses.
- [ ] Confirm tokenizer for *estimating* tokens when Kelpie does not report them (e.g. `tiktoken` if its encodings are available offline; else a chars/4 heuristic flagged as rough).
- [ ] Open decisions listed in section 10 that can now be closed.

Acceptance: `docs/discovery.md` complete; human replies "go".

### Phase 1 — Walking skeleton: text-only PDF → Markdown with page provenance
- `doc2md convert in.pdf -o out/` works end to end for a **digital text PDF**, using only pdfplumber.
- Produces `out/<stem>/<stem>.md`, `<stem>.json` (schema in ARCHITECTURE.md §5), `run.json`.
- Markdown contains `<!-- page: N -->` markers; JSON blocks have `page` and `block_id`.
- Python API `doc2md.convert()` returns `ConversionResult`.
- Repo bootstrap in this phase: `pyproject.toml`, folder skeleton limited to what the phase uses, `.gitignore` (incl. `samples/`, `out/`, `bench_runs/`, `.doc2md_cache/`, `.env`), `AGENTS.md` (3–10 lines pointing to this spec and ARCHITECTURE.md plus the rules in section 0), `docs/decisions.md`, ruff/mypy/pytest configured.
- Acceptance tests: synthetic 3-page PDF → expected paragraphs in order with the right page numbers; JSON validates against the Pydantic model; CLI exit code 0; re-run is deterministic (same output bytes).
- Demo: convert a synthetic PDF and open the `.md`.

### Phase 2 — Text normalisation and special characters
- Ligature mapping (U+FB00–FB06) → plain letters; soft hyphen removal; line-end hyphenation repair (`exam-\nple` → `example`, but keep real hyphens such as `state-of-the-art`); whitespace cleanup; German umlauts/ß preserved; `(cid:NN)` glyph artefacts detected and reported as `garbled`.
- Acceptance tests (table-driven): `"ﬂow"`→`"flow"`, `"ofﬁce"`→`"office"`, `"Straße"` unchanged, `"Über-\ngröße"` → `"Übergröße"`, `"(cid:12)(cid:45)"` flagged garbled. A fixture PDF with real fl/fi ligatures extracts correctly **without any special-casing outside `text_normalize.py`**.
- Demo: the reported "f followed by l" issue no longer occurs.

### Phase 3 — Page signals and routing (`inspect`)
- Compute FR1 signals; implement `router.classify()` with thresholds from config; add `doc2md inspect` printing a per-page table (page, chars, image-area %, tables, garbled %, class, reason).
- Fast path now only processes `TEXT` pages; pages classified `COMPLEX`/`SCANNED` get a placeholder block `<!-- page N: routed to hard path (not yet implemented) -->`.
- Acceptance: synthetic fixtures (text, table with merged cells, image-heavy page, scanned page made by rasterising a text page) classify as expected; thresholds overridable via config and CLI `--set router.min_chars=...`; classification is pure and unit-tested with signal dictionaries (no PDF needed for most tests).
- Demo: `doc2md inspect` on a mixed fixture shows 3 different classes.

### Phase 4 — Hard path with Docling
- `DoclingExtractor` converts **only the routed pages** (page range or sub-PDF; see ARCHITECTURE §6.3), CPU, OCR `en+de` when local OCR artifacts are provisioned, table structure on, Docling's own picture description **off** (we do images ourselves). Runtime model downloads are disabled by default; missing artifacts fail only the affected page with a clear provisioning message.
- Docling output mapped into the common `Block` model with `source="docling"` and correct page numbers (original page numbers, not sub-PDF numbers).
- Lazy import; single converter instance per run; page results cached.
- Acceptance: a synthetic scanned page yields its text; a table fixture yields a Markdown table with the right cell count; `import doc2md` + converting a text-only PDF does not import `docling` (test via `sys.modules`); page numbers in JSON equal original page numbers for non-contiguous routed pages (e.g. pages 2 and 5).
- Demo: mixed PDF converts fully; `run.json` shows which pages used which method.

### Phase 5 — Images and the Kelpie vision backend
- Implement `VisionBackend` protocol, `FakeVisionBackend` (tests) and `KelpieVisionBackend` (real, per Phase 0 discovery).
- Extract embedded images per page (pdfplumber / pypdfium2), filter (min size, aspect, duplicates), save to `images/`, describe via vision backend with a fixed, versioned prompt (`prompts/describe_image.v1.txt`), insert inline:

  ```markdown
  ![Figure p3-i01](images/p0003-i01.png)
  > **Image description (p3-i01):** …
  ```
- Token usage recorded per call. Retries with backoff on transient errors; timeout configurable; concurrency bounded.
- Acceptance (with `FakeVisionBackend`): logo-sized image skipped and listed in `run.json` as `skipped: too_small`; duplicate image described once; description appears inline after the right paragraph; Kelpie failure leaves a placeholder and a `failed` image record but the document completes. One **integration test** against real Kelpie, marked `@pytest.mark.kelpie`, skipped unless `KELPIE_*` env vars are set.
- Demo: image-heavy PDF → Markdown with inline descriptions and a token total.

### Phase 6 — Pipelines, cache and metrics
- Add `full-vision` and `docling-only` pipelines behind the same `convert()` (`pipeline=` argument / `--pipeline`).
- Finalise metrics (FR8) and disk cache (FR9) with `--no-cache` and cache-key tests.
- Acceptance: second run of same file+config makes 0 Kelpie calls and 0 Docling calls (verified through metrics); changing a config value that affects output invalidates the cache; token totals in `run.json` equal the sum of per-call usage; `estimated` flag set when Kelpie did not report usage.
- Demo: run all three pipelines on one PDF and compare `run.json`.

### Phase 7 — Benchmark harness
- `bench/suite.toml` lists documents (path, tags: `digital|scanned|tables|figures|en|de`) and pipelines to run. `baseline_current` is **optional** in the suite: the harness and report must work without it (savings vs `full-vision` only) and include it automatically once its adapter is configured (software available from next week). Implement the adapter against a fake in tests; wire the real one only when the software is delivered and its invocation is known.
- `doc2md bench run` executes each (doc, pipeline) pair, **cold cache**, several repetitions for time (default 3, report median), collecting into `bench_runs/<timestamp>/` the per-run outputs and a `results.csv` (schema in ARCHITECTURE §7).
- `doc2md bench report <run_dir>` writes `report.md`: per-pipeline and per-document tables for tokens, calls, time/page, % pages on hard path, plus savings vs `baseline_current` and vs `full-vision`.
- Acceptance: harness runs with `FakeVisionBackend` and a fake baseline adapter in tests; `results.csv` has the exact columns; report renders deterministically from a stored fixture CSV (golden file test).
- Demo: `bench run` on 2 synthetic docs, 2 pipelines.

### Phase 8 — Quality evaluation
- `doc2md bench review-sheet <run_dir>` selects a **stratified sample of pages** (default 30: 10 per class, fewer if not available, fixed random seed) and writes a CSV/Markdown review sheet showing for each page the rendered page image path and the output of each pipeline **blind-labelled** (A/B/C, shuffled with seed, mapping saved separately).
- Rubric (0–2 per criterion): text fidelity, special characters/umlauts, table fidelity, figure/image description usefulness, reading order. Defined in `bench/rubric.md`.
- `doc2md bench judge <run_dir>` runs an LLM-as-judge via Kelpie (judge model from Phase 0, text+page image if vision-capable) with the same rubric and a fixed prompt; outputs JSON scores per page/pipeline.
- `doc2md bench report` merges manual and judge scores; reports agreement between them on the overlapping sample (e.g. Spearman or simple % agreement) and **explicitly states the limits of the judge** (local model, possible bias towards its own style).
- Acceptance: review sheet generation is deterministic with a seed; unblinding map round-trips; judge parser handles malformed model output (returns `judge_error`, never crashes); merged report golden-file test.
- Demo: generate a review sheet from fixture run outputs.

### Phase 9 — Findings and packaging
- Run the benchmark on the complete local corpus: all permitted PDFs in `samples/`, all committed synthetic PDFs used by the test suite, and every PDF discovered under the read-only cloned reference repository `C:\Users\rp99480\dev\ai4tc_webapp` when present. The real EDAG OCR baseline is explicitly **out of scope** for this phase; compare `tiered` with `full-vision` and leave an integration seam for a parallel manual comparison with the existing OCR software.
- `docs/FINDINGS.md`: method, corpus manifest, results tables, charts (optional), **recommendation vs go/no-go criteria (section 8)** adapted to the available comparisons, explicit baseline exclusion, risks, and what to do next (e.g. add the EDAG adapter, docx/xlsx/eml converters, bounding boxes, image classifier).
- Packaging: `pyproject.toml` with extras `[hard]` (docling) and `[bench]`; `README.md` (install, usage, library API); `THIRD_PARTY_NOTICES.md`; version `0.1.0`.
- Acceptance: fresh virtualenv `pip install .[hard,bench]` works; README examples run; the corpus discovery command is deterministic and does not copy confidential PDFs; FINDINGS cites the exact run directory and versions used, or clearly records an environment block when Kelpie/Docling artifacts or external PDFs are unavailable.

## 8. Success criteria and go/no-go (proposed values only — to be reviewed by Riccardo, then confirmed with Amro and Oz before Phase 9)

Measured on the Oz/Hannes sample set, cold cache, same Kelpie vision model for all vision calls:

| Criterion | Proposed threshold for "go" |
|-----------|-----------------------------|
| Parsing tokens (Kelpie input+output) | `tiered` ≥ **50 % lower** than `baseline_current` and than `full-vision` on the whole set |
| Quality | Mean rubric score of `tiered` ≥ **95 %** of `baseline_current`; no single category (text, tables, figures, special chars) more than **10 %** worse |
| Time (CPU) | Total wall time per document no worse than **1.5×** `baseline_current` (Docling on CPU is slow; this checks it is not prohibitive) |
| Robustness | 0 crashes; failed pages < 2 % |
| Special characters | 0 occurrences of fl/fi ligature artefacts in `tiered` output of the sample set |

Report time per page for easy vs hard pages separately: the hypothesis is that speed gains come from easy pages.

If thresholds are missed, `FINDINGS.md` must say which component is the cause (routing misclassification, Docling cost, vision cost) and what tuning is proposed, instead of only "no-go".

## 9. Deliverables

1. Python package `doc2md` (library + CLI) in a git repo, tests green.
2. `bench/` harness and rubric.
3. `docs/discovery.md`, `docs/decisions.md`, `docs/licenses.md`, `docs/FINDINGS.md`.
4. `README.md`, `THIRD_PARTY_NOTICES.md`.
5. A short demo (Phase 9) for Amro/Oz: command-line run on one image-heavy document plus the comparison table.

Timeline expectation from the call: Riccardo estimated **about one week** for a first experiment with results. Phases 0–6 are the minimum for a first look; 7–9 complete the evaluation.

## 10. Assumptions and open items (to close in Phase 0 / with stakeholders)

| ID | Item | Default assumption until closed | Closed by |
|----|------|---------------------------------|-----------|
| A1 | Kelpie interface (HTTP/OpenAI-compatible/SDK), auth, models, usage reporting | Read from the reference implementation in `C:\Users\rp99480\dev\ai4tc_webapp` and verified with `scripts/kelpie_probe.py`; adapter isolated behind `VisionBackend` | Phase 0 |
| A2 | How to run the current EDAG system as black box and read its token usage | Software delivered to Riccardo **next week**; baseline adapter finished then | Delivery + Phase 7 |
| A3 | Sample documents (count, kinds, languages) | ≥ 6 docs from Oz/Hannes | Phase 0 |
| A4 | Python version and OS on the EDAG PC | ≥ 3.11, Windows or Linux | Phase 0 |
| A5 | Token estimation method when Kelpie reports no usage | `tiktoken` if offline-capable, else chars/4 flagged `estimated` | Phase 0 |
| A6 | Go/no-go thresholds (section 8) | Proposed values only; Riccardo reviews them (then Amro/Oz) before Phase 9. The agent must not treat them as final | Riccardo, then Amro/Oz |
| A7 | Project/package name | **Closed: `doc2md`** (project folder `doc2md`) | — |
| A8 | Whether the vision model and judge model are the same | Same unless Phase 0 shows a better local option | Phase 0 |
| A9 | Whether benchmark excerpts may be shared outside the team | No: metrics and anonymised excerpts only | Oz/Hannes |
| A10 | Whether Docling model artifacts may be downloaded at runtime | No: provision local artifacts; remote download is development/provisioning-only | Phase 0/4 |

## 11. Glossary

- **Page class:** `TEXT`, `COMPLEX`, `SCANNED` (FR2).
- **Fast path:** pdfplumber extraction. **Hard path:** Docling (layout/OCR/tables).
- **Vision backend:** component that sends an image + prompt to a vision LLM through Kelpie.
- **Kelpie:** EDAG's internal LLM-call service, with some locally hosted models.
- **Provenance:** page + block id (and optional bbox) attached to every piece of extracted content.
- **Baseline current:** the existing EDAG screenshot-to-text engine. **Full-vision:** our re-implementation of the same idea for controlled comparison.
