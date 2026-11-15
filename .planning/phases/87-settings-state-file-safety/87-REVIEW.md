---
phase: 87-settings-state-file-safety
reviewed: 2026-11-15T23:28:54Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - triggarr/config.py
  - triggarr/state.py
  - triggarr/web/routes.py
  - triggarr/templates/settings.html
  - tests/test_config.py
  - tests/test_state.py
  - tests/test_web.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 87: Code Review Report

**Reviewed:** 2026-11-15T23:28:54Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found
**Head reviewed:** `6262dd14` (diff base `633def80`)

## Summary

Scope was the Phase 87 diff (`git diff 633def80..HEAD`) plus the code it touches: `remove_instance` and `_removal_failed_response` in `routes.py`, `_atomic_toml_write(log_failure=...)` in `config.py`, the `load_state` non-object guard and `_recover_from_bad_state_file` in `state.py`, and the Remove button's row slot in `settings.html`.

The core ordering fix is sound. `remove_instance` now reads settings and re-checks existence inside `search_lock`, builds the post-removal settings on a copy, writes, and only then swaps live settings and tidies up. I traced the failed-write path and found no way for it to change live settings, the scheduler job, the client registry, the state entry or the tag cache. The D-05 response carries only the escaped instance name. The non-object guard sits at the single `load_state` entry point as the research recommended.

No blocker was found. Two warnings and four info items follow. Both warnings are cases where the new behavior tells the user or the log something that is not true, or tells them nothing.

Checks run during this review:

- `uv run ruff check triggarr/ tests/`: all checks passed.
- `uv run pytest tests/test_state.py tests/test_config.py tests/test_web.py -x -q`: 324 passed.
- Convention pack (`verify conventions --check`) on the seven files: no findings (not skipped).
- `load_state` edge cases were reproduced in a temp directory outside the repo (results cited in WR-01, IN-02 and SA-01).

Not verified: the row-slot swap was not exercised in a real browser. The htmx behavior described below is from reading the bundled `htmx.min.js` (2.0.8, default `responseHandling`) and the template.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: A state file that cannot be opened is reported as holding bad content, then reset with no copy kept

**File:** `triggarr/state.py:304-310` (message built at `:274-280`)
**Issue:** The `except (json.JSONDecodeError, OSError)` branch sends both cases through `_recover_from_bad_state_file` with the text "content that could not be read as JSON (...)". For an `OSError` the file's content was never read at all. Reproduced with a valid state file set to mode `000`; the log reads:

```
Could not set aside the bad state file .../state.json: PermissionError: [Errno 13] Permission denied
State file .../state.json held content that could not be read as JSON (PermissionError: [Errno 13] Permission denied: ...) where a JSON object was expected; queue progress and last-run times were reset to defaults ...
```

Two effects:

1. The warning states the file "held" the wrong kind of data. The file may be intact; the real cause is a permission or I/O problem. D-10 asks the warning to name "the kind of data found versus expected", and here nothing was found.
2. The set-aside copy fails for the same reason the read failed, so no copy exists. The next `save_state` then replaces the possibly intact file with defaults (`os.replace` needs only directory permission). Resetting on `OSError` predates this phase, but the D-08 "set aside first" promise does not hold on this path, and the only trace is the misleading line above.

**Fix:** Split the handler so the two causes get accurate wording, and keep the D-10 structure for the parse case only:

```python
try:
    with open(resolved_state_path, encoding="utf-8") as f:
        data = json.load(f)
except json.JSONDecodeError as exc:
    return _recover_from_bad_state_file(
        resolved_state_path, f"content that could not be read as JSON ({type(exc).__name__}: {exc})"
    )
except OSError as exc:
    return _recover_from_unreadable_state_file(resolved_state_path, exc)
```

where the unreadable variant logs "State file {path} could not be opened ({reason}); starting with default queue progress and last-run times. The file was left in place and will be replaced on the next save." Whether an unreadable file should be overwritten at all is a product question; see SA-03.

### WR-02: On htmx, every removal failure other than a failed save still shows the user nothing, and can leave an untrue message on the row

**File:** `triggarr/web/routes.py:983`, `:1007`; `triggarr/templates/settings.html:165-172`
**Issue:** The row slot only receives content on a 2xx response, because htmx 2.0.8's default `responseHandling` does not swap 4xx/5xx. `_removal_failed_response` returns 200 for that reason, but only the `except OSError` branch uses it. The other failure exits are still non-2xx with no `HX-Retarget`/200 handling:

- `:983` returns 400 "Instance '...' not found". This is the normal result when the instance was already removed in another tab or by the concurrent request the new in-lock check is designed for. The page shows nothing and the stale row stays.
- `:1007` catches `OSError` only. `_atomic_toml_write` has a separate `except Exception` branch (`config.py:187-203`) that re-raises non-`OSError` failures (for example a serialization error from `tomli_w`). That propagates as a bare 500. Live state is untouched, so this is safe, but the user again sees nothing, which is the silent failure D-04 set out to remove.

There is a second effect from D-06. After one failed save the row shows "'X' was not removed ... Nothing was changed." If the retry then ends in any of the non-swapped responses above (or a 401 after the session expired), that message stays on screen although it no longer describes what happened. In the "already removed elsewhere" case it is false.

**Fix:** Route the htmx case of these exits through the same 200-into-the-slot mechanism with wording that fits each cause, and widen the save boundary:

