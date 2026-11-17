---
phase: 88-bounded-upgrade-backups-telemetry-regression
reviewed: 2026-11-16T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - README.md
  - tests/test_db.py
  - tests/test_telemetry.py
  - triggarr/db.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 88: Code Review Report

**Reviewed:** 2026-11-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found
**Diff range:** `a1b4b65c..HEAD`

## Summary

Phase 88 caps timestamped pre-upgrade retry backups at 3 per schema version (`_prune_timestamped_backups` in `triggarr/db.py`), adds 9 tests for it, adds a startup regression test for the FastAPI OpenTelemetry auto-configure variables, and adds one README sentence.

The pruning logic matches the plan:
- Candidates are matched by an exact prefix plus `fullmatch` on the stamp.
- They are listed with `iterdir`, not glob.
- The canonical backup can never match.
- The just-written file is excluded.
- Ordering uses the filename stamp, not mtime.
- OSError on listing or unlink is logged once at WARNING and never re-raised.

I found no correctness bug on the normal path. The 12 focused tests pass and ruff is clean.

Main concerns:
- **WR-01:** the backup is copied straight to its final name and pruned afterwards. A copy that fails partway (for example, disk full) leaves a truncated file. Later pruning counts that file as one of the "3 most recent" and can delete good backups to keep it.
- **WR-02:** the telemetry test never checks that FastAPI's auto-configure path actually ran. It would still pass if FastAPI renamed or dropped the variable.

## Warnings

### WR-01: A truncated retry backup from a failed copy is kept as one of the "3 most recent", and good backups are deleted to make room for it

**File:** `triggarr/db.py:277-287` (with `triggarr/db.py:199-210`)
**Issue:** `run_migrations` writes the retry backup straight to its final name, `shutil.copy2(db_path, timestamped_path)`. Pruning runs only after that copy succeeds. If `copy2` fails partway, for example with ENOSPC (the situation a crash loop that fills the disk is likely to cause), `copyfile` leaves a partial `test.v9-backup-<stamp>` file behind and pruning never runs for that attempt. On the next attempt the partial file:
- has a valid stamp,
- passes `is_file()`, and
- is newer than the older good copies.

So `_prune_timestamped_backups` keeps it as one of the 3 retained backups and deletes older, intact ones. The INFO line then says it is "keeping ... the 3 most recent", which suggests to an operator that those copies can be used for recovery. The canonical `.v9-backup` is still intact, so the original data is not lost. Still, the retry set can quietly fill with corrupt files.

Related: the copy happens before the prune, so peak disk use during an attempt is canonical plus 4 timestamped copies, not plus 3. That is the moment a nearly full disk is most likely to fail.

The project convention in `CLAUDE.md` is "Atomic file writes (write-then-rename) for config and state". The backup write does not follow it.

**Fix:** Write the copy to a temporary name that the stamp regex cannot match, then rename it into place. A failed copy then never produces a candidate name:
```python
stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
timestamped_path = db_path.with_suffix(f".v{current}-backup-{stamp}")
tmp_path = timestamped_path.with_name(timestamped_path.name + ".partial")
try:
    shutil.copy2(db_path, tmp_path)
    tmp_path.replace(timestamped_path)
finally:
    tmp_path.unlink(missing_ok=True)
```
Optionally, prune down to `_MAX_RETAINED_TIMESTAMPED_BACKUPS - 1` before the copy, so the peak is canonical plus 3. Add a test: patch `shutil.copy2` to write a few bytes and then raise `OSError(28, ...)`, then check that no `*-backup-<stamp>` file is left behind.

### WR-02: The telemetry regression test cannot tell whether the auto-configure path was exercised

**File:** `tests/test_telemetry.py:23-37`
**Issue:** The test sets `FASTAPI_OTEL_AUTO_CONFIGURE=true` and an OTLP endpoint, starts the app, and checks only that `/health` returns 200.

In FastAPI 0.162.4, the auto-configure failure (missing `opentelemetry-sdk` / exporter) is caught inside FastAPI's own `telemetry/_runtime.lifespan` and only logged as a warning. The test would pass the same way if any of these happened:
- FastAPI renamed or dropped `FASTAPI_OTEL_AUTO_CONFIGURE`,
- a FastAPI downgrade removed the telemetry module,
- the variable were read at a different time.

