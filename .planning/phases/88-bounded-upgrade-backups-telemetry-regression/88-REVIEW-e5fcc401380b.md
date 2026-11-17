---
phase: 88-bounded-upgrade-backups-telemetry-regression
reviewed: 2026-11-17T03:21:10Z
reviewed_head: fbc812eba07f674069e04486f369524e58927298
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
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 88: Code Review Report (re-review after fix round 1)

**Reviewed:** 2026-11-17T03:21:10Z
**Reviewed head:** `fbc812eba07f674069e04486f369524e58927298`
**Diff range:** `a1b4b65c..fbc812eb` (fix commits `6e94aaea..d7cc03a2` read closely)
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

This is a re-review of the whole Phase 88 diff after the first fix round. The phase does three things:
- It caps timestamped pre-upgrade retry backups at 3 per schema version (`_prune_timestamped_backups`).
- It writes each retry backup to a `.partial` file and then renames it (the WR-01 fix).
- It pins startup against FastAPI's OpenTelemetry auto-configure variables and documents that in the README.

The fixes for WR-01, WR-02, IN-01, IN-02 and IN-03 are correct:
- The `.partial` name can never fully match `[0-9]{8}T[0-9]{12}Z`, so pruning can never count it.
- If the copy fails, the cleanup removes the temporary file and re-raises the original exception. A bare `raise` after the inner `try/except` re-raises the outer exception, so the original error is not lost.
- The success path makes no extra delete call.
- The telemetry test now fails if FastAPI's auto-configure path does not run.

I checked the FastAPI 0.162.4 source (`fastapi/telemetry/_runtime.py`). The startup failure is caught inside FastAPI's lifespan wrapper and logged at WARNING through the stdlib `fastapi` logger. The assertion matches that message.

Checks on this head: the 18 focused backup, prune and telemetry tests pass, and `ruff check triggarr/ tests/` is clean. I did not re-run the full suite. The fix report records 3347 passed, 1 skipped.

What remains:
- **WR-01 (carried forward, the optional part of the original WR-01):** pruning runs only after a successful copy, so it cannot free disk space when the disk is full.
- **Three Info items:** a README claim that is only partly accurate, a telemetry test that depends on the runner's environment, and two test-coverage gaps around the new cleanup branch.

## Original vs. refreshed findings

| Prior ID | Prior title (short) | Status at `fbc812eb` | Evidence |
|---|---|---|---|
| WR-01 | Truncated retry backup counted as one of the 3 most recent | **Fixed**, with a residual carried forward as the new WR-01 | `6e94aaea`: write to `.partial`, then `replace`, and clean up on failure (`triggarr/db.py:285-298`). The new test `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups` covers it. The optional "prune before copy / peak disk" part was not done and is now the new WR-01. |
| WR-02 | Telemetry test cannot tell whether auto-configure ran | **Fixed** | `621aebb0` asserts `"automatic telemetry configuration failed"` in `caplog` (`tests/test_telemetry.py:37-42`). Residual: the test builds its own `FastAPI(lifespan=...)`. Production (`triggarr/__main__.py:68`) uses the same constructor with no `telemetry=` argument today, so I accept that and do not count it. |
| IN-01 | Stamp regex accepts non-ASCII digits | **Fixed** | `579d734e`: `[0-9]{8}T[0-9]{12}Z` (`triggarr/db.py:119`). An Arabic-Indic decoy was added to the test. |
| IN-02 | End-to-end pruning test accepts any WARNING | **Fixed** | `6387334c`: the test requires `"Could not remove old retry backup"` (`tests/test_db.py:2965-2967`). |
| IN-03 | README omits the startup warning | **Fixed**, with a refinement in the new IN-01 | `d7cc03a2` adds the warning sentence (`README.md:215`). The sentence overstates when the warning appears and what it says (new IN-01). |
| IN-04 | Retry backups never cleaned after a successful upgrade | **Carried forward, accepted by owner ruling** (not counted) | Unchanged by design (D-06). The owner kept D-06, and the cleanup is in the backlog together with stale `.partial` files. |
| CV-01 | README file-name casing (tool output) | **False positive** (not counted) | The convention checker emitted it again at this head (see Conventions). |
| SA-01 | No cleanup of retry backups after success | **Resolved by owner ruling: keep D-06, defer to backlog** | The backlog item "Remove retry backups once an upgrade succeeds" covers timestamped copies and stale `.partial` files. No code change is expected in this phase. |

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Pruning runs only after a successful copy, so it cannot free space when the disk is full and a restart fails at the backup step

**File:** `triggarr/db.py:279-305`
**Issue:** On the retry path, the order is:
1. copy to `.partial`
2. rename
3. `_prune_timestamped_backups`

At step 1, the disk holds the canonical backup, the 3 retained timestamped copies, and the new copy in progress. That is one full database copy more than the cap the phase promises. If the disk cannot hold that extra copy, `copy2` raises ENOSPC. The `.partial` is cleaned up correctly, but the exception leaves `run_migrations` before pruning runs, so the 3 old copies are never reduced.

Every later start repeats this. That includes the start after the user installs a release that fixes the failing migration. Triggarr does not start again until someone deletes backup files by hand. The phase's own retained copies are what fill the space, and the pruning meant to bound them never gets a chance to run.

This is far better than the unbounded behaviour before the phase. Still, the "at most 3" promise only holds when the disk has room for a fourth copy. The case it fails in is a disk that fills up during a crash loop, which is exactly the case the bound is for.

