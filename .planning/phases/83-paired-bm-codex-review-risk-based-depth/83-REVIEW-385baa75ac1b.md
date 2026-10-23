---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-23T19:10:00Z
depth: standard
review_head: 385baa75ac1b31a30c0d49c8a21cfa122a69bce0
diff_base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
previous_review: 83-REVIEW-b19e7b28687b.md
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
  warning: 1
  info: 3
  total: 4
carried_from_previous:
  fixed_verified: 0
  still_present: 3
  still_present_carried_phase_85: 6
  set_aside_ruled: 0
status: issues_found
---

# Phase 83: Code Review Report (round 6 re-review)

**Reviewed:** 2026-10-23T19:10:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found (1 new Warning, 3 new Info; no blockers)

## Summary

This round re-reviews local head `385baa75ac1b31a30c0d49c8a21cfa122a69bce0` against `83-REVIEW-b19e7b28687b.md`. The round-6 fixes are commits `469622a..69f15d6`. They touch:
- `tests/codex_report_status.py`: a `commands_run` list with only blank commands now counts as no commands run.
- `tests/codex_review_run.py`: a new `run_command` that starts pytest and codex in their own process group and kills the whole group on a timeout.
- `docs/review-classification-policy.md`: the sensitive row now names the review machinery.
- `docs/owner-cli-acceptance.md`: step 1 now lists the paired Codex review.
- New tests for each of these.

None of the other 18 in-scope files changed since round 5.

Checks run on this head:
- Targeted suites (`test_codex_report_status`, `test_codex_review_contract`, `test_review_instructions`, `test_app_cards`, `test_codex_review_run`, `test_review_checkpoint_record`): 341 passed.
- `ruff check triggarr/ tests/`: clean.
- Two probe scripts I ran on this macOS host (in the session scratchpad, not committed):
  - Sending SIGTERM to a parent blocked in `run_command(..., start_new_session=True)` leaves the child running.
  - Calling `os.killpg` on a group that holds only a zombie leader raises `PermissionError`, not `ProcessLookupError`.

All four round-6 changes do what they claim:
- **Blank-command rule:** correct for v1 and v2 reports, and a mix of blank and real commands still counts as complete.
- **Group kill on timeout:** a real grandchild test shows the timeout now kills grandchildren too.
- **Policy row and acceptance step:** both are guarded by drift tests that read the actual table cell and step line.

The new Warning is a side effect of the process-group change: a child in its own session no longer dies with the runner, so if the runner is terminated rather than interrupted, codex or pytest keeps running as an orphan. A missing `.status.json` is still never reported as clean.

## Previous findings status (83-REVIEW-b19e7b28687b.md)

| ID | Status | Evidence |
|----|--------|----------|
| IN-01 (Ctrl-C during the Codex wait leaves a reserved attempt with no `.status.json`) | **Still present, partly mitigated** | `run_command`'s `except BaseException` (`codex_review_run.py:139-142`) now kills the child group on `KeyboardInterrupt`, so codex no longer keeps running. But `execute` (`:546-556`) still catches only `Exception`, so the reserved attempt still has no status stub and the operator still gets a traceback. |
| IN-02 (the RunnerError invariant rests on a comment; the reservation can half-succeed) | **Still present** | `:546-549` still re-raises `RunnerError` without checking for `.status.json`. `reserve_outputs(run, prompt)` (`:545`) is still outside the `try`. |
| IN-03 (contract says UTF-8, code uses the locale encoding) | **Still present** | `:381`, `:435` and `:625` still pass `errors="replace"` without `encoding="utf-8"`. |
| WR-03 (PR judged by its own checker) | Still present, carried to Phase 85 per owner | No base-checker run. This round again changes `codex_report_status.py`, the checker that will judge it. |
| WR-04 (raw `.jsonl` exposes home path; docstring overclaims) | Still present, carried to Phase 85 per owner | The `redact_local_paths` docstring (`:309-316`) still says local paths "never appear". |
| IN-01 r4 (template matches display text) | Still present, carried to Phase 85 per owner | `cycle_grade.html:20-22` is unchanged. |
| IN-02 r4 (no `pr_url` / `scope` comparison) | Still present, carried to Phase 85 per owner | The checker still has no expected-PR or expected-scope argument. |
| IN-03 r4 (stale untrusted clause in prompt) | Still present, carried to Phase 85 per owner | The contract prompt is unchanged. |
| IN-04 r4 (`diff_argv` used only by tests; substring guards) | Still present, carried to Phase 85 per owner | Unchanged. |

The round-4 SA-01 to SA-03 items were ruled by the owner on 2026-10-23 and are not repeated here.

## Narrative Findings (AI reviewer)

### Warnings

#### WR-01: If the runner is terminated rather than interrupted, codex or pytest keeps running as an orphan (regression from `start_new_session`)

