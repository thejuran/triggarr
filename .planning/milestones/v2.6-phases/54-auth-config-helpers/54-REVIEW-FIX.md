---
phase: 54-auth-config-helpers
fixed_at: 2026-04-14T00:00:00Z
review_path: .planning/phases/54-auth-config-helpers/54-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 54: Code Review Fix Report

**Fixed at:** 2026-04-14
**Source review:** .planning/phases/54-auth-config-helpers/54-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: hash_password crashes on passwords exceeding 72 bytes

**Files modified:** `triggarr/auth.py`
**Commit:** 49a999e
**Applied fix:** Added explicit 72-byte length check on encoded password before passing to bcrypt. Raises `ValueError` with clear message instead of letting bcrypt crash with an opaque error.

### CR-02: sign_session accepts empty secret, producing forgeable cookies

**Files modified:** `triggarr/auth.py`
**Commit:** 49a999e
**Applied fix:** Added `if not secret` guard to `sign_session` (raises `ValueError`) and `validate_session` (returns `None`). Prevents signing with an empty key and silently rejects validation attempts with no secret configured.

### WR-01: verify_password crashes with ValueError on empty or invalid hash

**Files modified:** `triggarr/auth.py`
**Commit:** 49a999e
**Applied fix:** Wrapped `bcrypt.checkpw` call in try/except catching `ValueError` and `TypeError`, returning `False` instead of crashing on invalid or empty hash strings.

### WR-02: Test assertion does not actually verify absence of auth secrets

**Files modified:** `tests/test_auth_config.py`
**Commit:** 8b395fc
**Applied fix:** Replaced weak assertion (`len([s for s in secrets if s in ("",)]) == 0`) with direct `assert secrets == []` which properly verifies that no secrets are collected when all auth values are empty defaults.

## Skipped Issues

None.

---

_Fixed: 2026-04-14_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
