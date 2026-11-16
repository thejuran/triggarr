---
phase: 87-settings-state-file-safety
verified: 2026-11-15T23:40:33Z
status: human_needed
score: 3/3 roadmap success criteria verified (29/29 PLAN must-have truths verified)
has_blocking_gaps: false
overrides_applied: 0
human_verification:
  - test: "Open Settings in a real browser, trigger a removal that fails to save (e.g. temporarily make the config directory read-only or patch in a test env), observe the row"
    expected: "The D-05 sentence appears inside the clicked instance's own row, with no full-page reload; any unsaved edits in other instance rows or the Add Instance form are still present after the failure; clicking Remove again on that row replaces the message; reloading the page clears it"
    why_human: "htmx DOM-swap behavior, page-reload-survival of unsaved form state, and the visual row placement were never exercised in a real browser for this phase -- only proven via template-structure and HTTP-response-content tests"
  - test: "With a failed removal's error message showing on a row, click or try to select the message text itself"
    expected: "Selecting/reading the message does not collapse the instance's <details> section"
    why_human: "Code review finding IN-01: the .remove-error span is a child of <summary> and has no data-stop-propagation, unlike the Remove button, so a click on the message toggles the row collapsed -- this needs a human to judge whether the resulting UX (message hidden until re-expanded) is acceptable"
  - test: "Trigger removal while aria-live=\"polite\" region is empty, then make a save fail, with a screen reader running"
    expected: "The screen reader announces the new error text without requiring focus to move to the row"
    why_human: "aria-live announcement behavior is assistive-technology/browser behavior, not inferable from source"
---

# Phase 87: Settings & State-File Safety Verification Report

**Phase Goal:** Removing an instance can't corrupt live settings when the disk write fails, and a corrupted-but-valid state file recovers to defaults instead of crashing.
**Verified:** 2026-11-15T23:40:33Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When removing an instance fails to save the settings file, the instance keeps its existing settings, schedule and live connection exactly as before the attempt | VERIFIED | `remove_instance` (`triggarr/web/routes.py:978-1017`) reads settings and re-checks existence inside `search_lock`, builds the post-removal `Settings` on a copy, writes via `_atomic_toml_write`, and only reassigns `request.app.state.settings` after the write returns (line 1024). `test_remove_instance_write_failure_keeps_live_state` (both plain and htmx) asserts "4K" stays in live settings (same object identity), `scheduler.remove_job` is never called, the client stays registered and unclosed, and the state/tag-cache entries survive -- ran it live: **PASS** (`uv run pytest tests/test_web.py -k remove_instance -q` → 17 passed). Concurrency is covered by `test_remove_instance_concurrent_removals_both_persist` and `test_remove_instance_concurrent_same_instance_second_is_not_found`, both lock-held and both passing against the real writer and real TOML file on disk. |
| 2 | When that save fails, the user sees an error stating the instance was not removed, with no internal detail exposed | VERIFIED (for the tested/realistic failure mode) | `_removal_failed_response` (`routes.py:938-956`) returns the exact fixed sentence `"'<escaped name>' was not removed: the settings file could not be saved. Nothing was changed. Check the Triggarr log for details."` -- 200 for `HX-Request: true` (no `HX-Redirect`), 500 for a direct POST. `test_remove_instance_write_failure_htmx_shows_message`, `..._plain_returns_500`, `..._no_internal_detail`, and `..._escapes_name` pass; `test_remove_instance_real_write_failure_logs_one_error` drives a **real** `os.replace` `OSError(ENOSPC)` (writer not mocked) and confirms exactly one ERROR log line naming "radarr", "4K" and "No space left on device", with no duplicate "Config write failed" line and no leftover `.tmp` file. See "Minor non-blocking findings" below for a residual edge case (non-`OSError` writer exceptions) the review flagged. |
| 3 | When the saved state file holds valid JSON that is not an object ([], 42, null), Triggarr starts with default state and logs a warning instead of crashing | VERIFIED | `load_state` (`triggarr/state.py:284-319`) adds `if not isinstance(data, dict): return _recover_from_bad_state_file(...)` before any dict-only helper runs. Independently re-ran this by hand (not via pytest) against `[]`, `42`, `null`, `"hello"`, `true` in a scratch temp dir: each returned `{'radarr': {}, 'sonarr': {}, 'lidarr': {}, 'search_log': []}` with no exception, logged one WARNING naming the kind found (e.g. "a list") and that a diagnostic copy was kept, and left exactly one `state.json.corrupt` file holding the original bad content. `uv run pytest tests/test_state.py -k "non_object or set_aside or wrong_structure"` → 16 passed. |