```python
except Exception as exc:  # error boundary: nothing live has been changed yet
    logger.error(...)      # as today; the writer already logs the non-OSError case
    return _removal_failed_response(request, instance_name)
```

For not-found on htmx, return 200 with a short escaped message such as "'X' no longer exists. Reload the page." (or an `HX-Redirect` to the settings page, which also clears the stale row). Add tests for both. If widening the `except` is not wanted, at minimum clear or replace the slot on any non-2xx response.

## Info

### IN-01: The error slot sits inside `<summary>`, so clicking the message collapses the instance

**File:** `triggarr/templates/settings.html:172`
**Issue:** The `remove-error` span is a child of `<summary>` and, unlike the Remove button, has no `data-stop-propagation`. Clicking the message, or starting to select its text to copy it, toggles the `<details>` and hides the instance's fields.
**Fix:** Add `data-stop-propagation` to the span (the handler at `:343-345` already covers any element with that attribute), or move the span just after `</summary>`; `hx-target="next .remove-error"` still resolves there.

### IN-02: `test_state_set_aside_permissions_not_wider` cannot fail

**File:** `tests/test_state.py:505-516`
**Issue:** The source is set to `0600` and the test asserts the copy has no bits beyond `0600`. `tempfile.mkstemp` always creates the temp file as `0600`, so the assertion holds even if `shutil.copy2` were replaced by a content-only copy. The real behavior is "copy takes the source's mode": a `0644` source produced a `0644` copy when I ran it. That meets the "at least as restrictive as the state file" discretion item, but the test does not pin it.
**Fix:** Use a source mode that differs from the `mkstemp` default and assert equality, for example `chmod(0o640)` then `assert stat.S_IMODE(corrupt.stat().st_mode) == 0o640`.

### IN-03: Concurrency tests depend on a private `asyncio.Lock` attribute

**File:** `tests/test_web.py:1603-1609`, `:1640-1646`
**Issue:** Both tests poll `lock._waiters` to know when the two requests are queued. This is a CPython implementation detail. If it changes, the tests fail on the "must be queued" assertion rather than pass falsely, so the risk is breakage on a Python upgrade, not a false green.
**Fix:** Acceptable as is. A version-independent alternative is to patch `_atomic_toml_write` with a function that blocks on a `threading.Event` for the first caller, which holds the lock from inside the route without touching lock internals.

### IN-04: `_atomic_toml_write` does not log or guard a failure to create the temp file

**File:** `triggarr/config.py:152`
**Issue:** Pre-existing, but the docstring extended in this phase describes when "Config write failed" is logged. `tempfile.mkstemp` runs before the `try`, so the most likely real-world failures (read-only volume, directory not writable, no space) raise without the writer logging anything, whatever `log_failure` is. `remove_instance` is unaffected because it logs in its own `except OSError`. `save_settings` and `add_instance` rely on the writer's line and get none on this path.
**Fix:** Move the `mkstemp` call inside the `try` (with `tmp_path = None` beforehand and a guard on the cleanup), or note the exception in the docstring. Belongs with the D-14 follow-up rather than this phase.

## Set aside (needs ruling)

### SA-01: A state file that is not valid UTF-8, or is very deeply nested, still crashes startup

**Where:** `triggarr/state.py:301-304`
**Why excluded:** CONSIST-03 covers valid JSON that is not an object. The non-UTF-8 case is already recorded in `.planning/backlog/MAINTENANCE.md` (line 15) as an owner decision, not scheduled.
**Effect if left as is:** Triggarr fails to start until someone deletes the file by hand. Disk corruption usually produces arbitrary bytes rather than tidy JSON, so non-UTF-8 is a likely form of the "truncated/unparseable" case that D-09 says gets one recovery behavior. Not yet recorded: a file of deeply nested brackets (reproduced with 200,000 `[`) raises `RecursionError`, which is also uncaught.
**Needs:** Ruling: in scope / defer / accept. The fix is small: catch `(json.JSONDecodeError, UnicodeDecodeError, RecursionError)` on the bad-content path, with one regression test each. If deferred, add the `RecursionError` case to the existing backlog note.

### SA-02: Add Instance and Save Settings can still bring back an instance that was just removed

**Where:** `triggarr/web/routes.py:902` vs `:923` (`add_instance`), `:640` vs `:727` (`save_settings`)
**Why excluded:** D-13 says other writers are recorded, not fixed. Already recorded in `.planning/backlog/MAINTENANCE.md` (line 16).
**Effect if left as is:** If an add or a save is waiting on the lock while a removal completes, it writes its older snapshot and the removed instance reappears in settings with no scheduler job or client until the next save or restart. It needs two overlapping requests, so it is unlikely for a single user. Note that the `remove_instance` docstring's claim ("cannot resurrect it from a stale snapshot") is true only for removal against removal.
**Needs:** Ruling: defer (as recorded) / schedule. Phase 90 reuses this route, so it may be a natural place.

### SA-03: Whether an unreadable (as opposed to corrupt) state file should be overwritten

**Where:** `triggarr/state.py:304-310`
**Why excluded:** Resetting to defaults on `OSError` predates this phase; WR-01 covers only the inaccurate wording added here.
**Effect if left as is:** A temporary permission or I/O problem at startup discards queue progress and last-run times, and no copy is kept because the copy fails the same way. Search history is unaffected. The cost is repeat searches of items already searched, not lost data the user entered.
**Needs:** Ruling: accept (startup always continues, per D-11's spirit) / defer / treat as a startup error.

---

_Reviewed: 2026-11-15T23:28:54Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
