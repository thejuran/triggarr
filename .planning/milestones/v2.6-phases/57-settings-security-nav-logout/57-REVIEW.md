---
phase: 57-settings-security-nav-logout
reviewed: 2026-04-14T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - triggarr/web/routes.py
  - tests/test_auth_routes.py
  - triggarr/templates/settings.html
  - triggarr/templates/partials/security_password.html
  - triggarr/templates/partials/security_apikey.html
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 57: Code Review Report

**Reviewed:** 2026-04-14
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 57 adds three new security-settings endpoints (`POST /settings/password`, `POST /settings/security`, `POST /settings/api-key/regenerate`), a logout route, and the associated HTML partials and templates. The overall structure is solid: SecretStr discipline is maintained throughout, all three new write endpoints hold `search_lock` for atomic TOML writes, the `Disabled` auth method is correctly rejected at the API layer, and the password change handler always verifies the current password before accepting a new one.

Three warnings were found, none of which are exploitable in isolation, but each represents a real correctness or security gap worth closing before a release tag. Three informational items are included for completeness.

---

## Warnings

### WR-01: TOCTOU in `change_password` — verification uses pre-lock snapshot; concurrent password change can succeed against a stale hash

**File:** `triggarr/web/routes.py:1194-1219`

**Issue:** `settings` is read from `request.app.state.settings` at line 1194, before the `search_lock` is acquired. The `verify_password` call at line 1203 therefore runs against a snapshot that could be stale if a concurrent request is simultaneously changing the password. A second concurrent `POST /settings/password` that races between the read at line 1194 and the lock acquisition at line 1222 would verify the current password against the *old* hash and could succeed, overwriting the winner's new hash with the loser's hash.

This is a low-probability race (requires two concurrent password-change requests), but the pattern is inconsistent with how `setup_post` handles the same concern (it re-checks `needs_setup` inside the lock at line 1065-1066).

**Fix:** Read settings and verify the current password inside the lock, mirroring the setup_post guard:

```python
async with request.app.state.search_lock:
    current_settings = request.app.state.settings
    if not verify_password(current_password, current_settings.auth.password_hash.get_secret_value()):
        # Return error — cannot set response inside lock easily, so either restructure
        # or use a flag and return after the lock block.
        pass
    else:
        new_auth = current_settings.auth.model_copy(update={"password_hash": SecretStr(new_hash)})
        updated = current_settings.model_copy(update={"auth": new_auth})
        ...
```

---

### WR-02: API key exposed in plaintext in HTML `data-key` attribute on every settings page load

**File:** `triggarr/templates/partials/security_apikey.html:12`

**Issue:** The `data-key="{{ key }}"` attribute on the `<input>` element places the full API key in plaintext into every HTML response for `GET /settings`. The key is present in:

1. The DOM (accessible to any injected script, browser extensions, dev-tools).
2. The raw HTML in browser history and any intermediate caches.
3. Server-side HTML response logs if request/response logging is ever enabled.

This is the mechanism used by `copyApiKey()` in `settings.html` line 282 (`var key = document.getElementById('api-key-input').dataset.key`). The `value` attribute is already present on the same input, so `data-key` is a redundant second copy.

The API key is treated as a credential (equivalent to a session secret) per CLAUDE.md conventions. Embedding it in two places in the DOM doubles the exposure surface with no functional benefit.

**Fix:** Remove `data-key` and update `copyApiKey()` to read from `input.value` directly, which is already populated:

```html
<!-- security_apikey.html: remove data-key attribute -->
<input type="{{ 'text' if is_revealed else 'password' }}" value="{{ key }}" readonly
       id="api-key-input"
       class="...">
```

```javascript
// settings.html copyApiKey(): read from value, not dataset.key
function copyApiKey(btn) {
    var key = document.getElementById('api-key-input').value;
    ...
}
```

---

### WR-03: `change_password` endpoint accessible regardless of auth method; no guard against `Disabled` or `External` mode

**File:** `triggarr/web/routes.py:1191-1241`

**Issue:** `POST /settings/password` and `POST /settings/api-key/regenerate` have no guard against the auth method being `Disabled` or `External`. When `auth.method == "External"`, authentication is delegated to the reverse proxy; there is no local password to change. When `auth.method == "Disabled"`, `AuthMiddleware` passes all requests through without any session validation.

In `Disabled` mode, `POST /settings/password` will call `verify_password("", "")` which returns `False` (bcrypt rejects an empty hash), so the error path is taken — this is safe by accident rather than by explicit guard. However, in `External` mode, a locally authenticated session cookie could still reach this endpoint and change the local password hash that is never actually used for authentication, which is confusing but not directly exploitable.

The real risk is that there is no explicit assertion in the code that communicates this constraint to future maintainers, making it easy to introduce a regression.

**Fix:** Add an explicit guard at the top of both `change_password` and `regenerate_api_key_endpoint`:

```python
@router.post("/settings/password")
async def change_password(request: Request) -> HTMLResponse:
    settings = request.app.state.settings
    if settings.auth.method not in ("Forms", "Basic"):
        return HTMLResponse("Password management is only available in Forms or Basic auth mode", status_code=400)
    ...
```

---

## Info

### IN-01: `save_security` silently ignores the no-op case (method unchanged)

**File:** `triggarr/web/routes.py:1244-1272`

**Issue:** When the submitted `auth_method` matches the current method, the handler still acquires `search_lock`, writes the TOML file, reloads config, and refreshes the redacting sink. This is a needless full write cycle for a no-op change. While not a bug, it causes spurious disk writes and log noise on every "Save" click without an actual change.

**Fix:** Short-circuit when the method is unchanged:

```python
if auth_method == settings.auth.method:
    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)
```

---

### IN-02: Test file imports `re` inside a test function body

**File:** `tests/test_auth_routes.py:632`

**Issue:** `import re as _re` appears inside `test_regenerate_api_key` at line 632. This is a style inconsistency — all other imports are at the module top level. Ruff rule `E402` / `PLC0415` will not flag this as an error (it's inside a function), but `isort` / ruff `I` rules may surface it depending on configuration, and it's at odds with the project's module-level import convention.

**Fix:** Move `import re` to the top of the test file with the other standard library imports.

---

### IN-03: `security_apikey.html` fallback variable resolution is fragile

**File:** `triggarr/templates/partials/security_apikey.html:1`

**Issue:** `{% set key = api_key if api_key is defined else auth_api_key %}` relies on Jinja2's `is defined` test to distinguish the two context variable names used in different rendering paths (inline settings page vs. htmx partial response from `regenerate_api_key_endpoint`). If either variable name is misspelled in a future route handler, the template will silently render a blank key value without raising an error, because `is defined` swallows missing-variable errors.

**Fix:** Use a single, consistent context variable name (`api_key`) in both rendering paths. Update `settings_page` to pass `api_key` instead of `auth_api_key`, and remove the fallback from the template:

```python
# routes.py settings_page context:
"api_key": settings.auth.api_key.get_secret_value(),
```

```html
<!-- security_apikey.html: -->
{% set key = api_key %}
```

---

_Reviewed: 2026-04-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