**Score:** 3/3 roadmap success criteria verified.

### PLAN Frontmatter Must-Haves (granular truths)

All 29 must-have truths across 87-01-PLAN.md (10), 87-02-PLAN.md (10) and 87-03-PLAN.md (9) were checked against the current code and tests, not just the SUMMARY narrative. Representative spot-checks beyond the roadmap-level table above:

- `_atomic_toml_write(path, data, *, log_failure: bool = True)` exists in `triggarr/config.py:129`; `remove_instance` is the only caller passing `log_failure=False` (`grep -n "log_failure=False" triggarr/web/routes.py` → exactly one line, inside `remove_instance`); `test_atomic_toml_write_logs_os_replace_failure` is unmodified and passes, confirming every other caller still logs as before.
- `tests/audit_lock_coverage.py` → `covered: 8 / 8, uncovered: 0` (run live).
- `_recover_from_bad_state_file` is called from both the `except (json.JSONDecodeError, OSError)` branch and the `if not isinstance(data, dict)` branch (`grep -c "return _recover_from_bad_state_file("` → 2), satisfying D-09's "one shared recovery path" requirement.
- `state.json.corrupt` set-aside: `shutil.copy2` preserves mode, writes to a same-directory temp file then `os.replace`s onto the one fixed name (`triggarr/state.py:244-281`); `test_state_set_aside_keeps_exactly_one_copy` and the three `test_state_set_aside_failure_still_recovers[mkstemp|copy2|replace]` cases pass, proving the copy step never blocks recovery and never leaks a temp file or descriptor.
- `settings.html`'s instance row: `hx-target="next .remove-error" hx-swap="innerHTML"` on the Remove button and the empty, `aria-live="polite"` `.remove-error` span land inside the same `<summary>` (`triggarr/templates/settings.html:163-173`); `test_no_new_body_swap_html_targets` now asserts `len(matches) == 0` with the stale `matches[0]` indexing assertion removed, and passes; `grep -c 'hx-target="body"' triggarr/templates/settings.html` → 0.
- `.planning/backlog/MAINTENANCE.md` carries all four required Phase-87-dated records (D-13 audit, D-14 follow-up, UTF-8 crash finding, pre-lock snapshot finding) -- re-verified the D-13 route:line evidence directly against current `routes.py` (e.g. `save_settings` read at :640, lock at :727, swap at :732; `add_instance` read at :902, swap at :928) and all citations are accurate for the current head.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `triggarr/web/routes.py` | Reordered `remove_instance`, `_removal_failed_response`, isolated cleanup | VERIFIED | Read-under-lock → build copy → write (`log_failure=False`) → swap → isolated scheduler/client cleanup, exactly as PLAN 87-01 specifies; wired into the route decorator and called by tests via `TestClient`/`httpx.AsyncClient`. |
| `triggarr/config.py` | `log_failure` keyword flag on `_atomic_toml_write` | VERIFIED | `log_failure: bool = True`; primary "Config write failed" line wrapped in `if log_failure:`; all other branches (dir-fsync warning, temp-cleanup error, unexpected-error branch) unchanged. |
| `triggarr/state.py` | `isinstance(data, dict)` guard + `_recover_from_bad_state_file` | VERIFIED | Both present; guard precedes `_is_v22_state_format`; helper shared by both broken-file branches; manually exercised against 5 non-object JSON roots with real file I/O (see Truth 3 above). |
| `triggarr/templates/settings.html` | Row-local error slot, retargeted Remove button | VERIFIED | `.remove-error` span inside `<summary>`, `hx-target="next .remove-error"`, `hx-swap="innerHTML"`; classes (`w-full`, `flex-wrap`, `gap-2`, `text-red-400`, `text-sm`) all present in `triggarr/static/css/output.css` (no rebuild needed). |
| `tests/test_web.py`, `tests/test_config.py`, `tests/test_state.py` | New regression tests named in each PLAN's must_haves | VERIFIED | Every named test (`test_remove_instance_write_failure_keeps_live_state`, both concurrency tests, `test_remove_instance_real_write_failure_logs_one_error`, the four response-content tests, the two tidy-up resilience tests, `test_atomic_toml_write_log_failure_false_suppresses_primary_line`, `test_settings_remove_button_targets_row_error_slot`, the rewritten `test_no_new_body_swap_html_targets`, `test_state_wrong_structure_list_recovers`, `test_state_non_object_root_recovers` x6, `test_state_non_object_warning_names_kind_without_contents`, all five `test_state_*set_aside*` tests) exists and was run directly -- all pass. |
| `.planning/backlog/MAINTENANCE.md` | D-13/D-14/UTF-8/pre-lock-snapshot records | VERIFIED | All four bullets present, each tagged `(Phase 87, 2026-11-15)`, each with accurate current-code line evidence (re-checked against the actual file, not just trusted from the SUMMARY). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `remove_instance` | `_atomic_toml_write` | `run_in_executor(..., functools.partial(_atomic_toml_write, config_path, ..., log_failure=False))` inside the lock, inside `try/except OSError` | WIRED | Confirmed at `routes.py:997-1017`; `tests/audit_lock_coverage.py` independently confirms the call is lexically inside `search_lock`. |
| `remove_instance` | `request.app.state.search_lock` | settings read + not-found re-check inside `async with` | WIRED | `routes.py:978-983`; line number of the settings read (979) is inside, not before, the `async with` (978). |
| `settings.html` Remove button | `span.remove-error` | `hx-target="next .remove-error" hx-swap="innerHTML"` | WIRED (structurally; not browser-exercised -- see Human Verification) | `templates/settings.html:163-173`; proven by `test_settings_remove_button_targets_row_error_slot` against a real multi-instance render. |
| `load_state` non-dict branch | `_recover_from_bad_state_file` | `if not isinstance(data, dict): return _recover_from_bad_state_file(...)` | WIRED | `state.py:312-313`; manually exercised, see Truth 3. |
| `load_state` except branch | `_recover_from_bad_state_file` | shared call for JSONDecodeError/OSError | WIRED | `state.py:304-310`. |
| `triggarr/search/scheduler.py::create_lifespan` | `load_state` | single startup call site | WIRED (unchanged) | `grep -n "load_state(" triggarr/search/scheduler.py` → one call at line 481. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Non-object JSON state roots recover to defaults with a set-aside copy and no crash (real filesystem, no mocks) | ad-hoc Python script writing `[]`, `42`, `null`, `"hello"`, `true` to a temp `state.json` and calling `load_state()` directly | All 5 returned default state, logged one warning each, left exactly one `state.json.corrupt` | PASS |
| `remove_instance` regression suite | `uv run pytest tests/test_web.py -k remove_instance -q` | 17 passed, 135 deselected | PASS |
| State recovery / set-aside regression suite | `uv run pytest tests/test_state.py -q` | 51 passed | PASS |
| Writer `log_failure` regression suite | `uv run pytest tests/test_config.py -k atomic_toml_write -q` | 6 passed | PASS |
| AST lock-coverage audit | `uv run python tests/audit_lock_coverage.py` | `covered: 8 / 8, uncovered: 0` | PASS |
| Full test suite (run once) | `uv run pytest tests/ -q` | 3310 passed, 1 skipped (pre-existing, unrelated) | PASS |
| Lint | `uv run ruff check triggarr/ tests/` | All checks passed! | PASS |
| Named commits from SUMMARYs exist on this branch | `git cat-file -e` for all 13 cited commit hashes | all 13 present | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CONSIST-01 | 87-01 | Instance keeps settings/schedule/connection on failed save | SATISFIED | Full-postcondition test + real-writer test + both concurrency tests, all passing against current code. |
| CONSIST-02 | 87-01, 87-02 | User sees "not removed" error with no internal detail, on the instance's row | SATISFIED (dominant failure mode); see minor finding below | D-05 response content/escaping tests pass; row-local slot wiring proven by render test; see "Minor non-blocking findings" for an edge case outside the tested `OSError` path. |
| CONSIST-03 | 87-03 | Non-object valid-JSON state file recovers to defaults with a warning, no crash | SATISFIED | Verified both via the test suite and an independent manual repro against real files. |

