# Phase Status

| Phase | Status | Evidence | Branch |
|---|---|---|---|
| 0 | Complete with documented exceptions | `docs/discovery.md`, `docs/kelpie-example.md`, `docs/licenses.md` | `phase-0` |
| 1 | Complete | 4 tests, CLI/API, provenance sidecar, deterministic outputs | `phase-1` |
| 2 | Complete | 21 tests, normalization and real ligature fixture | `phase-2` |
| 3 | Complete | 34 default tests, `inspect`, signals and routing | `phase-3` |
| 4 | Complete within enterprise perimeter | Docling table/page-range tests; local artifacts required; OCR download skipped by TLS boundary | `phase-4` |
| 5 | Complete | 40 default tests, FakeVisionBackend, image filtering/dedupe, real Kelpie probe | `phase-5` |
| 6 | Complete with local-environment exception | FR3 enrichment, three pipelines, JSON cache, no-cache, derived call/token metrics; 46 default tests | `phase-6` |

## Accepted Constraints

- Four additional real documents are still needed before benchmark work.
- Docling/OCR artifacts must be provisioned locally; runtime downloads are outside the product perimeter.
- Scanned OCR is unavailable until those local artifacts are provisioned.

## Remaining Product Work

- Phase 7: benchmark harness and comparison reports.

## Phase 6 Notes

- The default test suite is green: 46 passed, 1 skipped, 4 deselected.
- Ruff and strict mypy are green.
- The targeted slow Docling tests remain blocked on this workstation because the
  Docling package/artifacts are not available. This preserves the enterprise
  rule: conversion never downloads Docling/OCR artifacts at runtime.
