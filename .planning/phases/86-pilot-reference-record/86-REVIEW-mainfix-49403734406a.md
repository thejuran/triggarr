---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T03:35:15Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - tests/test_codex_review_container.py
  - uv.lock
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 86: Code Review Report

**Reviewed:** 2026-11-14T03:35:15Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (Info only; no Critical or Warning findings)

## Summary

Scope is the two commits in `b80c3e26cf9456dde7245350d7033f6feb94db0f..49403734406a7c0073def56b5fc5740b81fcf30e`
on branch `fix/main-ci-otel-and-clock-tests`:

- `d824705` adds a `_FrozenDatetime` stand-in to `tests/test_codex_review_container.py` (14 added lines) and
  installs it on the runner module from the shared `_BoundaryFixture`.
- `4940373` bumps `opentelemetry-api` 1.45.1 -> 1.45.2 in `uv.lock` (3 changed lines).

I looked for defects in both and found none that change behavior. Two Info items and one set-aside item follow.

**What was checked, and the result**

| Check | Result |
|---|---|
| `uv run pytest tests/test_codex_review_container.py` at head | 312 passed, 1 skipped |
| `uv run pytest tests/` at head (run 16-17 days after the fixture's `_NOW`, so past the 7-day limit) | 3281 passed, 1 skipped |
| `uv run ruff check tests/test_codex_review_container.py` | clean |
| `uv lock --check` | lock is consistent with `pyproject.toml` |
| Locked sdist and wheel sha256, size and upload time for `opentelemetry-api` 1.45.2 vs. the PyPI JSON API | all match; release not yanked |
| CI's audit command (`uv export --locked --no-dev ...` then `pip-audit==2.10.1 --strict --no-deps --disable-pip`) run locally | "No known vulnerabilities found", exit 0 |
| Every clock read in `tests/codex_review_run.py` | exactly one: line 1660, `checked_at = now or datetime.now(UTC)`; no `time.time`, `utcnow` or `today` |
| BM convention check on the two files | no findings (no rule pack applies to Python or lock files) |

**Not checked:** I did not reproduce the "11 tests failed on main" claim from the `d824705` commit message, because
doing so needs the pre-fix tree and this review was restricted to no branch switches and no file changes. The
mechanism is confirmed by reading: `verify_boundary_main()` (runner line 4202) and the untrusted path in `main()`
(runner line 4346) call `verify_isolation_boundary()` without `now`, so line 1660 read the real clock while the
fixture's sign-in date is `_NOW - 1 day` (test line 1931).

**Why the clock fix is sound**

- The runner imports `from datetime import UTC, datetime`, so patching the module attribute `datetime` reaches the
  single clock read. `UTC` is untouched.
- The other use of the patched name is `datetime.fromisoformat(...)` in `credential_preflight()` (runner line 2940).
  On the subclass this returns a `_FrozenDatetime` instance; subtraction, `.tzinfo`, `.replace()` and
  `.isoformat()` all behave as on `datetime`, and the tests that assert `age_days == 1.0` pass.
- The patch goes through `monkeypatch`, so it is undone after each test and cannot leak into other test files.
- Tests that pass `now=_NOW` explicitly are unaffected (`now or ...` short-circuits).
- The freshness-limit tests (test lines 1166-1223, 2144) pass `now=_NOW` directly to the function under test, so
  the freeze does not weaken the 7-day boundary coverage.

**Why the lock bump is sound**

- Only the `opentelemetry-api` package block changed; its dependency list (`typing-extensions`) is unchanged and
  no other package moved.
- The Dockerfile installs from an export of `uv.lock` with `--require-hashes`, and the hashes in the lock match
  what PyPI serves, so the image build will accept the new files.

## Narrative Findings (AI reviewer)

## Info

### IN-01: `_FrozenDatetime.now()` returns a timezone-aware value when called with no timezone

**File:** `tests/test_codex_review_container.py:92-94`
**Issue:** The real `datetime.now()` with no argument returns a naive local time. The stand-in returns `_NOW`,
which is UTC-aware, in that case. Nothing triggers this today: the runner's only clock read passes `UTC`. If a
later runner change adds a bare `datetime.now()` and mixes it with naive values, the tests would raise
`TypeError` (or pass) where production behaves differently. The method also returns a plain `datetime`, not a
`cls` instance; that is harmless here.
**Fix:** Match the stdlib contract, or refuse the unused case so a future caller fails loudly:
```python
@classmethod
def now(cls, tz=None):
    if tz is None:
        raise AssertionError("runner must read the clock with an explicit timezone")
    return _NOW.astimezone(tz)
```

### IN-02: The clock freeze is an undocumented side effect of `_BoundaryFixture`

**File:** `tests/test_codex_review_container.py:1922-1941`
**Issue:** The class docstring still reads "A fake host identity + per-run scratch tree", but constructing the
fixture now also replaces the runner's whole `datetime` name for the rest of the test. A test author who builds a
`_BoundaryFixture` and then wants to exercise real-clock behavior, or who inspects the type of a parsed timestamp,
gets the frozen class with no hint from the fixture. The new `setattr` line is also placed between two unrelated
`delenv` calls (line 1939), which makes it easy to miss. No current test is affected.
**Fix:** Add one sentence to the `_BoundaryFixture` docstring stating that it freezes the runner's clock at `_NOW`,
and move the `setattr` next to the other `codex_review_run` patch on line 1941.

## Set aside (needs ruling)

### SA-01: Runner entry points have no way to be given a clock

**Where:** `tests/codex_review_run.py:1660`, called without `now` at `:4202` (`verify_boundary_main`) and `:4346`
(`main`, untrusted path)
**Why excluded:** `tests/codex_review_run.py` is not in the changed-file list for this review; the commit under
review deliberately works around it from the test side.
**Effect if left as is:** No user-facing effect. The cost is in maintenance: tests must replace the module's
`datetime` name wholesale to control time, which is what makes IN-01 and IN-02 possible. Any future test that
reaches these entry points without `_BoundaryFixture` and uses a `_NOW`-relative sign-in date will start failing
about a week after it is written, the same way the 11 tests did.
**Needs:** Ruling from the developer: accept the test-side patch as the standing approach, or defer a small
runner change (a module-level `_now()` helper that tests patch, or a `now` parameter threaded through the two
entry points) to a later phase.

---

_Reviewed: 2026-11-14T03:35:15Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
