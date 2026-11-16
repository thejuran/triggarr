---
phase: 87-settings-state-file-safety
fixed_at: 2026-11-15T23:58:23Z
review_path: .planning/phases/87-settings-state-file-safety/87-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 87: Code Review Fix Report

**Fixed at:** 2026-11-15T23:58:23Z
**Source review:** `.planning/phases/87-settings-state-file-safety/87-REVIEW.md` (head reviewed `6262dd14`)
**Iteration:** 1
**Fix round base:** `3bc9a610`, committed directly on `phase-87-settings-state-file-safety`

**Summary:**
- Findings in scope (owner-approved): 4 (WR-01, WR-02, IN-01, IN-02)
- Fixed: 4
- Skipped: 0
- Rejected: 0
- Out of scope by owner decision, untouched: IN-03, IN-04, SA-01, SA-02, SA-03, `triggarr/config.py`

Two points need a ruling or a human check; they are listed under "Open points" below.

**Checks after the last fix commit:**
- `uv run pytest tests/ -x -q`: 3320 passed, 1 skipped (before this round: 3310 passed, 1 skipped)
- `uv run ruff check triggarr/ tests/`: All checks passed
- `uv run python tests/audit_lock_coverage.py`: covered: 8 / 8, uncovered: 0

## Fixed Issues

### WR-02: On htmx, every removal failure other than a failed save still shows the user nothing, and can leave an untrue message on the row

**Status:** fixed: requires human verification (logic change; part (c) is browser behavior)
**Files modified:** `triggarr/web/routes.py`, `triggarr/templates/settings.html`, `tests/test_web.py`
**Commits:** `48fc5b78` (failing tests), `79f0f9e2` (fix)

**Applied fix:**

- **(a) Non-OSError write failure.** `remove_instance` now also catches `Exception` (not `BaseException`, so cancellation still propagates) around the settings write. Live settings, the scheduler job, the client, the state entry and the tag cache are untouched and the fixed D-05 response is returned (htmx 200 into the row slot, plain POST 500) with no internal detail. Building the settings data (`_settings_to_dict`) was moved into its own guarded step just before the write, so a failure there is handled the same way and logs its own single error entry.
- **Log count (D-07).** `_atomic_toml_write`'s unexpected-error branch always logs an error-level "Config write failed (unexpected error)" line, whatever `log_failure` is. `config.py` was not edited. To keep the total at one error-level entry, the route logs its app/instance context for this case at warning level and leaves the writer's line as the single error. See open point 1.
- **(b) Instance not found inside the lock.** An htmx request now gets the same answer as a successful removal (empty 200 with `HX-Redirect` to the settings page), so the stale row disappears. A plain POST keeps its 400 with the escaped instance name. The htmx answer echoes nothing.
- **(c) Stale message.** The existing nonce'd script in `settings.html` gained a delegated `htmx:beforeRequest` listener that empties the row's `.remove-error` slot (`textContent = ''`) when a Remove request starts. No inline handlers, no `| safe`, no markup written.

**Tests added (`tests/test_web.py`):**
- `test_remove_instance_unexpected_write_error_keeps_live_state` (plain and htmx)
- `test_remove_instance_unexpected_real_write_error_logs_one_error`
- `test_remove_instance_settings_build_failure_logs_one_error`
- `test_remove_instance_not_found_htmx_redirects_like_success`
- `test_remove_instance_not_found_plain_keeps_400_and_escapes_name` (passed before the fix; pins the unchanged plain path)
- `test_remove_instance_concurrent_same_instance_htmx_second_redirects`
- `test_settings_clears_row_error_slot_when_remove_request_starts`

No existing test was changed for this finding. The existing not-found tests use plain POSTs, whose behavior is unchanged.

### WR-01: A state file that cannot be opened is reported as holding bad content, then reset with no copy kept

**Status:** fixed (wording only, as scoped)
**Files modified:** `triggarr/state.py`, `tests/test_state.py`
**Commits:** `2c1a9381` (failing test), `0bd66a85` (fix)