No orphaned requirements: REQUIREMENTS.md maps only CONSIST-01/02/03 to Phase 87, and all three are claimed in PLAN frontmatter (87-01: CONSIST-01, CONSIST-02; 87-02: CONSIST-02; 87-03: CONSIST-03).

### Anti-Patterns Found

None in the files this phase modified. No `TBD`/`FIXME`/`XXX`/`HACK` markers; the only `placeholder` matches are legitimate HTML `placeholder=` input attributes and docstring prose about placeholder URLs, unrelated to stubbed code. No bare `except:` (`grep -cE "^\s*except:\s*$" triggarr/web/routes.py` → 0, each cleanup step uses `except Exception as exc:` with logging, matching the plan's "error boundary" intent).

### Minor non-blocking findings (from 87-REVIEW.md, independently assessed)

These do not fail any of the three roadmap success criteria or any PLAN must-have as literally written (the PLAN's own must-haves scope the D-05/D-07 failure handling specifically to the `except OSError` branch, which is the realistic failure mode and is the one driven through a real `os.replace` failure in testing). They are legitimate gaps worth tracking, not reasons to fail this phase:

- **WR-02 (review):** On htmx, only the `OSError`-during-write path reaches the row's friendly message. A non-`OSError` exception from the writer (e.g. a hypothetical TOML serialization failure) would propagate as a bare 500, which htmx would not swap (user sees nothing), and a direct POST would get a generic "Internal Server Error" rather than the D-05 sentence. This requires a writer failure mode other than disk/permission/IO errors, which is not realistically reachable for already-validated Settings data. Also: the pre-existing "already removed by a concurrent request" 400 is not swapped into the row on htmx either (stale row stays), but this is a not-found conflict, not a save failure, and predates this phase.
- **WR-01 (review):** An unreadable (not merely malformed) state file is still described by the shared warning as having "held" bad content, and its set-aside copy also fails for the same reason it couldn't be read -- so D-08's "set aside first" promise doesn't fully hold on that path. This is the pre-existing `OSError`-on-read path, not the valid-JSON-non-object case CONSIST-03 is scoped to.
- **IN-01 (review):** The `.remove-error` span has no `data-stop-propagation`, so clicking/selecting the error text collapses the instance's `<details>` row (see Human Verification above).

Recommend these be added to `.planning/backlog/MAINTENANCE.md` or a follow-up quick task; none block this phase's goal.

### Human Verification Required

See YAML frontmatter `human_verification` list. Summary: the row-local error-display flow (D-04/D-06), its interaction with unsaved form state elsewhere on the page, the IN-01 click-collapse quirk, and `aria-live` screen-reader behavior were never exercised in a real browser for this phase -- only proven at the HTTP-response and static-template level. The underlying htmx wiring (`hx-target`/`hx-swap` attributes, response status/body) is verified and correct by inspection, but per this verification's scope, visual/interactive browser behavior is flagged for a human rather than assumed.

### Gaps Summary

No blocking gaps. All three roadmap success criteria are independently verified against the actual codebase (not just SUMMARY claims): real filesystem/writer failures were injected and observed to leave live state untouched and to produce the exact fixed user-facing message; real non-object JSON files were loaded and observed to recover to defaults with a kept diagnostic copy and no crash. The full test suite (3310 passed, 1 pre-existing skip) and lint pass cleanly on the current head. The only open items are (a) two minor, already-reviewer-flagged edge cases (WR-01, WR-02) that fall outside the literal, tested scope of CONSIST-02/03 and are recommended for backlog, and (b) browser-only UI/interaction checks that no one has yet run, listed under Human Verification.

---

*Verified: 2026-11-15T23:40:33Z*
*Verifier: Claude (bm-verifier)*
