---
phase: 88-bounded-upgrade-backups-telemetry-regression
reviewed: 2026-11-17T04:23:15Z
reviewed_head: d3edc849ebda0f73bb4fd32201d5a7db8d7ae62a
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

# Phase 88: Code Review Report (review of PR head d3edc849)

**Reviewed:** 2026-11-17T04:23:15Z
**Reviewed head:** `d3edc849ebda0f73bb4fd32201d5a7db8d7ae62a`
**Diff range:** `a1b4b65c..d3edc849`
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found (Info only; no Critical or Warning)

## Summary

`git diff --stat 91eef365..d3edc849 -- README.md tests/ triggarr/` is empty. Every commit after the round-3 head (`9018a341` through `d3edc849`) touches only `.planning/` files. The four files in scope are byte-identical to the round-3 head. I still re-read the whole phase diff (`a1b4b65c..d3edc849`) and re-checked each earlier finding against the current code instead of copying it.

What I re-traced in `triggarr/db.py`:
- **Order of the retry-backup steps** (`db.py:332-367`): abandoned partials are removed, then the timestamped copies are pruned to 2, then the copy is written to `.partial` and renamed into place, then a post-copy prune runs. The total is canonical + 3 after a successful copy and canonical + 2 after a failed one. A copy that keeps failing does not keep deleting backups.
- **Name matching** in both helpers needs the exact `<stem>.v{current}-backup-` prefix and a full ASCII stamp match. The canonical backup, other schema versions and user-named look-alikes cannot match. `entry == just_written` compares paths built from the same parent, so the new copy is reliably excluded.
- **Error handling**: listing and deletion failures log a WARNING and continue. A copy failure re-raises the original error even when cleanup of the partial file fails, and the cleanup error is logged.
- **Telemetry test** (`tests/test_telemetry.py`): sets the env before `FastAPI()` is built, clears the runner's OTEL variables, and asserts on the warning text. The owner chose to keep that wording check (D-12), so it is not raised again.
- **README** (`README.md:215`): matches what the FastAPI telemetry runtime does, as verified in round 3. Nothing has changed since.

Checks on this head:
- `uv run pytest tests/test_db.py tests/test_telemetry.py -q`: 122 passed
- `uv run ruff check triggarr/ tests/`: All checks passed

No new defects found. The two round-3 Info items are still in the code unchanged. They are carried forward below so this report stays truthful about the head, and both are already in the backlog (`.planning/backlog/MAINTENANCE.md:34`, owner stopping rule 2026-11-17). Neither is a new request for a fix in this phase.

Not raised again, by owner ruling: IN-04/D-06 (retry copies left after a successful upgrade; backlog `MAINTENANCE.md:32`) and CV-01 (the convention checker's README casing false positive).

## Original vs. refreshed findings

| Prior ID (round 3, `91eef365`) | Status at `d3edc849` | Evidence |
|---|---|---|
| IN-01 single-process assumption documented, not enforced | **Still present, backlogged** (carried as IN-01) | `db.py:260-264` and `db.py:333-337` unchanged; no lock or instance guard added. |
| IN-02 pre-copy prune log says "3 most recent" | **Still present, backlogged** (carried as IN-02) | `db.py:236-240` still logs `n=_MAX_RETAINED_TIMESTAMPED_BACKUPS` on both the pre-copy and post-copy calls. |
| SA-01 disk-full retry copy blocks startup | **Ruled: backlogged** (not counted, not set aside again) | `MAINTENANCE.md:33`. |
| IN-04 / D-06, CV-01 | **Out of scope by owner ruling** (not counted) | As instructed. |

## Narrative Findings (AI reviewer)

## Info

### IN-01: The "only one process" safety assumption behind partial-file cleanup is documented, not enforced (carried forward; backlogged)

**File:** `triggarr/db.py:249-264`, `triggarr/db.py:332-339`
**Issue:** `_remove_abandoned_partial_backups` deletes every `.partial` file for the current version, whatever its age. The only thing that makes this safe is a comment saying Triggarr is a single process. If two instances share one config volume and both start during a failed-upgrade crash loop, one can delete the other's in-progress `.partial`. The other then fails at `partial_path.replace(...)` with `FileNotFoundError` and must restart. No valid backup is lost, because the canonical backup is never touched. That deployment is unsupported.
**Fix (backlog):** Skip `.partial` files modified in the last few minutes, for example `if entry.stat().st_mtime > time.time() - 300: continue`, or record the single-instance requirement in the README deployment notes.

### IN-02: The pre-copy prune log says "the 3 most recent" while it keeps 2 (carried forward; backlogged)

**File:** `triggarr/db.py:236-240` (called with `just_written=None` from `db.py:339`)
**Issue:** The INFO line always reports `n=_MAX_RETAINED_TIMESTAMPED_BACKUPS` (3). Before the copy, the prune keeps 2 copies. If the copy then fails (for example a full disk), the log says 3 are kept while only 2 are on disk. That can mislead an operator who is counting backups during recovery.
**Fix (backlog):** Pass the number actually kept:
```python
kept = _MAX_RETAINED_TIMESTAMPED_BACKUPS - 1
...
logger.info(
    "Removed old retry backup {path}; keeping the original backup and the {n} most recent retry backups",
    path=stale_path,
    n=kept if just_written is None else _MAX_RETAINED_TIMESTAMPED_BACKUPS,
)
```

## Set aside (needs ruling)

None. The round-3 SA-01 (a full disk blocks startup during a crash loop) was ruled by the owner on 2026-11-17 and is in the backlog (`.planning/backlog/MAINTENANCE.md:33`).

---

_Reviewed: 2026-11-17T04:23:15Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Head: d3edc849ebda0f73bb4fd32201d5a7db8d7ae62a_