**File:** `tests/codex_review_run.py:112-146` (`run_command`), `:383`, `:419`
**Issue:**
- Before round 6, the pytest and codex children shared the runner's process group and controlling terminal.
- Now they start with `start_new_session=True`, so they are detached from the terminal and are cleaned up only by the Python `except` blocks in `run_command`.
- Those blocks run only when Python raises an exception: a timeout, or `KeyboardInterrupt` from SIGINT.
- Signals whose default action ends the process without any Python code running, such as SIGTERM (`kill <pid>`, a supervising tool's timeout, or an agent harness cancelling a Bash task) and SIGHUP (closing the terminal), now leave the whole child group running.

I confirmed this on this host. A parent blocked in `run_command(..., start_new_session=True, timeout=30)` was sent SIGTERM, and the child was still alive afterwards.

What follows from it:
- An orphaned `codex exec` keeps using Codex credits for up to the full model run, because the 1800 s limit was enforced by the parent, which is now dead.
- It keeps writing to `$OUT.jsonl` (an inherited descriptor) and may write `$OUT.last.json` into an attempt the operator thinks has stopped.
- `git worktree remove` in `finally` never runs, so the temp worktree stays registered.
- The next attempt can then run alongside a still-live earlier attempt.

The likely trigger is real: this runner is launched by agent harnesses that can stop a background task.
**Fix:** In `run_command`, while a session child is running, turn SIGTERM and SIGHUP into an exception so the existing `except BaseException` path kills the group. Restore the previous handlers afterwards:
```python
def _raise_on_signal(signum, _frame):
    raise SystemExit(128 + signum)

previous = {s: signal.signal(s, _raise_on_signal) for s in (signal.SIGTERM, signal.SIGHUP)}
try:
    with subprocess.Popen(argv, start_new_session=True, **kwargs) as proc:
        ...  # existing body
finally:
    for s, handler in previous.items():
        signal.signal(s, handler)
```
Add a real-subprocess test that sends SIGTERM to a parent running `run_command` and asserts the grandchild is gone, like the existing `test_timeout_kills_the_grandchild_too`. Then add one sentence to contract step 5 saying which signals clean up the child group.

### Info

#### IN-01: `_kill_group` suppresses the wrong error on macOS, so a timeout can be recorded as "could not start"

**File:** `tests/codex_review_run.py:106-109`, `:390-391`, `:424-426`
**Issue:**
- On macOS (the operator platform), `os.killpg` on a group whose only remaining member is an unreaped zombie leader raises `PermissionError` (EPERM), not `ProcessLookupError`. I confirmed this on this host.
- This can happen in the narrow window where the child and everything holding its pipe exit just as `communicate` times out.
- The `PermissionError` then escapes `run_command` from inside the `TimeoutExpired` handler.
- Because `PermissionError` is an `OSError`, `_run_pytest` records `exit_code: unknown` and `pytest could not start: PermissionError`, and `_run_codex` prints `codex could not start`.
- The result is still fail-safe (never clean), but the evidence names the wrong cause, and the "already exited" comment is wrong on the platform this runs on.

**Fix:** `contextlib.suppress(ProcessLookupError, PermissionError)` in `_kill_group`, with a comment that macOS returns EPERM for a zombie-only group. Add a unit test that calls `_kill_group` on an exited, unreaped `Popen`.

#### IN-02: The docstring says the group is killed on "any other interruption", but children left running after a normal exit are never killed

**File:** `tests/codex_review_run.py:121-127`, `:410-420`
**Issue:** The group is killed only on an exception. If the session leader exits normally (`uv`, or `codex`, whose stdout is a file rather than a pipe), any grandchild it leaves running (a leaked test server, or an MCP or sandbox helper) survives. It keeps running in a worktree that `finally` then removes. With the codex call there is no pipe that would keep `communicate` waiting, so nothing notices.
**Fix:** After a normal return in `run_command`, call `_kill_group(proc)` too. By then the leader has been reaped, so this needs the IN-01 suppression. Or narrow the docstring to "a timeout or a Python exception".

#### IN-03: The contract text was not updated for either round-6 runner and checker change

**File:** `docs/codex-adversarial-review-contract.md:61` (step 4.4), `:60` (step 4.2), `:67` (checker rules)
**Issue:** Step 4.4 still says the 1800 s limit is "Python's subprocess timeout". Step 4.2 does not say pytest runs in its own process group. Both behaviors are now `run_command`'s, and the module docstring (`codex_review_run.py:11-13`) was updated but the contract was not. The new rule that only-blank `commands_run` entries mean "no commands run" also appears only in code and tests. The contract is the governing document, and `test_codex_review_contract.py` checks it for drift, so the gap is in the document an owner reads.
**Fix:**
- Step 4.4: "enforced by the runner, which kills the whole child process group on timeout".
- Step 4.2: add the same wording for pytest.
- Checker paragraph: add "a report whose `commands_run` is empty or lists only blank commands is incomplete".
- Optionally add a contract drift assertion for each.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-10-23T19:10:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
