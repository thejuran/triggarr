---
phase: 87-settings-state-file-safety
reviewed: 2026-11-16T00:04:17Z
depth: standard
iteration: 2
head: f099c6a8
files_reviewed: 5
files_reviewed_list:
  - triggarr/state.py
  - triggarr/web/routes.py
  - triggarr/templates/settings.html
  - tests/test_state.py
  - tests/test_web.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 87: Code Review Report (iteration 2, review after fixes)

**Reviewed:** 2026-11-16T00:04:17Z
**Depth:** standard
**Files Reviewed:** 5 (`triggarr/config.py` read for context only; it was not changed in the fix round)
**Status:** issues_found
**Head reviewed:** `f099c6a8` (fix-round diff base `3bc9a610`)

The iteration 1 report (head `6262dd14`) is in git history for this file.

## Summary

This is a review of the fix round (`git diff 3bc9a610..HEAD -- triggarr tests`) against the code itself, not against `87-REVIEW-FIX.md`.

All four fixed findings (WR-01, WR-02, IN-01, IN-02) hold up. No blocker was found. Live state still cannot change on any failed-save path: in `remove_instance`, the first write to anything live is `request.app.state.settings = new_settings` at `triggarr/web/routes.py:1061`, and every failure exit (the settings-build guard, the `OSError` branch, the new `except Exception` branch, the not-found return) leaves the function before that line. Everything before it works on copies.

One new warning: the widened `except Exception` has a path on which the log holds no error-level entry and no system reason, and the line it does write points at an entry that does not exist. One new info item on the wording of the new unreadable-state-file warning.

What was checked for the fix-round diff, with the result:

| Check | Result |
|---|---|
| Nothing live mutated before the write succeeds | Holds (see above) |
| No internal detail in responses | Holds. Every failure exit returns `_removal_failed_response`, whose body is the fixed D-05 sentence plus the escaped name. The htmx not-found answer has an empty body. |
| `CancelledError` not swallowed | Holds. Both new handlers catch `Exception`; `asyncio.CancelledError` is a `BaseException` on the supported Python versions (3.11+) and propagates. |
| Log count per D-07 | Holds on three of four paths; fails on one (WR-01 below). The fixer's own open point about the content of the single error entry is SA-01. |
| htmx not-found redirect | Sound. Target is the fixed `settings_page` URL (no user input in it), app type and name length are validated first, nothing is echoed, nothing is mutated. The bundled htmx handles `HX-Redirect` before any swap. |
| CSP nonce discipline, no inline handlers | Holds. The new lines are inside the existing `<script nonce>` block; no `on*=` or `hx-on` attribute was added. |
| No unescaped user content | Holds. The listener writes only `textContent = ''`. The swapped message is built with `html.escape`. |
| `htmx:beforeRequest` listener scope | Holds by reading. The selector `summary > button[hx-post]` matches only the Remove buttons on this page (the tag inputs use `hx-get`, the connection pill is a `div`, the API-key regeneration goes through `htmx.ajax`). It clears only the slot under the clicked button's own `<summary>`. The bundled htmx sets `detail.elt` on every event and fires `htmx:beforeRequest` only after the confirmation is accepted, so cancelling the confirmation leaves the message in place. |
| `preventDefault` side effects | Holds by reading. It runs only when the clicked element is the `.remove-error` span, which contains text only. The Remove button's handler is unchanged. Keyboard toggling fires the click on the `<summary>` itself, so the span's listener does not run. |
| New unreadable-state-file path | One warning line, path and system reason only, no contents, no set-aside attempt, default state returned. Wording issue in IN-01. |

Checks run during this review:

- `uv run ruff check triggarr/ tests/`: all checks passed.
- `uv run pytest tests/test_state.py tests/test_web.py -x -q`: 213 passed. The full suite was not re-run by this review.
- Convention pack (`verify conventions --check`) on the five files: no findings (not skipped).
- A throwaway probe outside the repo reproduced WR-01 (output quoted there).

