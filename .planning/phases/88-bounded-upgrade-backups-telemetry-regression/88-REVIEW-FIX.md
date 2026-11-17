---
phase: 88-bounded-upgrade-backups-telemetry-regression
fixed_at: 2026-11-16T00:00:00Z
review_path: .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 5
skipped: 1
rejected: 0
status: partial
---

# Phase 88: Code Review Fix Report

**Fixed at:** 2026-11-16T00:00:00Z
**Source review:** .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (WR-01, WR-02, IN-01, IN-02, IN-03, IN-04)
- Fixed: 5
- Skipped: 1 (IN-04, by design)
- Rejected: 0

CV-01 is a convention-checker false positive that the review itself excludes from the totals. It is recorded under Skipped Issues for completeness and is not counted. SA-01 (owner ruling) was not touched.

Verification after all fixes: `uv run pytest tests/ -x -q` gives 3347 passed, 1 skipped. `uv run ruff check triggarr/ tests/` gives "All checks passed!".

## Fixed Issues

### WR-01: A truncated retry backup from a failed copy is kept as one of the "3 most recent"

**Files modified:** `triggarr/db.py`, `tests/test_db.py`
**Commit:** 6e94aaea
**Applied fix:** The timestamped retry backup is now written to `<name>-backup-<stamp>.partial` and then renamed into place (write-then-rename, matching the project convention). The `.partial` name can never fully match the stamp pattern, so a failed or interrupted copy is never a pruning candidate and never counts toward the 3 retained backups. If the copy or rename fails, the temporary file is removed. A failure to remove it is logged at WARNING, and the original error is still raised. Cleanup runs only on the failure path, so the success path makes no extra delete call.
New test `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups`:
- simulates a disk-full copy that writes a few bytes and then raises ENOSPC;
- checks that no new backup-named file is left;
- plants a stale `.partial` file with a newer stamp and checks that the next attempt still keeps the newest good backups and does not count the stale file.

I confirmed the test fails without the fix and passes with it.
**Not done (optional in the review):** pruning to N-1 before the copy to lower peak disk use. Peak use during an attempt is still the canonical backup plus 4 timestamped copies, briefly. A stale `.partial` from a hard kill in the middle of a copy is not deleted automatically. It is inert, but it does take disk space.

### WR-02: The telemetry regression test cannot tell whether the auto-configure path was exercised

**Files modified:** `tests/test_telemetry.py`
**Commit:** 621aebb0
**Applied fix:** The test captures the `fastapi` logger at WARNING and asserts that "automatic telemetry configuration failed" was logged. This proves the auto-configure path ran and its failure was absorbed. I checked it against a copy with the environment variable renamed: that copy fails. The private `_telemetry` assertion was left out because the log assertion alone proves the path ran.
**Not done:** the test still builds its own `FastAPI(...)` rather than the production construction in `triggarr/__main__.py`. Covering production would require refactoring app construction into a reusable function, which is out of scope for a minimal fix.

### IN-01: The stamp regex accepts non-ASCII digits

**Files modified:** `triggarr/db.py`, `tests/test_db.py`
**Commit:** 579d734e
**Applied fix:** `_BACKUP_STAMP_RE` is now `[0-9]{8}T[0-9]{12}Z`. Added an Arabic-Indic-digit decoy to `test_prune_ignores_other_versions_and_non_matching_names`. I confirmed the test fails with the old `\d` pattern.

### IN-02: The end-to-end pruning-failure test accepts any WARNING

**Files modified:** `tests/test_db.py`
**Commit:** 6387334c
**Applied fix:** The test now requires a WARNING line that contains "Could not remove old retry backup".

### IN-03: The README does not mention the warning operators will see

**Files modified:** `README.md`
**Commit:** d7cc03a2
**Applied fix:** Added that `FASTAPI_OTEL_AUTO_CONFIGURE=true` makes FastAPI log a one-time startup warning suggesting an OpenTelemetry extra. The README now says the warning is harmless, the extra is not supported, and unsetting the variable silences it.

## Skipped Issues

### IN-04: Retry backups for already-completed upgrades are never cleaned up

**File:** `triggarr/db.py:285`
**Reason:** By design under locked decision D-06. The owner ruling on SA-01 is pending, so no change was made.
**Original issue:** Pruning runs only for the current version on the retry path, so after a crash loop that ends in success, up to 3 retry copies for that version remain indefinitely.

### CV-01: README file-name casing (not counted)

**File:** `README.md:1`
**Reason:** A recorded false positive. `README.md` is a universal fixed name. The review excludes it from the totals.
**Original issue:** The convention checker reports CONSTANT casing against a derived camel file-name convention.

---

_Fixed: 2026-11-16T00:00:00Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
