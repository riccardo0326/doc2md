# QA report - targeted PDF quality improvements

## STATUS: PASS
Reviewed: 2026-10-27

## Task criteria
| Criterion | Result | Notes |
|---|---|---|
| Fast-path semantic blocks | PASS | Heading, paragraph, and inline-list regressions pass. |
| Text-backed hard-path fallback | PASS | Digital complex pages fall back transparently; scanned pages remain isolated failures. |
| Repeated margin filtering | PASS | Synthetic repeated headers and numeric footers are covered and configurable. |
| Decorative image filtering | PASS | Relative page-area filtering skips small decorative assets before vision. |
| Path-driven quality runner | PASS | Synthetic pass/fail cases and external-path invocation are verified. |

## Technical quality
| Check | Result |
|---|---|
| Tests | PASS: 68 passed, 1 skipped, 4 deselected |
| Type check | PASS: mypy reports no issues in 35 source files |
| Lint | PASS: Ruff checks `src`, `tests`, and `scripts` |
| Build | PASS: sdist and wheel built successfully |
| No debug statements | PASS |
| Edge cases handled | PASS: scanned failures, merged tables, one-row tables, invalid page dimensions, and fake vision failures covered |

## Strategy alignment
Pure extraction decisions remain separate from Docling and vision adapters, and
the quality runner keeps confidential PDFs and reference outputs outside Git.
User goal served: yes. The changes improve the first demo without adding
sample-specific branches or replacing the tiered architecture.

## Blockers
- None for the implemented changes.

## Suggestions (non-blocking)
- The unstructured-demo corpus still needs a follow-up quality pass for complex
  multi-column reading order, list-shaped tables, and OCR provisioning.

## Approved for git
[x] Human approved commit and push.
