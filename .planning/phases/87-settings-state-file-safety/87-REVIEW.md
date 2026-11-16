---
phase: 87-settings-state-file-safety
reviewed: 2026-11-16T02:58:00Z
depth: standard
iteration: 5
head: e90f8cef
files_reviewed: 2
files_reviewed_list:
  - triggarr/web/routes.py
  - tests/test_web.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 87: Code Review Report (iteration 5, review after the general-only Save fix)

**Reviewed:** 2026-11-16T02:58:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (info only: no critical, no warning)
**Head reviewed:** `e90f8cef` (only code change since iteration 4 head `0cb0f12e` is commit `7a92e735`; diff base `821c8922`; phase base `3cede400`)

The reports for iterations 1 to 4 (heads `6262dd14`, `f099c6a8`, `615a044a`, `0cb0f12e`) are in git history for this file.

## Summary

This is a review of commit `7a92e735` (`git show 7a92e735 -- triggarr tests`) against the code itself. Everything else between `0cb0f12e` and `e90f8cef` is planning markdown (`git diff --stat 0cb0f12e..HEAD -- triggarr tests` shows only the two reviewed files).

**This iteration has no critical and no warning finding.** Under the owner's stopping rule there is nothing to fix. One info item is listed for the backlog, and two items are set aside for an owner ruling (one new observation about code this commit did not change, one carried from iteration 2).

The fix is real. With a removal's settings write in progress, a Save that carries only general settings waits for the lock, then builds its configuration from the settings as they are after the removal. The removed instance is absent from the settings file, live settings, the client registry and the scheduler. The reverse overlap with Add Instance keeps the added instance, in both orders.

### Fix verification

| Check | Result |
|---|---|
| General-only Save queued behind a removal's write does not bring the instance back | Holds. `test_general_settings_save_during_removal_write_does_not_resurrect_removed` (`tests/test_web.py:1755`) passes at head: instance absent from the file, live settings and client registry; its client closed exactly once; no scheduler call for its job. |
| The test fails on the pre-fix code | Yes. The head test file was run against an exported copy of `7a92e735^`: it fails at `assert "4K" not in on_disk["radarr"]` (the removed instance is back in the file). The neighbouring Add Instance test passes there, as expected. |
| The same overlap with the settings class reading the app's own settings file, as it does in production | Holds. Tests use a settings file path the settings class does not read; in production they are the same file (see SA-01). Probed with both pointed at one file: the removed instance stays absent from the file, live settings and client registry. |
| General-only Save queued behind an Add Instance write keeps the added instance | Holds (probed). File and live settings contain all three instances; the id Add Instance generated is the id the Save kept; the state entry exists. |
| Add Instance queued behind a general-only Save's write | Holds (probed). Both the new general setting and the added instance are in the file and live settings. |
| Other instances after the overlap | Unchanged (probed): ids, API keys and tags of the remaining instances are the same in the file and live settings; the unchanged instance's client was neither rebuilt nor closed. |

### Review of commit `7a92e735`

| Check | Result |
|---|---|
| `_settings_from_form` against the code it replaced | Equivalent. The body (`triggarr/web/routes.py:645-721`) is the old code moved without edits: every general field, the form-key parsing, both instance branches, API-key preservation as a `SecretStr`, id preservation (`current_cfg.id` or a new id), and validation before any write. The only edits are the two rejection exits, which now return `None` instead of the redirect. |
| Rejection exits | Same response as before. `save_settings` turns `None` into the same 303 redirect (`:741-742`). Probed with an invalid URL and with a validation failure (six instances): 303, live settings object unchanged, no settings file written, one warning each. |
| Lock released on the early return | Yes. The return is inside `async with` (`:738-742`), which releases on exit. Probed: the lock is free after each rejected Save, and a following Save succeeds. |
| No gap between the read and the write | Holds. There is no `await` between taking the lock, reading live settings (`:739`), building the configuration (`:740`) and starting the write (`:745`), so no other request can run in between. Every other settings writer takes the same lock. |
| Anything new under the lock that can block or deadlock | Nothing that waits on another lock or on the network. `validate_arr_url` does no DNS lookup. The helper is synchronous and takes no lock, so it cannot deadlock. Two things that already ran on the event loop now run while the lock is held: the log lines for a rejection, and the settings-file read that building the settings object performs (SA-01). Both are short and were on the event loop before the change. The one user-visible effect is IN-01. |
| Post-save comparisons use the under-lock snapshot | Correct, and more accurate than before. Client rebuild (`:763`, `:789-795`) and tag-cache invalidation (`:846-858`) compare the new settings with the settings read under the lock (`:739`), so they no longer compare against a snapshot that another request may have replaced. Scheduler handling depends only on the new settings and the client registry. After a removal the instance is in neither, so nothing is recreated for it. |
| API keys | Handling unchanged. Keys stay `SecretStr` until `_settings_to_dict`; nothing new is logged. |
| Lock audit | `tests/audit_lock_coverage.py`: covered 8 / 8. |

### New test: reliability

- **Ordering is forced, not timed.** The removal's writer is held on an event; the Save is started only after the writer is running; the test then waits until exactly one request is queued on the lock and asserts that before releasing the writer. If the Save ran without queuing, the test fails rather than passing wrongly.
- **Cleanup.** The release event is set in `finally`, and the gated writer gives up after 10 seconds, so a failed assertion cannot leave a worker thread waiting.
- **Waits are condition-based** with a 10 second limit, not fixed sleeps.
- **Repeat runs:** 15 runs in a row, no failure.
- It waits on the private `asyncio.Lock._waiters` attribute, like the other overlap tests. That is the existing backlog item IN-03 (fails loudly if the attribute changes; cannot pass wrongly).
- The scheduler in this fixture is a mock that reports every job as existing, so the test's scheduler assertion proves "no job was rescheduled or added for the removed instance". That is the relevant check for this defect.