Not verified: nothing in `settings.html` was exercised in a browser by this review. The script behavior above is from reading the template and the bundled `htmx.min.js`. The tests for the new script lines match text in the page source; they do not run the script. The fix report records a partial headless-Chrome check without htmx loaded, and no real click-through of a failed removal followed by a retry.

## Iteration 1 dispositions

| Finding | Disposition | Verified | Notes |
|---|---|---|---|
| WR-01 unreadable state file reported as bad content | Fixed (wording only, as scoped) | Yes | `load_state` handles `OSError` separately (`triggarr/state.py:331-332`); one accurate warning, no set-aside attempt. The overwrite behavior is unchanged and is SA-03 (backlog). See IN-01 for one inaccurate clause. |
| WR-02 (a) non-`OSError` write failure showed nothing | Fixed | Yes | `triggarr/web/routes.py:1041-1054` returns the fixed message; live state untouched. Logging gap on one path: WR-01 below. |
| WR-02 (b) htmx not-found showed nothing | Fixed | Yes | `triggarr/web/routes.py:983-989` answers like a success (`HX-Redirect`); a plain POST keeps the escaped 400. |
| WR-02 (c) stale message could stay on the row | Fixed | Yes, by reading; not in a browser | `triggarr/templates/settings.html:357-362`. |
| IN-01 clicking the message collapsed the instance | Fixed | Yes, by reading; not in a browser | `triggarr/templates/settings.html:172`, `:346-351`. |
| IN-02 permissions test could not fail | Fixed | Yes | Source set to `0o640`, equality asserted (`tests/test_state.py:513-518`). |
| IN-03 tests depend on `asyncio.Lock._waiters` | Backlog (owner) | n/a | One more test of the same shape was added (`tests/test_web.py:1982-1987`). Same failure mode (fails loudly, never passes falsely); not made worse in kind. |
| IN-04 `mkstemp` outside the writer's `try` | Backlog (owner) | n/a | `triggarr/config.py` unchanged. |
| SA-01 non-UTF-8 or deeply nested state file crashes startup | Backlog (owner) | n/a | Unchanged by the fix round. |
| SA-02 add/save can bring back a removed instance | Backlog (already recorded) | n/a | Unchanged by the fix round. |
| SA-03 unreadable state file is overwritten on next save | Backlog (owner) | n/a | Unchanged by the fix round; the new warning now tells the user it will happen. |

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: When the settings write never starts, the log has no error entry and no reason, and points at a line that is not there

**File:** `triggarr/web/routes.py:1041-1054` (comment at `:999-1002`)
**Issue:** The new `except Exception` branch assumes every non-`OSError` failure comes from inside `_atomic_toml_write`, whose unexpected-error branch logs its own error line. So the route logs only a warning, leaves out the exception message, and says "see the config write error logged just before this".

That assumption does not hold when `run_in_executor` itself raises before the writer runs. The realistic cases are `RuntimeError: can't start new thread` (host or container thread limit reached) and `RuntimeError: cannot schedule new futures after shutdown`. Reproduced with a probe that makes `run_in_executor` raise `RuntimeError("can't start new thread")`. The whole log for the request was:

```
WARNING  Settings file .../triggarr.toml was not saved while removing radarr/4K; instance kept (RuntimeError; see the config write error logged just before this)
```

Effects:

1. D-07 is not met on this path: there is no error-level entry and the system reason is not recorded anywhere. Only the exception's type name survives.
2. The user is told "Check the Triggarr log for details", and the log sends them to an entry that does not exist.
3. The comment at `:999-1002` ("Each path logs exactly one error-level entry overall") is not true for this path.

The response and live state are correct on this path; the defect is in the log only. The path is narrow (it needs thread exhaustion or a shutdown race), which is why this is a warning.

