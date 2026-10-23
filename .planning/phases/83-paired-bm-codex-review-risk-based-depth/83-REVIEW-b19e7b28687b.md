---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-23T17:47:31Z
depth: standard
review_head: b19e7b28687bf7c0bc3dbcb7f7eda217b63e3d2e
diff_base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
previous_review: 83-REVIEW-49ded1e86444.md
files_reviewed: 18
files_reviewed_list:
  - .planning/config.json
  - .claude/schemas/codex-review-findings.schema.json
  - CLAUDE.md
  - docs/bm-review-baseline-2026-10-22.md
  - docs/buildomator-greptile-pilot.md
  - docs/codex-adversarial-review-contract.md
  - docs/owner-cli-acceptance.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - tests/codex_report_status.py
  - tests/codex_review_run.py
  - tests/test_app_cards.py
  - tests/test_codex_report_status.py
  - tests/test_codex_review_contract.py
  - tests/test_codex_review_run.py
  - tests/test_review_checkpoint_record.py
  - tests/test_review_instructions.py
  - triggarr/templates/partials/cycle_grade.html
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
carried_from_previous:
  fixed_verified: 2
  still_present_carried_phase_85: 6
  set_aside_ruled: 3
status: issues_found
---

# Phase 83: Code Review Report (round 5 re-review)

**Reviewed:** 2026-10-23T17:47:31Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found (new Info items only; no new blockers or warnings)

## Summary

This round re-reviews local head `b19e7b28687bf7c0bc3dbcb7f7eda217b63e3d2e` against the previous review, `83-REVIEW-49ded1e86444.md`. Since the previous review's source state (`04a424e`, the same source as `49ded1e8`), five source files changed: `tests/codex_report_status.py`, `tests/codex_review_run.py`, their two test files, and step 5 and the schema paragraph of `docs/codex-adversarial-review-contract.md`. This time the full 18-file scope was used, so `CLAUDE.md`, `docs/owner-cli-acceptance.md`, `.planning/config.json` and `tests/test_review_checkpoint_record.py` were also read. None of those four has a new defect.

Checks run on this head:
- Targeted suites (`test_codex_report_status`, `test_codex_review_contract`, `test_review_instructions`, `test_app_cards`, `test_codex_review_run`, `test_review_checkpoint_record`): 322 passed.
- `ruff check triggarr/ tests/`: clean.

Both owner-approved round-5 fixes (WR-01, WR-02) are fixed, and their tests confirm it. WR-01's regression test runs the exact reproduction from the previous review through the runner's own checker invocation. WR-02's tests use a real child process that prints bytes that are not valid UTF-8, not a mock. The six items the owner moved to Phase 85 are unchanged and still present. That is expected.

There are three new Info items, all edge cases in the round-5 failure handling. None of them can make an incomplete review look complete: a missing `.status.json` is still never reported as clean.

## Previous findings status (83-REVIEW-49ded1e86444.md)