The fix report records this as "Not done (optional in the review)". It is carried forward here as a Warning because the user-facing effect is a startup that fails until files are deleted manually.
**Fix:** Prune to `N - 1` before the copy, then copy. If the copy fails, the user still has the canonical backup plus `N - 1` intact retry copies, and the peak is never more than canonical plus N:
```python
if backup_path.exists():
    # Make room first so the peak never exceeds canonical + N (BKUP-01).
    _prune_timestamped_backups(db_path, current, just_written=None, keep=_MAX_RETAINED_TIMESTAMPED_BACKUPS - 1)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    ...  # .partial copy + replace, unchanged
```
To do this, `_prune_timestamped_backups` takes `keep` and an optional `just_written`. Add a test: plant 3 good copies, make `copy2` raise ENOSPC, and assert that exactly 2 good copies and the canonical backup remain. Alternatively, if the owner prefers to keep 3 copies even when the copy fails, catch ENOSPC on the copy, prune, and retry once.

## Info

### IN-01: The README overstates when the FastAPI warning appears and what it says

**File:** `README.md:215`
**Issue:** The README says: "With `FASTAPI_OTEL_AUTO_CONFIGURE=true`, FastAPI logs a one-time startup warning that automatic telemetry configuration failed and suggests installing an OpenTelemetry extra." In FastAPI 0.162.4 (`fastapi/telemetry/_runtime.py:105-131`), that is only partly true:
- With `FASTAPI_OTEL_AUTO_CONFIGURE=true` and no OTLP endpoint (`OTEL_EXPORTER_OTLP_ENDPOINT` or a per-signal variant), nothing is requested and no warning is logged.
- With an endpoint but `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`, a non-`otlp` `OTEL_*_EXPORTER`, or an endpoint that is not an HTTP(S) URL, the warning says something different (protocol, exporter or endpoint error), not "install an extra".

An operator who sees a different message may not connect it to this README note.
**Fix:** Reword it, for example: "If `FASTAPI_OTEL_AUTO_CONFIGURE=true` is set together with an OTLP endpoint, FastAPI logs a one-time startup warning beginning 'FastAPI automatic telemetry configuration failed'. The warning is harmless, the OpenTelemetry extra it may suggest is not supported, and unsetting `FASTAPI_OTEL_AUTO_CONFIGURE` silences it."

### IN-02: The telemetry regression test depends on the runner's OTEL environment

**File:** `tests/test_telemetry.py:27-28`
**Issue:** The test sets two variables but does not clear the others FastAPI reads. If the CI runner or a developer shell has any of these set, no warning is logged and the test fails even though Triggarr behaves correctly:
- `OTEL_SDK_DISABLED=true` (`_runtime.py:96` returns early),
- `OTEL_TRACES_EXPORTER`, `OTEL_METRICS_EXPORTER` and `OTEL_LOGS_EXPORTER` all set to `none`,
- per-signal `OTEL_EXPORTER_OTLP_*_ENDPOINT` values that override the generic one.

This is a test-reliability issue, not a product defect.
**Fix:** Clear the other OTEL variables at the top of the test:
```python
for name in ("OTEL_SDK_DISABLED", "OTEL_TRACES_EXPORTER", "OTEL_METRICS_EXPORTER", "OTEL_LOGS_EXPORTER",
             "OTEL_EXPORTER_OTLP_PROTOCOL", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
             "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"):
    monkeypatch.delenv(name, raising=False)
```

### IN-03: The new cleanup-failure branch has no test, and the stale-`.partial` half of the WR-01 test does not guard the fix

**File:** `triggarr/db.py:289-298`, `tests/test_db.py:2654-2707`
**Issue:**
- No test covers the branch where removing the `.partial` itself fails. That branch should log `"Could not remove incomplete retry backup"` at WARNING and still raise the original copy error (ENOSPC), not the cleanup `OSError`. The behaviour is correct today, but a later refactor that replaces the bare `raise` with `raise cleanup_exc`, or drops the inner `try`, would not be caught.
- In `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups`, the second half plants `...-backup-20990101T000000000000Z.partial` and checks that it is not counted. The pre-fix code would also pass that check, because `fullmatch` already rejects the `.partial` suffix. Only the first half guards the fix. The test name and comment suggest the second half does too.
**Fix:** Add a test that patches `shutil.copy2` to write bytes and raise `OSError(28, ...)` and patches `Path.unlink` to raise `PermissionError` for `.partial` names. Assert that `pytest.raises(OSError)` sees `errno == 28` and that exactly one WARNING names the `.partial` file. Optionally, change the second-half comment to say it pins the regex boundary, not the write-then-rename fix.

## Conventions

### CV-01: README file-name casing (tool output, false positive; not counted)

**File:** `README.md:1`
**Deviation:** At this head, `verify conventions --check` again reports "file name casing is CONSTANT (README)".
**Convention:** file-name-casing should be camel (derived).
**Fix:** None. `README.md` is a fixed, universal name, so the rule pack is wrong here. This is advisory only and does not count toward the totals.

## Set aside (needs ruling)

None. This review raises no new set-aside items.

The prior SA-01 has an owner ruling: keep D-06, and backlog "remove retry backups once an upgrade succeeds", including stale `.partial` files left by a process killed mid-copy. Because of that ruling, this review does not raise that behaviour again. The `.partial` leftovers fall under the same backlog item.

---

_Reviewed: 2026-11-17T03:21:10Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Head: fbc812eba07f674069e04486f369524e58927298_