`test_remove_instance_unexpected_write_error_keeps_live_state` (`tests/test_web.py:1804-1844`) exercises this same shape (the writer is replaced by a mock that logs nothing) but asserts nothing about the log, so it does not catch it.

**Fix:** Record whether the writer was entered, and log accordingly. This stays inside `routes.py`:

```python
writer_entered = False

def _write() -> None:
    nonlocal writer_entered
    writer_entered = True
    _atomic_toml_write(config_path, config_dict, log_failure=False)

try:
    await asyncio.get_running_loop().run_in_executor(None, _write)
except OSError as exc:
    ...  # unchanged
except Exception as exc:  # error boundary: nothing live has been changed yet
    if writer_entered:
        logger.warning(...)  # as today: the writer already logged the one error
    else:
        logger.error(
            "Could not save settings file {path} while removing {app}/{inst}; "
            "instance kept: {exc_type}: {exc}",
            path=config_path, app=app_name, inst=instance_name,
            exc_type=type(exc).__name__, exc=exc,
        )
    return _removal_failed_response(request, instance_name)
```

Add a test that makes `run_in_executor` raise and asserts exactly one error-level entry naming the app, the instance and the reason. The smaller alternative is to add `{exc}` to the existing warning and drop the "logged just before this" clause; that keeps the reason but still leaves this path without an error-level entry.

## Info

### IN-01: The unreadable-state-file warning promises the next save will replace the file, which is not always true

**File:** `triggarr/state.py:294-298`
**Issue:** The new warning ends "the next state save will replace it". That is true for the reproduced case (a file with no read permission). It is false when the path cannot be replaced, most plainly when `state.json` is a directory: `open` raises `IsADirectoryError` (an `OSError`), this warning is logged, and every later `save_state` then fails on `os.replace`. Docker creates a directory when a single-file bind mount points at a path that does not exist on the host, so this is reachable, though only by mounting the state file on its own rather than the config directory. The same holds on a read-only volume.
**Fix:** Say what will be attempted rather than what will happen, for example "the next state save will try to replace it".

## Set aside (needs ruling)

### SA-01: On a non-`OSError` failure inside the writer, the one error entry does not name the app or instance

**Where:** `triggarr/web/routes.py:1041-1053`, `triggarr/config.py:187-192`
**Why excluded:** Raised by the fixer as open point 1 in `87-REVIEW-FIX.md`. Closing it needs `log_failure=False` to also cover the writer's unexpected-error branch, which is a change to `triggarr/config.py`, and the owner kept that file out of the fix round.
**Effect if left as is:** D-07 asks for one error-level entry naming the app, the instance and the system reason. On this path the error entry names the settings file and the reason; the app and instance are in a separate warning line written right after it. Someone filtering the log to errors only sees a failed settings write with no indication it was a removal or which instance. Nothing is lost at the default log level.
**Needs:** Ruling: accept as is / approve the small `config.py` change. If approved, it also simplifies the WR-01 fix above (the route would log the single error on every path).

### SA-02: A failure closing the directory handle after the settings file was already replaced is reported as "not removed"

**Where:** `triggarr/config.py:204-206` (unchanged this phase), reached from `triggarr/web/routes.py:1030-1040`
**Why excluded:** `triggarr/config.py` is outside this iteration's file list and the code predates Phase 87. Noted because the brief asks whether live state and disk can disagree on a failed-save path.
**Effect if left as is:** If `os.close(dir_fd)` in the writer's `finally` raises after the rename succeeded, the route treats it as a failed save: the user is told nothing was changed and live state keeps the instance, but the file on disk no longer has it, so it disappears at the next restart. Live state itself is not changed on this path. A failing `close` on a directory handle is very unlikely in practice; this was found by reading, not reproduced.
**Needs:** Ruling: accept / defer to the backlog next to IN-04 (same function).

---

_Reviewed: 2026-11-16T00:04:17Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
