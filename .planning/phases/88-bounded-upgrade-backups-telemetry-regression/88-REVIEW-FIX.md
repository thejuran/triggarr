---
phase: 88-bounded-upgrade-backups-telemetry-regression
fixed_at: 2026-11-17T03:35:00Z
review_path: .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-REVIEW.md
iteration: 2
findings_in_scope: 4
fixed: 4
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 88: Code Review Fix Report

**Fixed at:** 2026-11-17T03:35:00Z
**Source review:** .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-REVIEW.md (re-review of `fbc812eb`)
**Paired Codex finding:** codex:e5fcc401380b:a1:F001 (fixed together with WR-01, per owner decision 2026-11-17)
**Iteration:** 2 (the round 1 report is in git history)

**Summary:**
- Findings in scope: 4 (WR-01 + Codex F001 as one fix, IN-01, IN-02, IN-03)
- Fixed: 4
- Skipped: 0
- Rejected: 0

Out of scope by owner decision: IN-04 / D-06 (retry copies left after a successful upgrade stay; this is in the backlog) and CV-01 (convention-checker false positive). Neither was touched.

Verification after all fixes, on head `f0d60ffe`:
- `uv run pytest tests/ -x -q` gives 3351 passed, 1 skipped, 38 warnings. Round 1 had 3347 passed; the 4 extra are the new tests below.
- `uv run ruff check triggarr/ tests/` gives "All checks passed!".

## Fixed Issues

### WR-01 + Codex F001: Pruning ran only after a successful copy, and abandoned `.partial` files were never reclaimed

**Files modified:** `triggarr/db.py`, `tests/test_db.py`
**Commit:** 54c67a12
**Status:** fixed: requires human verification. This changes the order of operations in the backup step.
**Applied fix:** On the retry-backup path in `run_migrations`, two steps now run before the new timestamped copy is made:
1. A new helper, `_remove_abandoned_partial_backups`, deletes staging files for the same version. It only matches names of the exact form `<db>.v{current}-backup-<stamp>.partial`, where the stamp fully matches the timestamp pattern. Other versions and other names (for example a user's own `...-backup-mycopy.partial`) are never touched.
2. `_prune_timestamped_backups(..., just_written=None)` trims timestamped copies down to 2, so the total is at most 3 once the new copy lands.

A short code comment states the assumption behind this: Triggarr is a single process and this runs at startup before serving, so no other copy can be in progress. Listing or deletion failures in either step log a WARNING and never block startup. The canonical `.v{current}-backup` file cannot match either pattern and is never touched. `.partial` files are still never counted among the 3 valid backups.

**Post-copy prune kept, not removed.** The two orders are not equivalent in one case. If a deletion fails before the copy but works on the next try, the post-copy prune is what still brings the total back to 3. In the normal case it deletes nothing. The cost: when a deletion fails every time, that file gets a second WARNING on the same startup.

**Tests**
Three new tests:
- `test_retry_backup_fits_on_full_disk_after_pre_copy_cleanup`: a simulated disk only has room for 3 retry-backup files. It starts with the canonical backup, 3 good copies and 2 abandoned partials. Startup proceeds to schema v10, the partials are reclaimed, and the 2 newest good copies plus the new one remain.
- `test_restart_reclaims_abandoned_partials_and_keeps_newest_backups`: 3 abandoned partials are seeded, one with a stamp that sorts newest, plus look-alike decoys. After a crash-loop restart the partials are gone, the decoys are untouched, the 2 newest good copies plus the new one remain, and the canonical backup is byte-identical.
- `test_stale_partial_removal_failure_logs_warning_and_does_not_block`: deleting an abandoned partial fails. Exactly one WARNING names the file and the reason, there is no ERROR, the new backup is still written, and the migration reaches v10.

One existing test changed. The first half of `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups` now expects the 2 newest good copies after a failed copy, because the oldest is now pruned before the copy. This is the outcome the review asked for: "exactly 2 good copies and the canonical backup remain".

**RED evidence:** I ran these tests against the pre-fix `triggarr/db.py` from HEAD `03305e99`, and all 4 failed:
- The full-disk test raised `OSError: [Errno 28] No space left on device`.
- The restart test failed with "Abandoned staging file ... must be reclaimed".
- The warning test failed with "Expected exactly 1 WARNING line, got: ''".
- The updated WR-01 test still had all 3 good copies.

All 4 pass with the fix.

### IN-01: The README overstated when the FastAPI warning appears and what it says

**Files modified:** `README.md`
**Commit:** dd568c17
**Applied fix:** The sentence now says the warning appears only when `FASTAPI_OTEL_AUTO_CONFIGURE=true` is set together with an OTLP endpoint, and that the rest of its text depends on the exporter and protocol settings. It still says the warning is harmless and that any OpenTelemetry extra it suggests is not supported. It now says unsetting `FASTAPI_OTEL_AUTO_CONFIGURE` silences it.

### IN-02: The telemetry regression test depended on the runner's OTEL environment

**Files modified:** `tests/test_telemetry.py`
**Commit:** 26899ae4
**Applied fix:** Before setting its own variables, the test now clears every variable that could skip or change the auto-configure path, using `monkeypatch.delenv(..., raising=False)`:
- `OTEL_SDK_DISABLED`
- `OTEL_EXPORTER_OTLP_PROTOCOL`
- for each of TRACES, METRICS and LOGS: `OTEL_{signal}_EXPORTER`, `OTEL_EXPORTER_OTLP_{signal}_ENDPOINT` and `OTEL_EXPORTER_OTLP_{signal}_PROTOCOL`

I took this list from the installed FastAPI telemetry runtime. The per-signal protocol variable was not in the review's list; I found it in the source and added it.

**Verified:** I ran the test with `OTEL_SDK_DISABLED=true` and all three `OTEL_*_EXPORTER=none` set in the shell:
- The fixed test passes.
- The HEAD version of the test fails with only `OTEL_SDK_DISABLED=true` set.

### IN-03: The cleanup-failure branch had no test, and the stale-`.partial` check did not guard any fix

**Files modified:** `tests/test_db.py`
**Commit:** f0d60ffe
**Applied fix:**
- **New test `test_failed_partial_cleanup_logs_warning_and_reraises_copy_error`:** `shutil.copy2` writes bytes and then raises ENOSPC, and `Path.unlink` raises `PermissionError` for `.partial` names. The test asserts three things:
  - the raised error has `errno == 28` and is not a `PermissionError`;
  - the staging file that could not be deleted is still on disk;
  - exactly one WARNING contains "Could not remove incomplete retry backup", the file name and `PermissionError`.
- **Stronger stale-partial check:** the second half of `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups` now also asserts that the abandoned 2099-stamped `.partial` is reclaimed. Its comment was updated to match.

**Guard evidence:** both tests were checked against deliberately broken versions of the code (mutation checks); the code was restored afterwards.
- The new test guards behaviour that was already correct, so it passes on the pre-fix code. To show it guards anything, I changed the code to re-raise the cleanup error (the refactor the review warned about). The test then failed with "The cleanup error must not replace the copy error".
- I removed the `_remove_abandoned_partial_backups` call. The stale-partial check then failed with "The abandoned staging file must be reclaimed", and no other assertion in the test failed.
- On the code before this round, the same test also fails, as shown in the RED evidence above.

---

_Fixed: 2026-11-17T03:35:00Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 2_
