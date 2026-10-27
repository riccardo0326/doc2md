# task-012 - Kelpie Hard Path

## What to build
Implement the enterprise hard path for `COMPLEX` and `SCANNED` PDF pages by
rendering only the selected page with pypdfium2 and calling Kelpie through the
already discovered `VisionBackend.transcribe_page()` contract. Use the
EDAG-hosted `DARE-NoCloud-Helios` deployment by default, parse the returned
Markdown into the common `Block` model, preserve original page provenance, and
record Kelpie usage, latency, cache state, and isolated failures. The local
Docling adapter remains disposable development diagnostics and must not be
selected by the enterprise default.

## Why

The current tiered pipeline sends hard pages to `DoclingExtractor`, which cannot
run on the enterprise PC because local model artifacts are out of scope. Kelpie
already provides the approved remote gateway to models hosted on EDAG servers.

## Relevant files

Read before starting:
- `src/doc2md/api.py` - routing, page rendering, cache, and metrics loop.
- `src/doc2md/converters/pdf/hard.py` - existing hard extractor seam and Docling diagnostic adapter.
- `src/doc2md/config.py` - hard/vision configuration and model defaults.
- `src/doc2md/cache.py` - JSON cache key contracts.
- `src/doc2md/models.py` - common `Block`, provenance, and usage models.
- `src/doc2md/vision/base.py` - discovered `VisionBackend` and `VisionResult` contract.
- `src/doc2md/vision/fake.py` - deterministic fake backend seam.
- `src/doc2md/vision/kelpie.py` - verified Responses API/Kelpie transport.
- `docs/discovery.md` and `docs/kelpie-example.md` - redacted Kelpie request/model evidence.
- `tests/test_hard.py`, `tests/test_phase6.py`, `tests/test_kelpie_integration.py` - existing hard/pipeline/Kelpie tests.

Create:
- `prompts/transcribe_page.v1.txt` - versioned page transcription prompt; request Markdown headings, paragraphs, lists, and GFM tables only.
- `tests/test_kelpie_hard.py` - offline fake-backend hard-path tests.

Modify:
- `src/doc2md/converters/pdf/hard.py` - add `KelpieHardExtractor` and Markdown-to-Block mapping; keep `DoclingExtractor` diagnostic-only.
- `src/doc2md/api.py` - select Kelpie hard path for enterprise `tiered` hard pages, render only routed pages, cache page results, and record calls.
- `src/doc2md/config.py` - make `hard.engine="kelpie"` and `DARE-NoCloud-Helios` the enterprise defaults; keep development Docling selection explicit.
- `src/doc2md/models.py` only if the existing common block contract cannot represent the parsed Markdown without widening it.
- `tests/test_hard.py` and `tests/test_phase6.py` - update expectations and cache/metrics coverage.
- `tests/test_kelpie_integration.py` - add one real Kelpie hard-page test marked `@pytest.mark.kelpie`, skipped without the discovered environment configuration.
- `README.md`, `PROJECT-SPEC.md`, `ARCHITECTURE.md`, `docs/decisions.md` - document the implemented Kelpie hard path and remove stale Docling-enterprise wording.

## Steps
1. Add a failing fake-backend test that routes a synthetic scanned page to Kelpie and returns a paragraph block with `source="vision"`.
2. Add a failing parser test for a Kelpie Markdown response containing a heading, paragraph, list, and GFM table.
3. Add the versioned transcription prompt without inventing HTTP or response fields beyond the existing `VisionBackend` contract.
4. Implement page rendering and `KelpieHardExtractor.extract()` using the injected vision backend and original page numbers.
5. Map Markdown blocks deterministically into the common block model and preserve table/list content.
6. Select the Kelpie hard extractor for enterprise `tiered` hard pages while retaining explicit `docling-dev-only` diagnostics.
7. Add hard-page cache keys containing source identity, page, prompt, model, DPI, and output-affecting vision configuration.
8. Record `transcribe_page` calls and usage in `run.json`; do not count cache hits as calls.
9. Ensure Kelpie failures produce isolated page placeholders and `--strict` remains non-zero.
10. Add the real Kelpie integration test using `DARE-NoCloud-Helios` and the environment names already documented in discovery.
11. Update the source-of-truth docs and remove statements that local Docling artifacts are an enterprise prerequisite.

## Acceptance criteria
- [ ] Enterprise `tiered` routes `COMPLEX` and `SCANNED` pages through Kelpie/Helios, not local Docling.
- [ ] `TEXT` pages do not make Kelpie hard-page calls.
- [ ] A Kelpie Markdown response becomes ordered heading, paragraph, list, and table blocks with original page provenance.
- [ ] Hard-page calls are cached and cache hits contribute no new call or token usage.
- [ ] `run.json` records hard-page calls, model, latency, and reported/estimated usage.
- [ ] Kelpie failure leaves an isolated failed page and does not abort other pages.
- [ ] The image description path continues to use the same Kelpie backend without contract changes.
- [ ] Local Docling/OCR model installation or runtime download is not required by any default command.

## Edge cases to handle
- When Kelpie returns empty or malformed Markdown: mark the page failed with a clear error.
- When a page is blank: the empty-page router completes it without Kelpie.
- When Markdown contains a merged or malformed table: preserve text and emit a simplified table/block warning rather than dropping content.
- When Kelpie is not configured: only hard pages fail; ordinary text conversion still completes.
- When the real integration environment is absent: the `@pytest.mark.kelpie` test skips without secrets or model responses in Git.

## Do not touch
- Kelpie request/response conventions discovered in the reference project.
- Local model installation, artifact downloads, TLS verification, or sample-specific branches.
- The baseline EDAG adapter.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests scripts` passes.
- [ ] `mypy src` passes.
- [ ] `python -m build` passes.
- [ ] A fake end-to-end conversion proves hard-page routing, blocks, cache, metrics, and failure isolation.
- [ ] README and source-of-truth docs describe Kelpie/Helios as the enterprise hard path.

## Status
dev-complete

### Dev notes
Files created:
- `prompts/transcribe_page.v1.txt` - versioned Kelpie page transcription prompt.
- `tests/test_kelpie_hard.py` - fake hard-path, cache, parser, and failure-isolation tests.

Files modified:
- `src/doc2md/converters/pdf/hard.py` - added `KelpieHardExtractor` and Markdown-to-Block parsing.
- `src/doc2md/api.py` - routes enterprise hard pages through Kelpie, caches results, and records hard calls.
- `src/doc2md/config.py` - defaults hard engine to Kelpie and model to `DARE-NoCloud-Helios`.
- `tests/test_hard.py`, `tests/test_quality_runner.py`, `tests/test_kelpie_integration.py` - updated enterprise hard-path expectations and integration seam.
- `README.md`, `docs/decisions.md` - documented Kelpie hard-path behavior.

Deviations from spec (if any):
- The Kelpie response is expected to contain Markdown, which is parsed into common blocks. No undocumented transport or response fields were added.

Suggestions for follow-up (do not act on these):
- Run the `@pytest.mark.kelpie` hard-page test on the corporate proxy with Helios.
