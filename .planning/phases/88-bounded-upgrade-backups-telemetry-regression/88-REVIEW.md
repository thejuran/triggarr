---
phase: 88-bounded-upgrade-backups-telemetry-regression
reviewed: 2026-11-17T14:30:30Z
reviewed_head: 39ccfabb3c0d9a26a14c5be74dbeceb4d1f12ca5
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

# Phase 88: Code Review Report (PR #63 head 39ccfabb)

**Reviewed:** 2026-11-17T14:30:30Z
**Reviewed head:** `39ccfabb3c0d9a26a14c5be74dbeceb4d1f12ca5`
**Diff range:** `a1b4b65c..39ccfabb`
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found (Info only; no Critical or Warning)

## Summary

Scope checks:
- `git diff 39ccfabb HEAD -- . ':!.planning/'` is empty, so the four files on disk are byte-identical to the PR head.
- `git diff --quiet d3edc849 39ccfabb -- README.md tests/ triggarr/` succeeds. The commits after the round-4 head (`770de346`, `e4ea7bb7`, `39ccfabb`) touch only `.planning/`, so the files in scope are unchanged since round 4 (and since round 3, `91eef365`).

I still re-read the whole phase diff (`a1b4b65c..39ccfabb`) instead of copying the earlier report.

What I re-traced in `triggarr/db.py`:
- **Order of the retry-backup steps** (`db.py:331-367`): abandoned `.partial` files are removed, then timestamped copies are pruned to N-1 (2). The copy is written to `<name>.partial` and renamed into place, then a post-copy prune keeps the new copy plus the 2 newest. That gives canonical + 3 after a successful copy and canonical + 2 after a failed one. A copy that keeps failing does not keep deleting backups, and the canonical backup is never a candidate.
- **Name matching** (`db.py:201-216`, `db.py:260-270`): needs the exact `<stem>.v{current}-backup-` prefix and an ASCII-only full stamp match. Other versions, the canonical file, `.partial` files (in the pruner) and look-alike names cannot match. `entry == just_written` compares paths built from the same parent, so the new copy is always excluded, even if the clock went back (tested).
- **Error handling**: listing and unlink failures log a WARNING and continue or return. They never block startup. A copy failure (`except BaseException`) removes the partial file, logs if that removal fails, and re-raises the original error. Log fields carry paths and exception text only, with no secrets.
- **Telemetry test** (`tests/test_telemetry.py`): sets the env before `FastAPI()` is built, clears OTEL variables from the runner that could change the result, and drives the lifespan through `TestClient`. The check on the warning wording is D-12, which the owner put out of scope.
- **README** (`README.md:215`): accurate for the FastAPI auto-configure behavior the test pins. Unchanged since round 3.

Checks on this head:
- `uv run pytest tests/test_db.py tests/test_telemetry.py -q`: 122 passed
- `uv run ruff check triggarr/ tests/`: All checks passed

No new defects found. The two round-3 Info items are still in the code unchanged. They are carried forward so this report is accurate for this head. Both are already in the backlog (`.planning/backlog/MAINTENANCE.md:34-36`, owner stopping rule 2026-11-17) and are not new requests for a fix in this phase.

Not raised again, by owner ruling: IN-04/D-06 (retry copies left after a successful upgrade; `MAINTENANCE.md:32`), CV-01 (convention-checker false positive), D-12 (telemetry test asserts the warning wording), and the full-disk crash-loop item (`MAINTENANCE.md:33`).

## Original vs. refreshed findings

| Prior ID (round 4, `d3edc849`) | Status at `39ccfabb` | Evidence |
|---|---|---|
| IN-01 single-process assumption documented, not enforced | **Still present, backlogged** (carried as IN-01) | `db.py:249-264` and `db.py:333-338` unchanged; no lock or age guard. |
| IN-02 pre-copy prune log says "3 most recent" | **Still present, backlogged** (carried as IN-02) | `db.py:236-240` still logs `n=_MAX_RETAINED_TIMESTAMPED_BACKUPS` for both the pre-copy and post-copy calls. |

## Narrative Findings (AI reviewer)

## Info

### IN-01: Partial-file cleanup relies on a documented "only one process" assumption that the code does not enforce (carried forward; backlogged at MAINTENANCE.md:34-35)

**File:** `triggarr/db.py:249-264`, `triggarr/db.py:333-339`
**Issue:** `_remove_abandoned_partial_backups` deletes every `.partial` file for the current version, whatever its age. Only a comment says this is safe because Triggarr runs as a single process. If two instances share one data volume and both start during a failed-upgrade crash loop, one can delete the other's in-progress `.partial` file. The other then fails at `partial_path.replace(...)` and has to restart. No valid backup is lost, because the canonical backup is never touched. Running two instances this way is not supported.
**Fix (backlog):** Skip `.partial` files modified in the last few minutes (`if entry.stat().st_mtime > time.time() - 300: continue`), or document the single-instance requirement in the README deployment notes.

### IN-02: The pre-copy prune log says "the 3 most recent" while only 2 are kept (carried forward; backlogged at MAINTENANCE.md:34, 36)

**File:** `triggarr/db.py:236-240` (called with `just_written=None` from `db.py:339`)
**Issue:** The INFO line always reports `n=_MAX_RETAINED_TIMESTAMPED_BACKUPS` (3). Before the copy, the prune keeps 2. If the copy then fails, the log says 3 are kept while only 2 are on disk, which can mislead an operator counting backups during recovery.
**Fix (backlog):**
```python
logger.info(
    "Removed old retry backup {path}; keeping the original backup and the {n} most recent retry backups",
    path=stale_path,
    n=_MAX_RETAINED_TIMESTAMPED_BACKUPS - 1 if just_written is None else _MAX_RETAINED_TIMESTAMPED_BACKUPS,
)
```

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-11-17T14:30:30Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Head: 39ccfabb3c0d9a26a14c5be74dbeceb4d1f12ca5_
