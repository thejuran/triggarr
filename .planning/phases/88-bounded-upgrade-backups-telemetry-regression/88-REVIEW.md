---
phase: 88-bounded-upgrade-backups-telemetry-regression
reviewed: 2026-11-17T03:37:54Z
reviewed_head: 91eef365b0cc5afd90a2b12b6df6ee4dd02cccbd
diff_base: a1b4b65c
depth: standard
files_reviewed: 4
files_reviewed_list:
  - README.md
  - tests/test_db.py
  - tests/test_telemetry.py
  - triggarr/db.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 88: Code Review Report (re-review after fix round 2, final round)

**Reviewed:** 2026-11-17T03:37:54Z
**Reviewed head:** `91eef365b0cc5afd90a2b12b6df6ee4dd02cccbd`
**Diff range:** `a1b4b65c..91eef365` (round-2 fix commits `54c67a12`, `dd568c17`, `26899ae4`, `f0d60ffe` read closely)
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found (Info only; no Critical or Warning)

## Summary

This re-review covers the whole Phase 88 diff after the second fix round. The phase:
- caps timestamped pre-upgrade retry backups at 3 per schema version;
- writes each retry backup to a `.partial` file and renames it into place;
- now (round 2) clears abandoned `.partial` files and prunes to 2 retry copies **before** the new copy, so the peak disk use is canonical + 3 and a disk that is full of old retry copies no longer blocks startup;
- pins startup against FastAPI's OpenTelemetry auto-configure variables and documents it in the README.

I traced the round-2 changes for correctness:
- **Pre-copy prune** (`triggarr/db.py:338-339`) keeps the 2 newest copies by file-name stamp (`candidates[2:]` deleted). After the copy, the post-copy prune (`db.py:367`) excludes the new file and keeps 2 others, so it deletes nothing in the normal case. The total is canonical + 3 after a successful copy, and canonical + 2 if the copy fails. A copy that keeps failing does not erode backups further: every restart prunes to 2, which is a no-op after the first.
- **Abandoned-partial cleanup** (`db.py:249-291`) only matches `<stem>.v{current}-backup-<stamp>.partial` with an exact ASCII stamp. Other versions, user-named look-alikes and the canonical backup cannot match. Listing and deletion errors are logged at WARNING and never raised.
- **Copy-failure cleanup** (`db.py:346-358`) still re-raises the original copy error. The new test proves the cleanup error does not replace it.
- **Clock rollback**: if the clock moves backwards, the newest real copy gets an older stamp and is pruned on the next attempt in favour of future-dated copies. This was already true before round 2. During a crash loop the database does not change between attempts (v10 is atomic), so all retry copies hold the same data. No user harm, so not a finding.

The README now limits the warning claim to "auto-configure plus an OTLP endpoint" and no longer quotes text that depends on the settings. That matches FastAPI 0.162.4 (`fastapi/telemetry/_runtime.py`): with no endpoint nothing is requested, and `OTEL_SDK_DISABLED=true` returns early. The lockfile has `opentelemetry-api` only (pulled in by FastAPI), with no SDK or OTLP exporter, so "nothing is exported" holds. The telemetry test now clears every OTEL variable the runtime reads, including the per-signal protocol variables.

Checks on this head:
- full suite `uv run pytest tests/ -x -q`: 3351 passed, 1 skipped
- `uv run ruff check triggarr/ tests/`: clean
- convention checker: only the known README casing false positive (CV-01)

What remains is two Info items: an assumption that only one process runs, which F001 asked to enforce and the code only documents, and a log line that overstates what is kept in the pre-copy prune. Neither harms a user on a supported deployment. Both can go to the backlog under the stopping rule.

## Original vs. refreshed findings

| Prior ID | Prior title (short) | Status at `91eef365` | Evidence |
|---|---|---|---|
| WR-01 | Pruning runs only after a successful copy, so a full disk blocks startup | **Fixed** | `54c67a12`: `_remove_abandoned_partial_backups` and `_prune_timestamped_backups(..., None)` now run before the copy (`triggarr/db.py:338-339`). `test_retry_backup_fits_on_full_disk_after_pre_copy_cleanup` simulates a disk with room for 3 retry files and proves startup reaches v10. The updated `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups` proves the canonical backup plus the 2 newest copies remain after a failed copy. That is the outcome the round-2 fix asked for. |
| Codex F001 | Abandoned `.partial` files pile up outside the cap | **Fixed**, with a residual noted as new IN-01 | `54c67a12`: abandoned partials for the current version are deleted at startup before the copy. `test_restart_reclaims_abandoned_partials_and_keeps_newest_backups` covers reclamation and decoys. `test_stale_partial_removal_failure_logs_warning_and_does_not_block` covers a failed deletion. F001 also asked for "ownership/locking sufficient to avoid deleting an active concurrent copy". The fix documents a single-process assumption instead of enforcing it (new IN-01). |
| IN-01 | README overstates when the FastAPI warning appears | **Fixed** | `dd568c17` (`README.md:215`): the warning is tied to auto-configure plus an OTLP endpoint, and the text is described as depending on exporter and protocol settings. This matches the FastAPI 0.162.4 source. |
| IN-02 | Telemetry test depends on runner OTEL env | **Fixed** | `26899ae4` (`tests/test_telemetry.py:27-36`) clears `OTEL_SDK_DISABLED`, `OTEL_EXPORTER_OTLP_PROTOCOL`, and the per-signal exporter, endpoint and protocol variables. |
| IN-03 | Cleanup-failure branch untested; stale-partial check did not guard the fix | **Fixed** | `f0d60ffe`: `test_failed_partial_cleanup_logs_warning_and_reraises_copy_error` asserts errno 28 survives, the `.partial` that could not be deleted is still on disk, and exactly one WARNING names it. The stale-partial half of the WR-01 test now asserts reclamation, which only the new code passes. |
| IN-04 | Retry backups never cleaned after a successful upgrade | **Carried forward, accepted by owner ruling (D-06)** (not counted) | Unchanged by design. In the backlog together with leftover `.partial` files for versions that are no longer current. |
| CV-01 | README file-name casing (tool output) | **False positive** (not counted) | The checker emitted it again at this head. `README.md` is a fixed universal name. |

