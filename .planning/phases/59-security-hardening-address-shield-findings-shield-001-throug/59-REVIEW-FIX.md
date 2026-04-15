---
phase: 59-security-hardening
fixed_at: 2026-04-15T12:15:00Z
review_path: .planning/phases/59-security-hardening-address-shield-findings-shield-001-throug/59-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 59: Code Review Fix Report

**Fixed at:** 2026-04-15T12:15:00Z
**Source review:** .planning/phases/59-security-hardening-address-shield-findings-shield-001-throug/59-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Rate limiter dict has no eviction bound for tracked IPs

**Files modified:** `triggarr/web/routes.py`
**Commit:** 3a7d7b4
**Applied fix:** Added `_MAX_TRACKED_IPS = 10_000` constant and LRU eviction logic in `_record_failure()`. When a new IP is recorded and the dict has reached capacity, the entry with the oldest most-recent timestamp is evicted before inserting the new IP.

### WR-02: Successful login log leaks plaintext username

**Files modified:** `triggarr/web/routes.py`
**Commit:** 3a7d7b4
**Applied fix:** Changed `logger.info("Login successful for user {username}", username=username)` to `logger.info("Login successful")`, removing the plaintext username from the success log to match the sanitization applied to failure logs under SHIELD-005.

**Note:** Both WR-01 and WR-02 were applied to the same file (`triggarr/web/routes.py`) and were committed atomically in a single commit.

**Test verification:** All 801 tests pass after fixes (`uv run pytest tests/ -x -q`).

---

_Fixed: 2026-04-15T12:15:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