**Applied fix:** `load_state` now handles `json.JSONDecodeError` and `OSError` separately. The parse case is unchanged (D-08 to D-10 recovery with set-aside). The `OSError` case goes to a new `_start_with_defaults_for_unreadable_state_file`, which logs one warning: the file could not be opened or read, the system reason, that Triggarr is starting with default queue progress and last-run times, that search history is unaffected, and that the file was left as it is, no copy was made and the next state save will replace it. No set-aside is attempted, so the misleading "Could not set aside the bad state file" line is gone. The warning carries the path and the reason only, never file contents.

Behavior is unchanged: Triggarr still starts with default state on `OSError`, and the file is still replaced by the next save. No protection against that overwrite was added; that remains the open owner question SA-03.

**Tests added (`tests/test_state.py`):** `test_state_unreadable_warning_is_accurate_and_skips_set_aside` (failure on open, and failure during read).

### IN-01: The error slot sits inside `<summary>`, so clicking the message collapses the instance

**Status:** fixed, with a deviation from the suggested mechanism (see open point 2)
**Files modified:** `triggarr/templates/settings.html`, `tests/test_web.py`
**Commits:** `42e410a2` (failing test), `92ddc3a1` (fix)

**Applied fix:** The `.remove-error` span now carries `data-stop-propagation`. That alone does not work: a check in headless Chrome showed a `<summary>` still toggles when a non-interactive child stops propagation (the Remove button is exempt only because it is a button). The existing nonce'd handler therefore also cancels the click's default action when the element is the removal-error slot. Buttons are handled exactly as before.

**Tests changed (`tests/test_web.py`):** `test_settings_remove_button_targets_row_error_slot` gained assertions (nothing removed): every slot has `data-stop-propagation`, and the page script cancels the default action for the slot.

### IN-02: `test_state_set_aside_permissions_not_wider` cannot fail

**Status:** fixed (test only)
**Files modified:** `tests/test_state.py`
**Commit:** `44120fc0`

**Applied fix:** The source file is now set to `0o640` (different from the `0o600` that `tempfile.mkstemp` gives the temp copy) and the test asserts the copy's mode equals `0o640`. Confirmed it can fail: with `shutil.copy2` swapped for a content-only copy in a throwaway run, the test fails; with the real code it passes.

## Open points

1. **D-07 on the non-OSError path is met for the count, not fully for the content.** The single error-level entry is the writer's line, which names the settings file and the system reason but not the app or instance. Those appear in the adjacent warning line. Making the one error entry name all three needs `log_failure=False` to also cover the writer's unexpected-error branch, which is a change to `triggarr/config.py` (out of scope this round). Needs a ruling: accept as is, or approve that small `config.py` change.
2. **IN-01 mechanism differs from the suggested one.** The review's "the existing handler covers it" does not hold in a browser, so the handler was extended by one line for the slot only. If moving the span outside `<summary>` is preferred instead, that also needs a layout check and a change to an existing template test.
3. **Browser verification is partial.** The rendered Settings page was loaded in headless Chrome from a saved file with a probe script: clicking the slot leaves the instance open, clicking Remove leaves it open, and a `htmx:beforeRequest` event from a row's Remove button empties that row's slot and no other. That run did not load htmx and had no CSP header. The event name and its `detail.elt` were confirmed by reading the bundled htmx 2.0.8. A real click-through (failed removal, then a retry that ends in 401) has not been done.

## Noticed, not changed (out of scope)

