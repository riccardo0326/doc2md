# task-007 - Legacy Local-Model OCR Task

## Superseded

This task is superseded by `workflow/tasks/task-012-kelpie-hard-path.md`.
Enterprise OCR/layout inference must use Kelpie with models hosted locally on
EDAG servers. No local model provisioning task remains in this repository.

## Why
The image-only table sample and two scanned pages cannot be judged by the fast
path. The current workstation has no implemented Kelpie hard path, and local
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
cancelled

### Replacement
- `task-012-kelpie-hard-path`
