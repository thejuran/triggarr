---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "04"
subsystem: testing
tags: [codex, review-machinery, hollow-report-guard, shlex]

# Dependency graph
requires:
  - phase: 83-paired-bm-codex-review-risk-based-depth
    provides: tests/codex_report_status.py (assess_report completeness checker), the schema, and the recorded Phase 83 .last.json evidence this plan re-assesses
provides:
  - "D-18 hollow-report guard: a commands_run entry with a null exit_code, or a report whose only commands are trivially uninformative (echo/printf/true/:/pwd/whoami/date/sleep/exit), no longer counts as evidence the diff was inspected"
  - "Re-assessment of all 13 recorded Phase 83 .last.json reports under the updated checker, with a reconciliation table against their recorded .status.json verdicts"
affects: [85-05, 85-06, "any future D-18 review-machinery hardening plan"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "shlex.split(posix=True) with a plain str.split() fallback to classify the first program in a shell command, skipping leading NAME=value env assignments"
    - "TRIVIAL_COMMANDS as a deliberately short, explicitly named frozenset -- extending it is flagged as a sensitive review-machinery change in its own comment"

key-files:
  created: []
  modified:
    - tests/codex_report_status.py
    - tests/test_codex_report_status.py

key-decisions:
  - "TRIVIAL_COMMANDS is exactly the plan's nine names (echo, printf, true, :, pwd, whoami, date, sleep, exit); the module comment explicitly calls extending it a sensitive change needing its own review."
  - "The hollow guard keeps the pre-existing 'no commands run' reason for a commands_run list with no non-blank command at all, and only applies the new null-exit-code / trivial-only checks once that first guard passes -- so a fully empty list still gets its original, unchanged reason text."
  - "Re-assessment used the report's own inspected_head_sha/inspected_base_sha as expected-head/base for the 5 recorded files with no companion .meta.json, matching the existing test file's _assess_recorded() pattern."

requirements-completed: [ACCEPT-01]

# Metrics
duration: ~15min
completed: 2026-10-27
---

# Phase 85 Plan 04: D-18 Hollow-Report Guard Summary

**Codex report checker now rejects a commands_run entry with a null exit code and a report whose only commands are trivially uninformative (echo/pwd/true/etc), closing the D-18 hollow-report gap; all 13 recorded Phase 83 reports re-assessed with no file changed.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-10-27 (shortly after 08:39 ET, base commit 57e7e34)
- **Completed:** 2026-10-27T12:48:06Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- Added `TRIVIAL_COMMANDS` (nine deliberately named commands) and `_first_program()` (POSIX-`shlex` tokenizer with a plain-split fallback, skipping leading `NAME=value` env assignments) to `tests/codex_report_status.py`.
- Replaced the hollow-report guard in `assess_report()`: a `commands_run` list whose only recorded command has no integer `exit_code`, or whose every recorded command's first program is in `TRIVIAL_COMMANDS`, now adds a specific incomplete reason. A list with no non-blank command at all keeps the original, unchanged "no commands run" reason.
- Re-assessed all 13 recorded Phase 83 `.last.json` reports under the updated checker and reconciled against their recorded `.status.json` verdicts (table below). No recorded file was changed.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- null exit_code and trivial-only command cases** - `07a2f17` (test)
2. **Task 2: GREEN -- require a non-trivial command with a recorded exit code; re-assess recorded reports** - `4a9a67a` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `tests/codex_report_status.py` - Added `TRIVIAL_COMMANDS`, `_first_program()`, and the extended hollow-report guard in `assess_report()`; updated the module docstring's list of incomplete causes.
- `tests/test_codex_report_status.py` - Added parametrized `test_hollow_report_guard` (5 cases: null-exit, trivial-only, env-prefixed-true, trivial-plus-real, failing-real).

## Verification Performed

- `uv run pytest tests/test_codex_report_status.py -q -rf` before the GREEN fix: 3 failed exactly as expected (`test_hollow_report_guard[null-exit]`, `[trivial-only]`, `[env-prefixed-true]`), 124 passed, 0 unrelated failures. Observed directly (log captured at `/tmp/85-04-red.log` during execution).
- `uv run pytest tests/test_codex_report_status.py -x -q` after the GREEN fix: **127 passed** in 0.16s. Observed directly, not inferred.
- `uv run ruff check tests/codex_report_status.py tests/test_codex_report_status.py`: **All checks passed!** Observed directly.
- `grep -c "TRIVIAL_COMMANDS" tests/codex_report_status.py` → `2` (definition + the `in TRIVIAL_COMMANDS` check). Matches the acceptance criterion ("at least 2").
- `grep -c "no command with a recorded exit code" tests/codex_report_status.py` → `1`. Matches the acceptance criterion exactly.
- Not run: `tests/test_codex_review_run.py` and the full `uv run pytest tests/ -x -q` suite. Per the plan's `<verification>` section, `test_codex_review_run.py` belongs to same-wave Plan 85-03 and the full-suite integration gate runs once post-wave (W06/W07), not inside this plan.

## Re-assessment of Phase 83 recorded reports

Ran `uv run python tests/codex_report_status.py --report <file> --exit-code 0 --expected-head <head> --expected-base <base> --current-head <head> --attempt 1 [--legacy-v1]` against all 13 `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/*.last.json` files. Expected head/base came from the matching `.meta.json` where one exists; the 5 files with no `.meta.json` used the report's own `inspected_head_sha`/`inspected_base_sha` (same pattern as the existing `_assess_recorded()` test helper). `--legacy-v1` was passed only for the two `schema_version: "1"` reports.

| File | schema_version | --legacy-v1 | Previous status (`.status.json`) | New status (this checker) | Changed? |
|---|---|---|---|---|---|
| 322afc50367d-postfix-a1.last.json | 2 | no | incomplete | incomplete | no |
| 322afc50367d-postfix-a2.last.json | 2 | no | complete | complete | no |
| 36eaa67c2976-final-a1.last.json | 2 | no | complete | complete | no |
| 385baa75ac1b-round6-a1.last.json | 2 | no | complete | complete | no |
| 49ded1e86444-phase-a1.last.json | 2 | no | incomplete | complete | **yes** |
| a7995baf187e-quick-a1.last.json | 1 | yes | complete | complete | no |
| b07e532dfd16-final-a1.last.json | 2 | no | complete | complete | no |
| b19e7b28687b-round5-a1.last.json | 2 | no | complete | complete | no |
| d501a68316b2-explicit-a1.last.json | 1 | yes | complete | incomplete | **yes** |
| d501a68316b2-explicit-a2.last.json | 2 | no | incomplete | complete | **yes** |
| d90c1c135dac-round7-a1.last.json | 2 | no | complete | complete | no |
| dbe1b7f56bdd-round2-a1.last.json | 2 | no | complete | complete | no |
| f46f18ccac12-round3-a1.last.json | 2 | no | complete | complete | no |

10 of 13 are unchanged. 3 changed; none of the recorded files were modified.

### Re-assessment changes (for the owner, T-85-11)

All three changes were verified to **predate this plan's D-18 fix** -- re-running each one against the checker as it existed immediately before this plan's commits (i.e. the Task-1 RED commit's implementation, unmodified from Phase 83/84) produces the identical status and reasons shown below. The hollow-report guard added in this plan did not cause any of these three; they are pre-existing drift between the `.status.json` snapshot taken at Phase 83 record time and later checker evolution within Phase 83 itself (the self-declared-incomplete phrase check and the structural `review_complete`/`incomplete_reasons` rules landed partway through Phase 83's own rounds).

1. **49ded1e86444-phase-a1.last.json**: recorded `incomplete` → now `complete` (reasons: none). Pre-85-04 checker also returns `complete`. Not a regression caused by this plan; the recorded `.status.json` for this file is older than whatever checker state produced the current `complete` result.
2. **d501a68316b2-explicit-a2.last.json**: recorded `incomplete` → now `complete` (reasons: none). Pre-85-04 checker also returns `complete`. Same pre-existing drift as above.
3. **d501a68316b2-explicit-a1.last.json**: recorded `complete` → now `incomplete` (reason: `"self-declared incomplete: limitations states 'incomplete review'"`). **This is the specific case the plan flags: a previously-complete report now reads incomplete.** Pre-85-04 checker also returns `incomplete` with the identical reason -- the drift predates this plan and is caused by the self-declared-incomplete phrase check (owner decision 2026-10-22, landed during Phase 83), not by the D-18 hollow-report guard. Per the plan's instruction, the recorded `d501a68316b2-explicit-a1.last.json` / `.status.json` files were **not modified**; this is disclosed here for the owner rather than silently accepted.

No file's status changed *because of* the null-exit-code or trivial-command checks added in this plan -- every one of the 13 recorded reports uses non-trivial commands (`git`, `cat`, `sed`, `rg`, `pytest`, `python3`/`.venv/bin/python`, `wc`, `cmp`) with recorded integer exit codes, so the new guard never fires on real evidence.

## Decisions Made

- Kept `TRIVIAL_COMMANDS` exactly as the plan specified (nine names) with a comment flagging extension as a sensitive change, rather than adding any judgment calls about what else might be "trivial."
- Used the report's own inspected head/base SHAs for the 5 recorded files lacking a `.meta.json` companion, mirroring the existing test suite's `_assess_recorded()` helper rather than inventing a new convention.

## Deviations from Plan

None - plan executed exactly as written. The "Re-assessment changes" disclosure above is the plan's own required output (not a deviation); confirming those three changes predate this plan's fix was the extra diligence the plan's T-85-11 threat-register entry calls for ("any change listed for the owner, files untouched").

## Issues Encountered

- `uv run pytest` initially failed with `ModuleNotFoundError: No module named 'loguru'` because only base dependencies were installed in this worktree's `.venv`. Resolved by running `uv sync --extra dev` before any test command; not a code change, so not logged as a deviation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `tests/codex_report_status.py`'s hollow-report guard is complete and independently verified against all recorded Phase 83 evidence. Ready for Plan 85-03's runner-side D-18 items (SIGTERM/SIGHUP process-group handling, `--trusted` verification, output-drain time limit, `_write_evidence_copy` cleanup, `redact_local_paths()` logging) and any later plan that depends on `assess_report()`'s completeness contract.
- No blockers or concerns for downstream plans in this wave.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: tests/codex_report_status.py
- FOUND: tests/test_codex_report_status.py
- FOUND: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-04-SUMMARY.md
- FOUND commit: 07a2f17 (Task 1)
- FOUND commit: 4a9a67a (Task 2)
