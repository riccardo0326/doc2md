# task-004 - Filter Decorative Images Before Vision

## What to build
Extend the image filter with a configurable page-relative size signal so
small decorative images can be skipped before a vision call, and make the
skip decision observable in `ImageRecord` and `run.json`. Keep the existing
width, height, area, aspect-ratio, and duplicate rules. A vision backend
failure for an image must remain an image-level warning/placeholder and must
not turn unrelated page extraction into a failure.

## Why
The sample PDF contains one small logo. It currently passes the absolute
64x64/10000-pixel thresholds, is sent to the unconfigured Kelpie backend, and
adds a `description failed` placeholder instead of being skipped.

## Relevant files

Read before starting:
- `src/doc2md/converters/pdf/images.py` - filtering and image records.
- `src/doc2md/config.py` - image thresholds.
- `src/doc2md/api.py` - image-stage activation and metrics.
- `tests/test_images.py` - fake vision and image assertions.

Modify:
- `src/doc2md/config.py` - add the generic relative-area threshold if approved.
- `src/doc2md/converters/pdf/images.py` - apply the page-relative filter.
- `tests/test_images.py` - cover decorative skip, kept figure, and backend failure.
- `docs/decisions.md` - record the threshold and its rationale.

## Steps
1. Add a failing synthetic fixture with a small page-relative image and a larger figure.
2. Add a configurable relative-area signal without recognizing logos by name or location on a specific page.
3. Record decorative images as `skipped` with an existing or explicitly approved skip reason.
4. Assert that skipped images make zero vision calls and are absent from Markdown.
5. Assert that a kept image still produces the existing path, description, provenance, and usage.
6. Run the full quality checks.

## Acceptance criteria
- [ ] A decorative image below the configured relative threshold is skipped before vision.
- [ ] A larger image is still described by `FakeVisionBackend`.
- [ ] A Kelpie/backend failure does not fail the page or the document.
- [ ] The default remains configurable and is not tied to the sample PDF.

## Edge cases to handle
- When the page has zero or invalid dimensions: fall back to absolute thresholds.
- When duplicate images occur: deduplication remains deterministic after filtering.
- When `--no-images` is set: no image extraction or vision initialization occurs.

## Do not touch
- Kelpie request/response contracts.
- Image bytes, confidential samples, or model responses in tests.

## Definition of done
- [ ] `pytest -q` passes.
- [ ] `ruff check src tests` passes.
- [ ] `mypy src` completes without errors.

## Status
dev-complete

### Dev notes
Files created:
- None.

Files modified:
- `src/doc2md/config.py` - added configurable `min_page_area_ratio=0.02`.
- `src/doc2md/converters/pdf/images.py` - applies the relative PDF-bounding-box filter with absolute fallback.
- `tests/test_images.py` - added a relative-filter test that verifies zero extra vision calls for the decorative fixture image.
- `docs/decisions.md` - recorded ADR-035.

Deviations from spec (if any):
- None.

Suggestions for follow-up (do not act on these):
- Tune the default ratio against additional figure-heavy documents before final benchmark claims.