## Narrative Findings (AI reviewer)

## Info

### IN-01: The "only one process" safety assumption behind partial-file cleanup is documented, not enforced

**File:** `triggarr/db.py:249-260`, `triggarr/db.py:332-339`
**Issue:** Codex F001 asked for reclamation "with ownership/locking sufficient to avoid deleting an active concurrent copy". The fix relies instead on a comment: Triggarr is a single process, and this runs at startup before serving. Nothing enforces that. There is no lock file or instance guard (checked `triggarr/__main__.py`).

If two containers are pointed at the same config volume and both start while the schema upgrade is crash-looping, instance B deletes instance A's in-progress `<...>.partial`. A's `partial_path.replace(...)` then raises `FileNotFoundError`, and A's startup fails until its next restart. No valid backup is lost: the canonical backup is never touched, and B still holds its own copies.

That deployment is unsupported, and it already risks SQLite contention. So this is a robustness note, not a defect a user on a supported setup would hit.
**Fix (backlog):** Either record the single-instance requirement in the README deployment notes, or skip `.partial` files modified in the last few minutes (`entry.stat().st_mtime > time.time() - 300`) so an active copy is never reclaimed. The second option needs no locking and keeps F001's reclamation for genuinely abandoned files.

### IN-02: The pre-copy prune logs "keeping ... the 3 most recent" while it keeps 2

**File:** `triggarr/db.py:236-240` (called from `db.py:339`)
**Issue:** `_prune_timestamped_backups` always logs "Removed old retry backup {path}; keeping the original backup and the 3 most recent". When it is called before the copy (`just_written=None`), it keeps 2 copies, and the third only appears if the copy succeeds. If the copy then fails (for example ENOSPC), the log says 3 copies are kept when only 2 are on disk. That could mislead an operator who is counting backups while recovering from a failed upgrade.

A related point is already acknowledged in the fix report: if a deletion fails every time, the same file gets two WARNING lines on one startup (pre-copy and post-copy prune). It is noisy but accurate.
**Fix (backlog):** Pass the number kept into the message, for example `n=_MAX_RETAINED_TIMESTAMPED_BACKUPS - (1 if just_written is None else 0)`, with wording such as "keeping the original backup and the {n} most recent retry backups".

## Conventions

### CV-01: README file-name casing (tool output, false positive; not counted)

**File:** `README.md:1`
**Deviation:** At this head, `verify conventions --check` reports "file name casing is CONSTANT (README)".
**Convention:** file-name-casing should be camel (derived).
**Fix:** None. `README.md` is a fixed, universal name, so the rule pack is wrong here. This is advisory only and does not count toward the totals.

## Set aside (needs ruling)

### SA-01: A retry-backup copy failure blocks startup even though the canonical backup already exists

**Where:** `triggarr/db.py:346-358`
**Why excluded:** This behaviour existed before the phase. The phase scope (BKUP-01/02) is bounding the number of backups, not deciding whether a failed second backup should abort the upgrade. Round 2 already shrank the case: the pre-copy prune frees the room held by old retry copies.
**Effect if left as is:** If the disk cannot hold even one more database copy after pruning to 2, every start fails with ENOSPC until the user frees space by hand. This happens even though the earliest pre-upgrade backup (the canonical file) is already safe on disk, and even after a release that fixes the migration.
**Needs:** Owner ruling: accept (fail loudly and keep the current behaviour), or backlog "continue without a retry backup when the canonical backup exists and the retry copy fails with ENOSPC, logging a WARNING".

The prior SA-01 (cleanup after a successful upgrade) remains resolved by the D-06 ruling and is not raised again.

---

_Reviewed: 2026-11-17T03:37:54Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Head: 91eef365b0cc5afd90a2b12b6df6ee4dd02cccbd_
