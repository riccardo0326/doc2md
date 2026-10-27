# task-007 - Provision and Verify Hard-Path OCR

## What to build
Provision the locally allowed Docling/OCR artifacts and add an explicit slow
integration verification for image-only table pages. The default runtime must
continue to reject unavailable artifacts without downloading silently. The
verification must record original page numbers, extracted text, table row and
column metadata, and the artifact/configuration state.

## Why
The image-only table sample and two scanned pages cannot be judged by the fast
path. Their current failures are caused by missing artifacts, not by a safe
fallback decision.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/hard.py` - Docling and OCR configuration.
- `src/doc2md/config.py` - artifact and remote-download settings.
- `tests/test_hard.py` - slow Docling/OCR test conventions.
- `docs/discovery.md` - installed API and enterprise artifact constraints.

Modify:
- `tests/test_hard.py` - add/extend slow scanned-table verification.
- `docs/discovery.md` or a run report - record artifact state and timings without confidential content.

## Acceptance criteria
- [ ] A provisioned OCR run extracts the image-only table without a failed-page placeholder.
- [ ] Original page numbers and sidecar provenance are correct.
- [ ] Missing artifacts still produce a clear isolated failure in the default path.
- [ ] No TLS bypass or implicit runtime model download is introduced.

## Definition of done
- [ ] Offline/default `pytest -q` remains green.
- [ ] Explicit slow Docling/OCR test passes when artifacts are provisioned or reports an environment skip with evidence.
- [ ] Ruff and mypy pass.

## Status
ready
