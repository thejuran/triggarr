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
