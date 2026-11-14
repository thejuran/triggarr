# Vibe-check deep review (routine): card-template PR, H1

This is the rendered report as shown in the session. Raw agent outputs and the scorer result are in the `.json` file next to this one.

- **Tool:** vibe-check deep-review 2.12.0, stock invocation, range mode `d5a4467..46c3919`, pass 1 (no earlier state on this branch).
- **Coverage evidence:** exact-head local coverage for H1 (3271 passed, 1 skipped); the provenance `check` passed. `cycle_grade.html` is not measured by coverage.py.
- **Agents:** bugs (opus), security, architecture (opus), impact, test-sufficiency, compliance, language-python. framework-fastapi did not run because triage found no FastAPI code. Vibe-check's own Codex pass joined (approve, 0 findings).
- **Git-safety gate:** rc 0. The guard refused three compliance commands (a file redirect and two awk calls); the repo was untouched.

| Found | Reported | Filtered |
|---|---|---|
| 4 | 1 | 3 sub-threshold |

## Medium

| # | File | Score | Agent | Finding |
|---|---|---|---|---|
| 1 | `triggarr/templates/partials/cycle_grade.html:24` | 74 | test-sufficiency | The card template now groups rows by the structured `kind` field, but no test renders the card to check it, and coverage can't measure the template |

## Filtered (sub-threshold)

- architecture arch-001: the reason-kind names are plain string literals rather than module constants.
- test-sufficiency cov-002: the paths in `cycle_view` that skip bad saved entries (L274/277/290/293) never run in tests. These paths predate this change.
- test-sufficiency cov-003: the all-kinds test adds "malformed" by hand instead of reading it from the result.

## Bottom line

No product defect. Bugs, impact and Codex each confirm that the card groups rows the same way as before for every well-formed record. The one reported item is a test gap: no test renders the card to show it uses `kind`.
