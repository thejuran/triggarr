# Phase 56: First-Run Setup & Login - Pattern Map

**Mapped:** 2026-04-14
**Files analyzed:** 7 (3 new, 4 modified)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/templates/base-auth.html` | template | request-response | `triggarr/templates/base.html` | role-match |
| `triggarr/templates/login.html` | template | request-response | `triggarr/templates/dashboard.html` | role-match |
| `triggarr/templates/setup.html` | template | request-response | `triggarr/templates/dashboard.html` | role-match |
| `triggarr/web/routes.py` (add auth routes) | controller | request-response | `triggarr/web/routes.py` (save_settings) | exact |
| `triggarr/web/middleware.py` (add ?next=) | middleware | request-response | `triggarr/web/middleware.py` (line 122-123) | exact |
| `triggarr/templates/base.html` (logout link) | template | request-response | `triggarr/templates/base.html` (nav bar) | exact |
| `tests/test_auth_routes.py` | test | request-response | `tests/test_auth_middleware.py` | exact |

## Pattern Assignments

### `triggarr/templates/base-auth.html` (template, new)

**Analog:** `triggarr/templates/base.html`

**Head block pattern** (lines 1-14):
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Triggarr{% endblock %}</title>
  <link rel="icon" type="image/x-icon" href="{{ request.url_for('static', path='favicon.ico') }}">
  <link rel="icon" type="image/png" sizes="32x32" href="{{ request.url_for('static', path='favicon-32x32.png') }}">
  <link rel="icon" type="image/png" sizes="16x16" href="{{ request.url_for('static', path='favicon-16x16.png') }}">
  <link rel="apple-touch-icon" sizes="180x180" href="{{ request.url_for('static', path='apple-touch-icon.png') }}">
  <link rel="manifest" href="{{ request.url_for('static', path='site.webmanifest') }}">
  <link rel="stylesheet" href="{{ request.url_for('static', path='css/output.css') }}">
</head>
```

**Key difference from base.html:** No `<nav>`, no htmx script, no sidebar. Just `<head>` + centered `{% block content %}` on dark background. D-07 specifies standalone minimal layout.

**Static asset URL pattern:** Always use `request.url_for('static', path='...')` for root_path awareness (never hardcode `/static/`).

---

### `triggarr/web/routes.py` -- Auth Route Handlers (controller, modify)

**Analog:** `triggarr/web/routes.py` -- existing route handlers

**Imports pattern** (lines 1-42). Auth routes will need these additional imports:
```python
from triggarr.auth import (
    COOKIE_MAX_AGE,
    generate_api_key,
    generate_session_secret,
    hash_password,
    sign_session,
    validate_session,
    verify_password,
)
from triggarr.config import _atomic_toml_write, load_settings
from triggarr.models.config import AuthConfig
```

**GET route with TemplateResponse pattern** (lines 272-306):
```python
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the dashboard page with per-instance status cards and search log."""
    # ... build context ...
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "apps": apps,
            # ... more context vars ...
        },
    )
```

**POST form handler pattern** (lines 419-511):
```python
@router.post("/settings")
async def save_settings(request: Request) -> RedirectResponse:
    """Save settings from form data: write TOML, reload, update scheduler."""
    form = await request.form()
    current_settings = request.app.state.settings
    config_path = request.app.state.config_path
    # ... parse form fields ...

    # Validate BEFORE writing to disk
    try:
        new_settings = SettingsModel(**new_config)
    except pydantic.ValidationError as exc:
        logger.warning("Invalid settings rejected: {exc}", exc=exc)
        return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

    # Acquire search_lock to prevent races during config mutation
    async with request.app.state.search_lock:
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = new_settings
```

**Config write + reload pattern** (lines 506-511):
```python
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = new_settings
```

**`_settings_to_dict` pattern** (lines 140-154) -- must be extended to include auth section:
```python
def _settings_to_dict(settings: SettingsModel) -> dict:
    """Convert Settings to a plain dict suitable for TOML serialization."""
    result: dict = {"general": settings.general.model_dump()}
    for app_name in APP_TYPES:
        instances = getattr(settings, app_name)
        result[app_name] = {}
        for inst_name, cfg in instances.items():
            d = cfg.model_dump()
            d["api_key"] = cfg.api_key.get_secret_value()  # TOML serialization extraction
            result[app_name][inst_name] = d
    return result
```

**Jinja2 global variable pattern** (lines 53-58):
```python
templates.env.globals["triggarr_version"] = get_display_version()
update_info: dict = {}
templates.env.globals["update_info"] = update_info
```
Use this pattern for `auth_active` template variable to avoid modifying every existing route handler.

---

### `triggarr/web/middleware.py` -- ?next= Addition (middleware, modify)

**Analog:** `triggarr/web/middleware.py` line 122-123

**Current fallback redirect** (lines 121-124):
```python
# Step 7: Fallback -> redirect or 401
if self._is_browser(request):
    return RedirectResponse("/login", status_code=302)
return JSONResponse({"detail": "Authentication required"}, status_code=401)
```

