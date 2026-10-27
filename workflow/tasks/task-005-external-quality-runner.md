# task-005 - Add a Path-Driven Quality Run

## What to build
Add a local-only quality runner that accepts an arbitrary PDF path and an
optional reference Markdown path, runs the public doc2md conversion, reads the
generated Markdown and JSON, and reports structural quality metrics and
failures. It must never embed a sample path, copy a confidential PDF, or
compare bytes literally when page markers and renderer conventions differ.
The runner should be usable in CI with synthetic fixtures and manually with
the supplied external PDF/reference pair.

## Why
The current tests are green but do not exercise the supplied document's
combination of repeated margins, merged tables, inline bullets, and a
decorative logo. A repeatable command is needed to verify the Markdown after
each targeted fix.

## Relevant files

Read before starting:
- `src/doc2md/api.py` - public conversion contract.
- `src/doc2md/models.py` - sidecar validation and provenance.
- `tests/conftest.py` - synthetic fixture conventions.
- `README.md` - documented developer commands.

Create:
- `scripts/check_quality.py` - path-driven local quality report.
- `tests/test_quality_runner.py` - offline synthetic tests for the report and exit behavior.

Modify:
- `README.md` - document the generic command without confidential paths.

## Steps
1. Define a small report schema for page failures, heading/list/table counts, repeated-margin residue, and source-text coverage.
2. Add synthetic tests for a passing report and a failing report.
3. Implement CLI arguments for source, output directory, optional reference Markdown, and optional JSON report path.
4. Use the reference only as an external quality oracle; compare normalized content/structure rather than exact bytes.
5. Run it against the supplied files from outside the repository and keep all generated artifacts outside Git.
6. Add the command to the developer runbook.

## Acceptance criteria
- [ ] The runner exits non-zero for failed pages or missing required extracted content.
- [ ] The runner validates the sidecar schema and page provenance.
- [ ] Synthetic tests are offline and contain no confidential text or PDF.
- [ ] The supplied PDF can be checked by passing its path at runtime, with no source-specific code.
- [ ] The report makes clear whether the Kelpie-backed hard path and real Kelpie service are available.

## Edge cases to handle
- When no reference is supplied: report intrinsic conversion checks only.
- When the reference has different page-marker conventions: do not report false failures from formatting alone.
- When a hard page is intentionally failed due missing artifacts: report it explicitly and distinguish it from a crash.

## Do not touch
- Confidential output folders or repository fixtures.
- Production extraction logic except for the public API calls needed by the runner.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests scripts` passes.
- [ ] `mypy src` completes without errors.
- [ ] README contains a reproducible generic invocation.

## Status
dev-complete

### Dev notes
Files created:
- `scripts/check_quality.py` - path-driven structural and reference-coverage report.
- `tests/test_quality_runner.py` - offline passing, missing-content, and hard-page failure tests.

Files modified:
- `README.md` - documented generic quality-runner commands.
- `docs/decisions.md` - recorded ADR-036.

Deviations from spec (if any):
- The runner defaults to `FakeVisionBackend` for offline safety; `--vision-backend kelpie` is explicit.

Suggestions for follow-up (do not act on these):
- Add a benchmark-level quality report aggregation once the external corpus is approved for Phase 9 evaluation.
