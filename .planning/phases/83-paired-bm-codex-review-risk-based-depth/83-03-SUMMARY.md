---
phase: 83-paired-bm-codex-review-risk-based-depth
plan: "03"
subsystem: review-workflow
tags: [codex, json-schema, audit-tooling, tdd, stdlib-only]

# Dependency graph
requires:
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 02)
    provides: ".claude/schemas/codex-review-findings.schema.json (the field/enum source this checker loads at runtime)"
provides:
  - "tests/codex_report_status.py: assess_report()/Assessment/main() -- the stdlib-only checker that decides whether a Codex report counts as a complete, current review of a specific head"
  - "tests/test_codex_report_status.py: 30 behavior tests covering every complete/incomplete case"
affects: [83-05 (invocation procedure that calls this checker), 83-06 (CLAUDE.md review-pairing instruction), 83-REVIEW-EVIDENCE.md, 83-DEMONSTRATIONS.md (negative-case recipes, D-17)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Audit tooling in tests/: a plain module + pytest wrapper + CLI, stdlib only, plain print() exempted from the loguru-only convention (same shape as tests/audit_lock_coverage.py)"
    - "Schema-driven validation: required/enum/nested-object checks are read from the JSON Schema file at call time, never duplicated as a second hardcoded field list"

key-files:
  created:
    - tests/codex_report_status.py
    - tests/test_codex_report_status.py
  modified: []

key-decisions:
  - "Severity/verdict enums and every required-field list are read from .claude/schemas/codex-review-findings.schema.json at runtime (via _check_schema) rather than hardcoded a second time, per the plan's interfaces block and REVIEW-04's single-source-of-truth intent"
  - "argparse's built-in ArgumentTypeError/parser.error() path is used for the --expected-head/--expected-base/--current-head SHA-format validation, which naturally produces exit code 2 for usage errors without custom exit-code plumbing"
  - "Reason strings never contain the word \"clean\" anywhere in the module (grep-verified); the only two status values are \"complete\" and \"incomplete\" (D-09)"

patterns-established:
  - "Pattern: any future report-shape checker in this repo should likewise derive its required/enum checks from the schema file at runtime, not maintain a parallel hardcoded list"

requirements-completed: [REVIEW-03, REVIEW-04, REVIEW-06]

# Metrics
duration: ~10min
completed: 2026-10-22
---

# Phase 83 Plan 03: Codex Report Completeness and SHA-Binding Checker Summary

**Stdlib-only `assess_report()`/`main()` in `tests/codex_report_status.py` that returns "complete" only for a schema-valid Codex report on the expected and current head, and "incomplete" with specific, stacked reasons for every missing/failed/stale/wrong-commit/malformed case -- 30 tests, TDD RED then GREEN.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-10-22 (session start)
- **Completed:** 2026-10-22T14:49:14-04:00 (GREEN commit)
- **Tasks:** 1 (TDD: RED then GREEN)
- **Files modified:** 2 (both new)

## Accomplishments

- Wrote `tests/test_codex_report_status.py` first (RED): 30 tests covering the valid-report complete case, the empty-findings "no-findings" complete case, missing/empty/whitespace report text, exit codes 124/1/None, truncated JSON, every schema violation (missing field, unexpected field, missing finding field, invalid severity enum), wrong head, invalid head SHA format, wrong base, staleness, reproduced-without-command, unreproduced-without-hypothesis, empty coverage, duplicate finding ids, a combined multiple-failure case asserting stable reason order, a "never contains 'clean'" sweep across six scenarios, and three CLI cases (exit 0/1/2). Confirmed RED with `ModuleNotFoundError` (module did not exist yet).
- Implemented `tests/codex_report_status.py` (GREEN): `Assessment` dataclass, `assess_report()` which collects every applicable reason rather than stopping at the first, `_check_schema()` which derives required fields, enums (`verdict`, `severity`), and nested `findings`/`commands_run` object shapes directly from the loaded schema JSON, `_finding_consistency_and_ids()` which produces `codex:<head12>:a<attempt>:<id>` qualified ids and flags duplicate ids plus reproduced/hypothesis inconsistencies, and a `main()` CLI using argparse's built-in usage-error path (exit 2) for malformed SHA arguments.
- All 30 new tests pass; the full suite (2201 tests) and `ruff check triggarr/ tests/` both pass with no changes needed to either file after the first GREEN pass -- no REFACTOR commit was necessary.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing tests for the Codex report checker** - `9caed38` (test)
2. **Task 1 GREEN: Codex report checker implementation** - `d214d3a` (feat)

**Plan metadata:** (this commit, docs: complete plan)

_Note: No REFACTOR commit was needed -- `uv run ruff check tests/` passed clean on the first GREEN implementation, and no duplication or clarity issue emerged on review._

## Files Created/Modified

- `tests/codex_report_status.py` - `Assessment` dataclass, `assess_report()`, schema-driven validation helpers, and a `main()` CLI (exit 0 complete / 1 incomplete / 2 usage error)
- `tests/test_codex_report_status.py` - 30 behavior tests for every complete/incomplete case and the CLI

## Decisions Made

- None beyond what the plan specified. One implementation choice made within the plan's stated discretion: enums (`severity`, `verdict`) are read from the schema's `enum` arrays at runtime inside `_check_schema`, extending the plan's "load required field names from the schema" instruction to cover enum values too, so there is exactly one place in the repository that defines valid severities/verdicts.

## Deviations from Plan

None - plan executed exactly as written. The `<behavior>` block's every listed case has a corresponding test, and the `<implementation>` block's RED/GREEN/REFACTOR sequence, commit messages, and verification commands were followed exactly. REFACTOR was evaluated and found unnecessary (tests green, ruff clean).

## Issues Encountered

None. The RED phase failed for the expected reason (`ModuleNotFoundError: No module named 'tests.codex_report_status'`), confirming the tests exercised real behavior rather than passing vacuously.

## User Setup Required

None - no external service configuration required. This plan creates two test-tree files only; no `.planning/config.json` key, BM setting, or application code (`triggarr/`) was touched.

## Next Phase Readiness

- `tests/codex_report_status.py` is ready to be invoked by the real Codex invocation procedure (`docs/codex-adversarial-review-contract.md`, Invocation step 6) once a live `codex exec` run exists.
- Plans 05/06 (invocation wiring and the `CLAUDE.md` review-pairing instruction) and the `83-REVIEW-EVIDENCE.md`/`83-DEMONSTRATIONS.md` plans can call this checker's CLI directly; its JSON output shape (`status`, `reasons`, `qualified_ids`, `finding_count`, `inspected_head`, `inspected_base`) is stable.
- D-17's negative-case demonstration (missing/stale/wrong-commit report shown as incomplete, local only) can be built directly from this plan's test fixtures (`WRONG_HEAD`, `STALE_CURRENT`, missing-report cases) without writing new scenarios from scratch.
- No blockers. No package was installed (stdlib only, confirmed via `grep -c "^import jsonschema\|^from jsonschema" tests/codex_report_status.py` printing 0).

## Self-Check: PASSED

Both created files confirmed present on disk (`tests/codex_report_status.py`, `tests/test_codex_report_status.py`); both task commit hashes (`9caed38`, `d214d3a`) confirmed present in `git log --oneline --all`.

---
*Phase: 83-paired-bm-codex-review-risk-based-depth*
*Completed: 2026-10-22*