**Cookie set pattern from Basic auth handler** (lines 148-156):
```python
response.set_cookie(
    "triggarr_session",
    session_value,
    max_age=COOKIE_MAX_AGE,
    httponly=True,
    samesite="lax",
    secure=True,
)
```
Copy these exact cookie attributes for login and setup session cookies.

---

### `triggarr/templates/base.html` -- Conditional Logout (template, modify)

**Analog:** `triggarr/templates/base.html` nav bar (lines 38-51)

**Nav items pattern** (lines 38-51):
```html
<div class="flex items-center gap-6 text-sm">
    <a href="{{ dashboard_url }}"
       class="{% if current_path == dashboard_url.path %}text-white border-b-2 border-triggarr-green pb-1 -mb-[7px]{% else %}text-triggarr-muted hover:text-white{% endif %}">
      Dashboard
    </a>
    <a href="{{ history_url }}" ...>History</a>
    <a href="{{ settings_url }}" ...>Settings</a>
</div>
```
Logout link goes inside this `<div>`, using POST form per D-10. Style with `text-triggarr-muted hover:text-white` to match nav items.

**Conditional rendering pattern** (lines 25-32, existing update_info conditional):
```html
{% if update_info and update_info.update_available %}
<a href="..." ...>v{{ update_info.latest_version }} available</a>
{% endif %}
```
Use similar pattern: `{% if auth_active %}` for logout visibility (D-11).

---

### `tests/test_auth_routes.py` (test, new)

**Analog:** `tests/test_auth_middleware.py`

**Test app factory pattern** (lines 22-51):
```python
def _make_auth_app(auth_config: AuthConfig | None = None) -> FastAPI:
    """Build a minimal FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    settings = MagicMock()
    settings.auth = auth_config or AuthConfig()
    app.state.settings = settings

    @app.get("/")
    async def index():
        return {"page": "home"}
    # ... more routes ...
    return app
```
The auth routes test will need a richer factory that includes the real router from routes.py, templates, and `app.state.config_path` + `app.state.search_lock`.

**Reusable auth config helper** (lines 64-78):
```python
def _configured_auth(
    method: str = "Forms",
    username: str = "admin",
    password_hash: str = _PASSWORD_HASH,
    api_key: str = _API_KEY,
    session_secret: str = _SESSION_SECRET,
) -> AuthConfig:
    """Create an AuthConfig with real credentials for testing."""
    return AuthConfig(
        method=method,
        username=username,
        password_hash=SecretStr(password_hash),
        api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret),
    )
```

**TestClient + redirect handling pattern** (lines 130-136):
```python
def test_needs_setup_browser_redirects_to_setup():
    client = TestClient(_make_auth_app(), follow_redirects=False)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert response.headers["location"] == "/setup"
```

**Import pattern** (lines 1-19):
```python
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session
from triggarr.models.config import AuthConfig
from triggarr.web.middleware import AuthMiddleware
```

---

## Shared Patterns

### Session Cookie Attributes
**Source:** `triggarr/web/middleware.py` lines 148-156
**Apply to:** POST /setup (auto-login), POST /login (login success)
```python
response.set_cookie(
    "triggarr_session",
    session_value,
    max_age=COOKIE_MAX_AGE,
    httponly=True,
    samesite="lax",
    secure=True,
)
```

### Atomic Config Write + Reload
**Source:** `triggarr/web/routes.py` lines 506-511
**Apply to:** POST /setup (persisting [auth] section)
```python
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, config_dict
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = load_settings(config_path)
```

### SecretStr Extraction for TOML
**Source:** `triggarr/web/routes.py` lines 140-154 (`_settings_to_dict`)
**Apply to:** `_settings_to_dict` extension for auth section, setup POST handler
```python
# Auth section must extract SecretStr manually:
auth_dict = {
    "method": auth.method,
    "username": auth.username,
    "password_hash": auth.password_hash.get_secret_value(),
    "api_key": auth.api_key.get_secret_value(),
    "session_secret": auth.session_secret.get_secret_value(),
}
```

### Jinja2 Global Variable
**Source:** `triggarr/web/routes.py` lines 53-58
**Apply to:** `auth_active` variable for conditional logout in base.html
```python
templates.env.globals["triggarr_version"] = get_display_version()
# Same pattern for auth_active -- use a callable so it reads live state:
# templates.env.globals["auth_active"] = ... (callable or dict reference)
```

### Loguru Logging (Never print/logging)
**Source:** Project convention (CLAUDE.md)
**Apply to:** All route handlers
```python
from loguru import logger
logger.info("Setup completed for user {username}", username=username)
logger.warning("Login failed for user {username}", username=username)
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have close analogs in the existing codebase |

## Metadata

**Analog search scope:** `triggarr/`, `tests/`
**Files scanned:** routes.py, middleware.py, auth.py, config.py, models/config.py, base.html, test_auth_middleware.py
**Pattern extraction date:** 2026-04-14
