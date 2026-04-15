---
phase: 56-first-run-setup-login
reviewed: 2026-04-14T12:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - tests/test_auth_middleware.py
  - tests/test_auth_routes.py
  - triggarr/templates/base-auth.html
  - triggarr/templates/base.html
  - triggarr/templates/login.html
  - triggarr/templates/setup.html
  - triggarr/web/middleware.py
  - triggarr/web/routes.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 56: Code Review Report

**Reviewed:** 2026-04-14T12:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 56 implements first-run setup, login/logout flows, auth middleware, and integration tests. The implementation is solid overall: open redirect prevention is correct, SecretStr discipline is maintained (extraction only at TOML serialization and HTTP client init), session cookies use httponly/samesite/secure flags, and the middleware follows a deny-all-then-whitelist pattern. Template autoescape is enabled globally, preventing XSS in reflected values like `next_url` and `username`.

Two warnings found: a timing side-channel on username comparison in the login route, and a logic gap in `_sync_auth_state` that could show the Logout button during first-run setup.

## Warnings

### WR-01: Username comparison in login_post is not timing-safe

**File:** `triggarr/web/routes.py:1119`
**Issue:** The login route uses plain `==` to compare the submitted username against `auth.username`. This leaks information about valid usernames via timing side-channel. The middleware's `_handle_basic_auth` correctly uses `secrets.compare_digest` for the same comparison (line 143), but the forms login path does not.
**Fix:**
```python
import secrets

# Replace line 1119:
#     and username == auth.username
# With:
    and secrets.compare_digest(username, auth.username)
```

### WR-02: _sync_auth_state shows Logout button during needs_setup state

**File:** `triggarr/web/routes.py:78`
**Issue:** `_sync_auth_state` sets `auth_state["active"] = True` whenever `method` is "Forms" or "Basic", but does not check `needs_setup`. When the app is in first-run state (no credentials configured), `method` defaults to "Forms", so `active` becomes `True` and `base.html` line 51 renders the Logout button in the nav bar -- even though no user is logged in. The integration tests mask this because they manually set `auth_state["active"]` (test_auth_routes.py line 79).
**Fix:**
```python
def _sync_auth_state(settings: SettingsModel) -> None:
    """Update auth_state dict for template conditional rendering (D-11)."""
    auth_state["active"] = (
        settings.auth.method in ("Forms", "Basic")
        and not settings.auth.needs_setup
    )
    auth_state["method"] = settings.auth.method
```

## Info

### IN-01: Clipboard API fallback in setup.html does not actually copy to clipboard

**File:** `triggarr/templates/setup.html:79-84`
**Issue:** The `copyApiKey` fallback branch (when `navigator.clipboard` is unavailable) selects the text visually using `window.getSelection()` but does not call `document.execCommand('copy')`, so the text is highlighted but not copied to the clipboard. The button still says "Copied!" which is misleading.
**Fix:**
```javascript
} else {
    var range = document.createRange();
    range.selectNodeContents(document.getElementById('api-key-display'));
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand('copy');
    btn.textContent = 'Copied!';
    setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
}
```

---

_Reviewed: 2026-04-14T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