- The two checks before the lock in `remove_instance` ("Invalid app type", "Instance name too long") still return 400, which htmx does not swap. The Settings page cannot produce either request, so only hand-built requests reach them.
- The Settings page comment above the `data-stop-propagation` handler credits `stopPropagation` with keeping the instance open for the Remove button. In Chrome the button is exempt because it is interactive, with or without that handler. Harmless.
- `load_state` treats a state file that exists but raises a non-`OSError`, non-`JSONDecodeError` error (invalid UTF-8, very deep nesting) as a crash. This is SA-01, already recorded.
- IN-04 (`mkstemp` outside the writer's `try`) is unchanged. For `remove_instance` that failure is an `OSError` and is logged once by the route.

---

_Fixed: 2026-11-15T23:58:23Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_

---

# Fix round 2

**Date:** 2026-11-15 (owner-approved scope of the same day)
**Sources:** `.planning/phases/87-settings-state-file-safety/87-REVIEW.md` (iteration 2: WR-01, IN-01, SA-01) and Codex finding F001 (`.planning/phases/87-settings-state-file-safety/codex/f099c6a85711-phase-fix1-a1.last.json`)
**Base:** `d524b1b7`, committed directly on `phase-87-settings-state-file-safety` (no worktree, no temp branch)

**Summary:**
- Items in scope: 5
- Done: 4 (item 1 F001 `add_instance`, item 3 WR-01 + SA-01, item 4 IN-01, item 5 lock audit)
- Stopped, nothing changed: 1 (item 2, the same stale-snapshot problem in `save_settings`; needs an owner ruling, see below)

**Checks after the last code commit (`d5aa50c7`):**
- `uv run pytest tests/ -x -q`: 3327 passed, 1 skipped (before this round: 3320 passed, 1 skipped)
- `uv run ruff check triggarr/ tests/`: All checks passed
- `uv run python tests/audit_lock_coverage.py`: covered: 8 / 8, uncovered: 0

## Item 1: Codex F001, Add Instance during a removal's write brought the removed instance back

**Status:** fixed: requires human verification (logic change in a concurrency path)
**Files modified:** `triggarr/web/routes.py`, `tests/test_web.py`
**Commits:** `8d04daa8` (failing tests), `bef326b9` (fix)

**What changed:** In `add_instance`, the read of live settings, the duplicate check, the max-5 check, the build of the new settings and the pydantic validation moved inside `async with request.app.state.search_lock`. The two checks that need no settings (app type, instance-name validity) stay before the lock. Validation still happens before the write, and live settings are still swapped only after the write succeeds. Every response is unchanged (the three 400 bodies, the validation 400, the 303 redirect).

**Tests added (`tests/test_web.py`):**
- `test_add_instance_during_removal_write_does_not_resurrect_removed`: pauses the removal's writer, submits Add Instance, releases the writer, then asserts the removed instance is absent from the settings file, live settings, the client registry and state, and the added instance is present. Failed before the fix with the removed instance back in the settings file.
- `test_add_instance_duplicate_check_uses_settings_current_under_lock`: two overlapping Adds of the same name now give one 303 and one "already exists" 400 (before the fix both returned 303).

Neither test reads `asyncio.Lock._waiters` (the dependency recorded as IN-03).

## Item 2: the same stale snapshot in `save_settings`

**Status:** stopped as instructed; `save_settings` is untouched and no test was committed (a failing test without its fix would break the suite).

**Why a reordering alone does not work.** Moving the build inside the lock is easy, but it does not give the intended result, because of how Save merges the form. For any app that has fields in the form, Save treats the form as the complete list of that app's instances:

- An instance named in the form that is not in current settings is created as new, with a fresh id. This is pinned by `test_save_settings_new_form_instance_gets_id`.
- An instance in current settings that is not named in the form is deleted. This is pinned by `test_save_settings_form_removal_invalidates_tag_cache`, and the route comments describe it as supported ("removed via form omission").

So with the build moved inside the lock:

- Save overlapping a removal: the form still carries the removed instance's fields, the instance is no longer in settings, and Save creates it again (new id; a blank API-key field can no longer be filled from the old value). The instance comes back, or the whole Save is turned away by validation. Which of the two happens was worked out by reading the code, not by running it.
- Save overlapping an add: the form does not name the added instance, so Save deletes it.

Getting "the instance stays removed and the rest of the Save applies" therefore needs a change to the merge rule, which is the stop condition for this item.

**Options for the owner:**

| Option | What the user gets | Cost and risk |
|---|---|---|
| A. Save only updates instances that exist when it runs. It never creates and never deletes; Add and Remove are the only ways to do that. | A Save can never bring a removed instance back or drop an added one, including from a page that was opened before the other change (stale tab), not only during an overlap. | Small code change, but it removes two behaviors that tests pin today (the two tests named above would change). Anything that posts to the Save endpoint to create or delete an instance would stop working. The Settings page itself does not appear to depend on either: its form lists every instance and has separate Add and Remove buttons (read from the template, not checked in a browser). |
| B. Keep both behaviors; Save compares the settings it saw when the request arrived with the settings at the time it holds the lock. Instances removed in between are skipped, instances added in between are kept. | Fixes the overlap case only (a Save sent while a removal or add is still being written). A Save from a stale tab still brings a removed instance back, as today. | More logic in an already long function, harder to reason about and test. No existing test changes. |
| C. Leave as is. | No change. The gap stays recorded in `.planning/backlog/MAINTENANCE.md`. | None now; the window is narrow for the overlap case, wider for the stale-tab case. |

Recommendation: A, because it is the only one that also closes the stale-tab case and it is the simplest rule to explain. It is a product decision (it removes "delete by leaving out of the form" and "create through Save"), so it was not made here.

## Item 3: iteration 2 WR-01 + SA-01, one error entry for every failed removal

**Status:** fixed
**Files modified:** `triggarr/config.py`, `triggarr/web/routes.py`, `tests/test_config.py`, `tests/test_web.py`
**Commits:** `7add7be4` (failing tests), `a6043c37` (fix)

**What changed:**
- `triggarr/config.py`, `_atomic_toml_write`: `log_failure=False` now also suppresses the "Config write failed (unexpected error)" line. The only code change is an `if log_failure:` around that one log call, plus the docstring. With the default `log_failure=True` nothing changes for any other caller. The directory-fsync warning and the temp-file cleanup error still always log.
- `triggarr/web/routes.py`, `remove_instance`: the two handlers around the write (`OSError`, then `Exception` with the round 1 warning) became one `except Exception` that logs the single error-level entry with the path, the app, the instance, the exception type and the reason, then returns the fixed D-05 response. It covers an `OSError` from the writer, any other exception from inside the writer, and the write never starting (`run_in_executor` raising). The warning that said "see the config write error logged just before this" is gone. `BaseException` and `CancelledError` are not caught. No response body changed.

**Tests added:**
- `tests/test_web.py`: `test_remove_instance_write_never_starts_logs_one_error` (plain and htmx): `run_in_executor` raises; one error entry naming the app, the instance and the reason, no warning line, fixed response, live state untouched, writer never called.
- `tests/test_config.py`: `test_atomic_toml_write_log_failure_false_suppresses_unexpected_error_line`, and `test_atomic_toml_write_logs_unexpected_error_by_default` (passed before the fix; pins the exact default line).

**Existing test changed (one):** `test_remove_instance_unexpected_real_write_error_logs_one_error` in `tests/test_web.py`. It encoded the round 1 workaround (the writer's line as the one error, plus a warning carrying the app and instance). It now asserts the single error names the app, the instance and the reason, that no "Config write failed" line appears, and that there is no warning line. Its other assertions are unchanged. All existing writer tests in `tests/test_config.py` pass unmodified.

**Remaining edge, unchanged by design:** if the writer fails and deleting its temp file then also fails, the writer still logs its separate "Failed to clean up temp file" error, so that double failure gives two error entries.

## Item 4: iteration 2 IN-01, unreadable-state-file warning wording

**Status:** fixed (wording only)
**Files modified:** `triggarr/state.py`, `tests/test_state.py`
**Commits:** `81538003` (failing test), `d5aa50c7` (fix)

**What changed:** the warning now ends "the next state save will try to replace it" instead of "will replace it". Nothing else in `load_state` changed.

**Test added (`tests/test_state.py`):** `test_state_unreadable_warning_does_not_promise_replacement`.

## Item 5: lock audit

`uv run python tests/audit_lock_coverage.py` reports `covered: 8 / 8, uncovered: 0`, the same as before this round. `tests/audit_lock_coverage.py` and `tests/test_audit_lock_coverage.py` were not changed: the audit checks that every writer reference sits inside the lock, and moving `add_instance`'s reads inside the lock does not affect that.

## Noticed, not changed (out of scope)

- `save_settings` still builds from a pre-lock snapshot (item 2 above).
- In `add_instance`, the "Invalid settings rejected" warning is now written while the lock is held. It only happens when validation fails and is one log line.
- `add_instance` adds the new instance's state entry in memory but does not save the state file at that point (it is saved by the next state save). Same as before this round.
- The docstring of `test_atomic_toml_write_log_failure_false_suppresses_primary_line` in `tests/test_config.py` says only the primary line is suppressed. The test still passes and was left unmodified as instructed; the sentence is now slightly out of date.
- The frontmatter at the top of this file still describes round 1.
- No review of these commits has been run. The BM review and the paired Codex pass on the new head are still to do.

---

_Fixed: 2026-11-15 (round 2)_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 2_