| ID | Status | Evidence |
|----|--------|----------|
| WR-01 (v1 label skips structured completeness) | **Fixed and verified** | `codex_report_status.py:85-100, 362-370`: v1 rules apply only when `legacy_v1` is set and the report says `"1"`. Otherwise a v1 label adds `V1_NOT_LEGACY_REASON` and is judged by the current schema plus `_structural_completeness`. CLI `--legacy-v1` is at `:464-468`. Tests: `test_v1_label_cannot_hide_an_unfinished_review` (the previous review's exact reproduction), `test_cli_v1_report_needs_legacy_flag`, and `test_checker_argv_never_requests_the_legacy_v1_path` (runner argv has no flag, and the checker returns 1 on the reproduction). The two recorded v1 reports (`a7995baf187e-quick-a1`, `d501a68316b2-explicit-a1`) still assess complete with the flag and incomplete without it. The contract text at line 67 matches the code. |
| WR-02 (non-UTF-8 output crash; reserved attempt with no status) | **Fixed and verified** | `errors="replace"` is now on the pytest (`:334`), git (`:386`) and checker (`:576`) calls. The codex call writes to a file, so nothing is decoded. `execute` wraps everything after the reservation in `_execute_reserved` (`:497-508`), which covers the `.meta.json` write. The inner handler widened from `OSError` to `Exception` (`:537`). The real-subprocess tests `test_non_utf8_pytest_output_does_not_crash_the_runner` and `test_non_utf8_checker_output_still_writes_a_status` pass, and so does the `.meta.json` failure test. See IN-01 and IN-02 for the remaining edges. |
| WR-03 (PR judged by its own checker) | Still present, carried to Phase 85 per owner | No base-checker run or `audited_inputs_changed_in_diff` record. This round again modifies the checker that judges it. |
| WR-04 (raw `.jsonl` exposes home path; docstring overclaims) | Still present, carried to Phase 85 per owner | The `redact_local_paths` docstring (`codex_review_run.py:262-270`) still says local paths "never appear" in the evidence. |
| IN-01 (template matches display text) | Still present, carried to Phase 85 per owner | `cycle_grade.html:20-22` is unchanged. |
| IN-02 (no `pr_url` / `scope` comparison) | Still present, carried to Phase 85 per owner | The checker has no `--expected-pr-url` or `--expected-scope`. |
| IN-03 (stale untrusted clause in prompt) | Still present, carried to Phase 85 per owner | The contract prompt at line 36 is unchanged. |
| IN-04 (`diff_argv` used only by tests; substring guards) | Still present, carried to Phase 85 per owner | `codex_review_run.py:194` is unchanged. |
| SA-01 (`--trusted` self-declared) | Not applicable this round: ruled, carried to Phase 85 | Owner disposition 2026-10-23. |
| SA-02 (committed `.jsonl` contains home path) | Not applicable this round: owner ruled publish as-is | Owner disposition 2026-10-23. |
| SA-03 (PLAN.md outside Codex diff) | Not applicable this round: ruling deferred to Phase 85 | Owner disposition 2026-10-23. |

## Narrative Findings (AI reviewer)

### Info

#### IN-01: An interrupt (Ctrl-C) during the 30-minute Codex wait still leaves a reserved attempt with no `.status.json`

**File:** `tests/codex_review_run.py:497-508, 528-548, 681-692`
**Issue:** Both new handlers catch `Exception`. `KeyboardInterrupt` derives from `BaseException`, so it gets past both handlers and past `main`.
- The most likely interrupt is an operator pressing Ctrl-C while `_run_codex` waits up to 1800 seconds.
- In that case `subprocess.run` kills the child, and the `finally` removes the worktree.
- But `.prompt.txt`, `.meta.json` and a partial `.jsonl` remain with no status stub, and the operator gets a traceback.

Contract step 5 now says a stub is written when any step after the reservation "fails with any error (... or anything unexpected)". An interrupt is arguably not an error, so this is an edge, not a contradiction. Fail-safe still holds, because a missing status is never clean.
**Fix:** In `execute`, catch `KeyboardInterrupt` next to `Exception`. Write the stub (`"harness interrupted after reserving the output"`) only if `.status.json` does not exist, then re-raise. Alternatively, change the contract wording to "any exception other than an interrupt".

#### IN-02: The "every RunnerError has already written its status" invariant relies on a comment, and the reservation itself can half-succeed

**File:** `tests/codex_review_run.py:432-440, 496-500`
**Issue:**
- The outer `except RunnerError: raise` (`:500-502`) rests on a comment saying every `RunnerError` after the reservation has already written its stub. That is true today. But a future `raise RunnerError(...)` added to `_execute_reserved` without a stub would bring back the WR-02 symptom silently. The outer `except Exception` branch already checks `.status.json` exists, but the `RunnerError` branch does not.
- `reserve_outputs` creates `.prompt.txt` with `O_EXCL` and then writes the prompt outside any guard. If that write fails (for example, disk full), the name is reserved with an empty or truncated prompt, no stub, and an `OSError` traceback (`main` does not catch `OSError`). The comment at `:495` says "nothing else is touched if it fails", but the reservation file itself is.

**Fix:** In the outer `except RunnerError` branch, apply the same check: write a stub if `.status.json` does not exist. Move the prompt write inside the guarded region, for example by calling `reserve_outputs` inside the `try` and writing a stub when the `O_EXCL` open succeeded but the write raised.

#### IN-03: The contract says output is "decoded as UTF-8", but the code decodes with the locale encoding

**File:** `docs/codex-adversarial-review-contract.md:62` (step 5); `tests/codex_review_run.py:334, 386, 576`
**Issue:** The calls pass `text=True, errors="replace"` without `encoding=`, so Python decodes with the locale's preferred encoding. On this macOS host, and under Python 3.11's C-locale coercion, that is UTF-8, so behavior is correct today. But the contract's claim ("decoded as UTF-8 with replacement characters") is a property of the environment, not of the code. Under a non-UTF-8 locale, the decoded evidence would differ from what Codex sees in the worktree copy, which is written with `encoding="utf-8"`.
**Fix:** Add `encoding="utf-8"` to the three calls so the code matches the contract.

## Set aside (needs ruling)

None. The previous round's SA-01 to SA-03 were all ruled by the owner on 2026-10-23 (see the status table).

---

_Reviewed: 2026-10-23T17:47:31Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