In each case the "pinned" behaviour is never reached. The test claims to pin TELEM-01 but would stay green when nothing is being pinned.

The test also builds its own `FastAPI(lifespan=...)` instead of the production construction in `triggarr/__main__.py:68-73` (middleware and static mount). A future production-only change, such as passing `telemetry=` there, would not be covered.

**Fix:** Assert that the precondition took effect, and that the failure was absorbed rather than skipped:
```python
app = FastAPI(lifespan=lifespan_fn)
assert app._telemetry["auto_configure"] is True  # env var was honoured at construction
...
with caplog.at_level(logging.WARNING, logger="fastapi"), TestClient(app) as client:
    response = client.get("/health")
assert "automatic telemetry configuration failed" in caplog.text
```
If relying on the private `_telemetry` attribute is unacceptable, the caplog assertion alone still proves the path ran.

## Info

### IN-01: The stamp regex accepts non-ASCII digits

**File:** `triggarr/db.py:117`
**Issue:** `re.compile(r"\d{8}T\d{12}Z")` on a `str` matches any Unicode decimal digit. I verified that `"٢٠٢٦0101T000000000000Z"` fully matches. That conflicts with the D-07 rule that only names exactly in the `strftime` format are ever deletion candidates, and non-ASCII digits would also break the "fixed-width string order = time order" assumption. It needs a deliberately odd filename to trigger.
**Fix:** `re.compile(r"[0-9]{8}T[0-9]{12}Z")` or add `flags=re.ASCII`.

### IN-02: The end-to-end pruning-failure test accepts any WARNING, not specifically the pruning one

**File:** `tests/test_db.py:2903-2906`
**Issue:** `test_run_migrations_proceeds_when_pruning_fails` checks only that some line starts with `WARNING`. The v10 migration emits no warnings today, so the test passes for the right reason. But any future WARNING from `run_migrations` or `_migrate_v10` would satisfy it even if pruning stopped logging.
**Fix:** Assert on the message: `assert "Could not remove old retry backup" in log_text`.

### IN-03: The README does not mention the warning operators will see

**File:** `README.md:215`
**Issue:** The new sentence says the variables "do not stop Triggarr from starting, but nothing is exported". With them set, FastAPI logs `FastAPI automatic telemetry configuration failed: Automatic OpenTelemetry export requires fastapi[opentelemetry] ...` through stdlib logging at startup. That message tells the operator to install an extra, which is not possible in the shipped image and is not supported. An operator could read it as a misconfiguration to fix.
**Fix:** Add: "FastAPI logs a one-time warning about the missing OpenTelemetry extra; it is harmless and can be silenced by unsetting the variables."

### IN-04: Retry backups for already-completed upgrades are never cleaned up

**File:** `triggarr/db.py:285` (design, D-06/D-07)
**Issue:** Pruning runs only for the `current` version, and only on the retry path. After a crash loop that ends in success, the 3 retry copies for that version stay forever. Only a new crash loop from the same version would prune them, and that can no longer happen. The size is bounded at 3, so this is informational and matches D-06 as decided.
**Fix:** None required. See SA-01.

## Conventions

### CV-01: README file-name casing (tool output, false positive)

**File:** `README.md:1`
**Deviation:** The convention checker reports "file name casing is CONSTANT (README)" against a derived "camel" file-name convention.
**Convention:** file-name-casing should be camel (derived by `verify conventions --check`).
**Fix:** None recommended. `README.md` is a universal fixed name, so this is a false positive in the rule pack, not a defect. It is listed only because the tool emitted it. It does not count toward the totals.

## Set aside (needs ruling)

### SA-01: No cleanup of retry backups after a successful upgrade

**Where:** `triggarr/db.py:275-291`
**Why excluded:** D-06 locks "nothing extra is deleted on the success path". Removing leftover retry backups after success would be a product decision, not a defect.
**Effect if left as is:** After a crash loop that ends in success, users keep the canonical backup plus up to 3 full-size database copies for that version indefinitely. Disk use stays bounded but is never reclaimed automatically.
**Needs:** Owner ruling: accept (current D-06), or defer a "remove retry backups once the upgrade succeeds" item to the backlog.

---

_Reviewed: 2026-11-16T00:00:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
