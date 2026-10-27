# task-007 - Provision and Verify Hard-Path OCR

## What to build
Record and verify the enterprise hard-processing boundary for image-only table
pages. Local OCR/layout/model installation and model downloads are out of scope
on enterprise PCs. Add an explicit slow integration seam for the approved remote
hard adapter when its contract is available; until then, verify the isolated
failure behavior and record the environment state.

## Why
The image-only table sample and two scanned pages cannot be judged by the fast
path. The current workstation has no approved remote hard adapter, and local
model provisioning is prohibited by the enterprise boundary.

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
- [ ] An approved remote hard-adapter run extracts the image-only table without a failed-page placeholder.
- [ ] Original page numbers and sidecar provenance are correct.
- [ ] Missing artifacts still produce a clear isolated failure in the default path.
- [ ] No TLS bypass or implicit runtime model download is introduced.

## Definition of done
- [ ] Offline/default `pytest -q` remains green.
- [ ] Explicit remote hard-adapter test passes when that adapter is available or reports the environment boundary with evidence.
- [ ] Ruff and mypy pass.

## Status
blocked

### Blocker
The current workstation has no approved remote hard adapter. A disposable
development artifact download was attempted only to document the boundary and
failed on the corporate self-signed TLS certificate. TLS verification was not
bypassed, and no model artifacts were copied into the repository.

### Already verified
- The existing slow Docling table/OCR tests remain available as disposable
  development diagnostics only.
- Default runtime behavior still rejects missing artifacts with a clear
  `HardExtractionError`.
