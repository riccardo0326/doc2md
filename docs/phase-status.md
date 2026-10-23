# Phase Status

| Phase | Status | Evidence | Branch |
|---|---|---|---|
| 0 | Complete with documented exceptions | `docs/discovery.md`, `docs/kelpie-example.md`, `docs/licenses.md` | `phase-0` |
| 1 | Complete | 4 tests, CLI/API, provenance sidecar, deterministic outputs | `phase-1` |
| 2 | Complete | 21 tests, normalization and real ligature fixture | `phase-2` |
| 3 | Complete | 34 default tests, `inspect`, signals and routing | `phase-3` |
| 4 | Complete within enterprise perimeter | Docling table/page-range tests; local artifacts required; OCR download skipped by TLS boundary | `phase-4` |
| 5 | Complete | 40 default tests, FakeVisionBackend, image filtering/dedupe, real Kelpie probe | `phase-5` |

## Accepted Constraints

- Four additional real documents are still needed before benchmark work.
- Docling/OCR artifacts must be provisioned locally; runtime downloads are outside the product perimeter.
- Scanned OCR is unavailable until those local artifacts are provisioned.

## Remaining Product Work

- Enrich the pdfplumber fast path with semantic headings, paragraph grouping, lists, and simple GFM tables before benchmark/demo claims.
- Phase 6: cache, full-vision/docling-only pipelines, and complete metrics.