### Checks run during this review (from the checkout, without writing to it)

- `pytest tests/` (full suite): 3331 passed, 1 skipped.
- `ruff check triggarr/ tests/`: all checks passed.
- Convention pack (`verify conventions --check`) on the two files: no findings (not skipped).
- Head `tests/test_web.py` against an exported copy of `7a92e735^`: the new test fails, for the reason above.
- A throwaway probe file outside the repo (7 cases, all passed): both orders of Add Instance against a general-only Save, the removal overlap with ids/keys/clients checked, the removal overlap in the production file arrangement, both rejection exits, the lock wait in IN-01, and the form-omission case in SA-01.

Not verified: nothing was exercised in a browser. `triggarr/config.py`, `triggarr/state.py` and the templates are unchanged since iteration 4 and were not re-reviewed. The items the owner ruled on (the full-form case, request cancellation during a write, the late write in other routes, the two missing tests) were not re-examined.

## Earlier-iteration dispositions

| Finding | Disposition | Verified | Notes |
|---|---|---|---|
| Iteration 4 IN-01: the "write already running" test allows 100 ms for the request to reach the write | Backlog | Yes (entry exists) | Recorded in `.planning/backlog/MAINTENANCE.md`. Test unchanged. |
| Iteration 4 IN-02: the mock-based test still describes the failure as "the write never starts" | Backlog | Yes (entry exists) | Recorded in `.planning/backlog/MAINTENANCE.md`. Test unchanged. |
| Codex F001 at `0cb0f12e`: a removal cancelled after its write started lets the write finish without live state being updated | Backlog by owner | Yes (entry exists) | Recorded in `.planning/backlog/MAINTENANCE.md` (fix once for all settings routes). Not re-examined. |
| Deep-review Warning: a general-only Save overlapping a removal resurrects the removed instance | Fixed in `7a92e735` | Yes | `triggarr/web/routes.py:637-742`. Regression test fails before the fix and passes after; also holds in the production file arrangement. See the tables above. |

## Narrative Findings (AI reviewer)

## Info

### IN-01: A rejected Save now waits for a running search before answering

**File:** `triggarr/web/routes.py:738-742`
**Issue:** The URL check and the settings validation moved inside the lock, so a Save that is going to be rejected (invalid instance URL, or settings that fail validation) is answered only once the lock is free. Before `7a92e735` it was answered at once. Measured: with the lock held, the rejected Save was still unanswered after 300 ms and returned its 303 as soon as the lock was released. A Save that succeeds has always waited for the lock, so the only change is how long a rejected one takes while a search cycle or another settings change is running. Nothing is lost or written. This is the same cost as iteration 3 IN-01 for Add Instance, and it is the price of reading settings under the lock.
**Fix:** None needed for correctness. If the delay matters, check the submitted URLs before taking the lock (that check does not depend on current settings) and keep the build and validation inside it.

## Set aside (needs ruling)

### SA-01: In production, a Save whose form leaves an instance out does not delete it; the tests pin the opposite

**Where:** `triggarr/web/routes.py:718` (`SettingsModel(**new_config)`), `triggarr/models/config.py:194-196` and `:227-239`
**Why excluded:** Not changed by `7a92e735` (the line was moved, not edited) and it predates Phase 87. It concerns the full-form Save behavior the owner has already placed in the backlog, so it is raised as a fact that affects that backlog item rather than as a finding of this iteration.
**What was observed:** Building the settings object reads the settings file as a second source and merges it underneath the submitted values. In production that file is the app's own settings file (`triggarr/__main__.py:53` and the class default are the same path). Probed with both pointed at one file: a Save whose form carried fields for only one of two Radarr instances left both instances in the file and in live settings. In the test suite the two paths differ, so `test_save_settings_form_removal_invalidates_tag_cache` (`tests/test_web.py:3884`) pins a deletion that production does not perform.
**Effect if left as is:** For a user, a Save from a stale page keeps an instance that was added elsewhere instead of deleting it, which is the safer outcome. The cost is accuracy: the backlog entry "Settings read before search_lock" describes Save as deleting an instance absent from the form, and the proposed follow-up design is written against that. The same merge is also what carries the sign-in settings through a Save, and it is a file read on the event loop, now inside the lock.
**Needs:** A ruling from the owner: correct the backlog entry's description and take this into the follow-up design (suggested), or accept as is. No change is suggested for this phase.

### SA-02: A failure closing the directory handle after the file was replaced is reported as a failed save

**Where:** `triggarr/config.py:207-208` (`_atomic_toml_write`, the `finally` that closes the directory handle)
**Why excluded:** Carried from iteration 2 SA-02. `triggarr/config.py` is unchanged in this iteration and the behavior predates Phase 87. The backlog entry still reads "no owner ruling yet".
**Effect if left as is:** If closing the directory handle fails after the settings file was already replaced, the writer raises. Remove Instance then tells the user the instance was not removed although the file no longer has it, and Save Settings or Add Instance fail with the file changed and the running app not updated, until a restart. Very unlikely; found by reading, not reproduced.
**Needs:** A ruling from the owner: fix (treat a close failure after the replace as a warning, like the directory-sync failure next to it), or backlog.

---

_Reviewed: 2026-11-16T02:58:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
