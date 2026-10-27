# QA report - task-012 - Kelpie hard path

## STATUS: PASS
Reviewed: 2026-10-27

## Task criteria
| Criterion | Result | Notes |
|---|---|---|
| Kelpie hard routing | PASS | Fake end-to-end tests route `COMPLEX` and `SCANNED` pages through `method="vision"`. |
| Markdown block mapping | PASS | Heading, paragraph, list, and GFM table responses map to common blocks with page provenance. |
| Cache and metrics | PASS | Second run makes no hard vision call and excludes cached usage from current totals. |
| Failure isolation | PASS | Kelpie hard errors produce isolated failed pages. |
| Real Kelpie integration | PASS WITH NOTE | `@pytest.mark.kelpie` test is present and skips without corporate proxy configuration. |
| Local model boundary | PASS | No model artifact or runtime download is required by the default path. |

## Technical quality
| Check | Result |
|---|---|
| Tests | PASS: 78 passed, 2 skipped, 4 deselected |
| Type check | PASS: mypy reports no issues in 35 source files |
| Lint | PASS: Ruff checks `src`, `tests`, and `scripts` |
| Build | PASS: sdist and wheel built successfully |
| No debug statements | PASS |

## Blockers
- Real Kelpie verification requires the corporate proxy and credentials already documented in Phase 0.

## Suggestions (non-blocking)
- Run the marked integration test on the target corporate environment with `DARE-NoCloud-Helios`.

## Approved for git
[x] Human requested implementation, commit, push, and merge-ready branch.
