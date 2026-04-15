# Phase 57: Settings Security & Nav Logout - Pattern Map

**Mapped:** 2026-04-14
**Files analyzed:** 6 (new/modified)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/web/routes.py` (modify: add 3 POST endpoints) | controller | request-response | `triggarr/web/routes.py` `setup_post()` (line 1017) | exact |
| `triggarr/templates/settings.html` (modify: add Security section + banner) | component | SSR render | `triggarr/templates/settings.html` General section (lines 10-72) | exact |
| `triggarr/templates/partials/security_password.html` (new) | component | request-response (htmx swap) | `triggarr/templates/setup.html` form + errors (lines 14-50) | exact |
| `triggarr/templates/partials/security_apikey.html` (new) | component | request-response (htmx swap) | `triggarr/templates/setup.html` success state (lines 53-88) | role-match |
| `triggarr/web/routes.py` (modify: settings_page GET context) | controller | request-response | `triggarr/web/routes.py` `settings_page()` (line 367) | exact |
| `tests/test_auth_routes.py` (modify: add security settings tests) | test | integration | `tests/test_auth_routes.py` setup/login tests (lines 227-425) | exact |

## Pattern Assignments

### POST `/settings/password` endpoint (controller, request-response)

**Analog:** `triggarr/web/routes.py` `setup_post()` lines 1017-1096

**Imports pattern** (lines 1-50 of routes.py):
```python
# Already imported -- no new imports needed for password change endpoint
# Uses: asyncio, os, Request, HTMLResponse, SecretStr, templates
# Uses: hash_password, verify_password from triggarr.auth
# Uses: _atomic_toml_write, load_settings from triggarr.config
# Uses: _settings_to_dict, _sync_auth_state (module-level)
```

**Form validation pattern** (setup_post lines 1023-1041):
```python
form = await request.form()
username = form.get("username", "").strip()
password = form.get("password", "")
confirm = form.get("confirm_password", "")

errors: dict[str, str] = {}
if not username:
    errors["username"] = "Username is required"
if not password:
    errors["password"] = "Password is required"
elif password != confirm:
    errors["confirm_password"] = "Passwords do not match"

if errors:
    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"setup_complete": False, "errors": errors, "username": username},
    )
```

**Config mutation pattern** (setup_post lines 1056-1074):
```python
config_path = request.app.state.config_path
async with request.app.state.search_lock:
    current_settings = request.app.state.settings
    updated = current_settings.model_copy(update={"auth": new_auth})
    config_dict = _settings_to_dict(updated)
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, config_dict
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = load_settings(config_path)

_sync_auth_state(request.app.state.settings)
```

**Post-mutation log redaction refresh** (setup_post lines 1077-1078):
```python
_new_secrets = collect_secrets(request.app.state.settings)
setup_logging(request.app.state.settings.general.log_level, _new_secrets)
```

---

### POST `/settings/security` endpoint (controller, request-response)

**Analog:** `triggarr/web/routes.py` `save_settings()` lines 477-570

**Config save with Pydantic validation pattern** (save_settings lines 553-570):
```python
# Validate BEFORE writing to disk (QUAL-02)
try:
    new_settings = SettingsModel(**new_config)
except pydantic.ValidationError as exc:
    logger.warning("Invalid settings rejected: {exc}", exc=exc)
    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

# Acquire search_lock to prevent races
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = new_settings
    _sync_auth_state(new_settings)
```

**Method validation constraint** (D-13: no Disabled in UI):
```python
# Must reject "Disabled" -- only Forms/Basic/External allowed via POST
ALLOWED_METHODS = {"Forms", "Basic", "External"}
```

---

### POST `/settings/api-key/regenerate` endpoint (controller, request-response)

**Analog:** `triggarr/web/routes.py` `setup_post()` lines 1043-1074 (credential generation + persist)

**Key generation pattern** (setup_post lines 1044-1046):
```python
api_key = generate_api_key()
```

**Partial template return pattern** (for htmx swap):
```python
return templates.TemplateResponse(
    request=request,
    name="partials/security_apikey.html",
    context={"api_key": new_api_key, "revealed": True, "success": "Key regenerated"},
)
```

---

### `triggarr/templates/settings.html` modification (component, SSR)

**Analog:** `triggarr/templates/settings.html` lines 8-72 (General section card pattern)

**Section card pattern** (lines 10-72):
```html
<section class="bg-triggarr-card rounded-lg border border-triggarr-border p-5">
    <h2 class="text-lg font-semibold mb-4">General</h2>
    <div class="grid grid-cols-1 gap-4 max-w-md">
        <div>
            <label class="block text-sm text-triggarr-muted mb-1">Log Level</label>
            <select name="log_level"
                    class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
                {% for level in ['debug', 'info', 'warning', 'error'] %}
                <option value="{{ level }}" {% if log_level == level %}selected{% endif %}>
                    {{ level | capitalize }}
                </option>
                {% endfor %}
            </select>
        </div>
    </div>
</section>
```

**Form input pattern** (line 28):
```html
<input type="number" name="hard_max_per_cycle" value="{{ hard_max_per_cycle }}"
       min="0" max="1000"
       class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
```

**External form pattern** (lines 188-191 -- forms outside main form to avoid nesting):
```html
<!-- Add-instance forms must live outside the main settings form to avoid nested <form> (illegal in HTML) -->
{% for app_name in apps %}
<form id="add-{{ app_name }}" method="post" action="{{ request.url_for('add_instance') }}"></form>
{% endfor %}
```

**htmx include pattern** (from `triggarr/templates/partials/health_summary.html` lines 1-5):
```html
<div id="health-summary"
     hx-get="{{ request.url_for('partial_health_summary') }}"
     hx-trigger="every 30s"
     hx-swap="outerHTML">
```

---

### `triggarr/templates/partials/security_password.html` (new component, htmx swap)

**Analog:** `triggarr/templates/setup.html` lines 14-50

**Form with inline error pattern** (setup.html lines 14-50):
```html
<form method="post" action="{{ request.url_for('setup_post') }}" class="mt-6">
  <div class="space-y-4">
    <div>
      <label for="username" class="block text-sm font-medium text-triggarr-muted mb-1">Username</label>
      <input type="text" id="username" name="username"
             value="{{ username | default('admin', true) }}"
             autocomplete="username"
             class="bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm text-triggarr-text placeholder-triggarr-muted w-full focus:ring-2 focus:ring-triggarr-green focus:outline-none">
      {% if errors and errors.username %}
      <p class="text-red-500 text-sm mt-1" aria-live="polite">{{ errors.username }}</p>
      {% endif %}
    </div>
  </div>
  <button type="submit"
          class="w-full bg-triggarr-green hover:bg-triggarr-green-dark text-white text-sm font-medium rounded py-2 mt-6 transition-colors cursor-pointer">
    Create Account
  </button>
</form>
```

**Key adaptation for htmx:** Replace `method="post" action="..."` with `hx-post="..." hx-target="#password-section" hx-swap="innerHTML"`.

**Success message pattern** (D-05):
```html
{% if success %}
<p class="text-green-500 text-sm mt-2">{{ success }}</p>
{% endif %}
```

---

### `triggarr/templates/partials/security_apikey.html` (new component, htmx swap)

**Analog:** `triggarr/templates/setup.html` lines 53-88

**API key display + clipboard copy pattern** (setup.html lines 57-88):
```html
<code id="api-key-display"
      class="block w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm text-triggarr-text select-all mt-6">{{ api_key }}</code>

<button type="button" onclick="copyApiKey(this)"
        class="mt-2 bg-triggarr-card-elevated border border-triggarr-border rounded px-3 py-1 text-sm text-triggarr-text hover:text-white transition-colors cursor-pointer">
  Copy
</button>

<script>
  function copyApiKey(btn) {
      var text = document.getElementById('api-key-display').textContent;
      if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(function() {
              btn.textContent = 'Copied!';
              setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
          });
      } else {
          var range = document.createRange();
          range.selectNodeContents(document.getElementById('api-key-display'));
          window.getSelection().removeAllRanges();
          window.getSelection().addRange(range);
          document.execCommand('copy');
          btn.textContent = 'Copied!';
          setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
      }
  }
</script>
```

**Key adaptation:** Add `data-key` attribute for masked/revealed toggle; copy reads from `dataset.key` instead of `textContent`.

---

### `triggarr/web/routes.py` settings_page GET modification (controller, request-response)

**Analog:** `triggarr/web/routes.py` `settings_page()` lines 367-400

**Template context pattern** (lines 386-400):
```python
return templates.TemplateResponse(
    request=request,
    name="settings.html",
    context={
        "apps": apps,
        "log_level": settings.general.log_level,
        "hard_max_per_cycle": settings.general.hard_max_per_cycle,
        # ... existing context ...
    },
)
```

**Auth context additions** (extract SecretStr at template boundary):
```python
# Add to context dict:
"auth_method": settings.auth.method,
"auth_is_disabled": settings.auth.is_disabled,
"auth_api_key": settings.auth.api_key.get_secret_value(),
"auth_username": settings.auth.username,
```

---

### `tests/test_auth_routes.py` modification (test, integration)

**Analog:** `tests/test_auth_routes.py` lines 227-425

**Test app factory pattern** (lines 66-92):
```python
def _make_route_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    static_dir = Path(__file__).resolve().parent.parent / "triggarr" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    cfg = auth_config or AuthConfig()
    settings = SettingsModel.model_construct(
        general=GeneralConfig(),
        auth=cfg,
        radarr={},
        sonarr={},
        lidarr={},
    )
    app.state.settings = settings
    app.state.config_path = config_path or Path("/tmp/test-triggarr.toml")
    app.state.search_lock = asyncio.Lock()
    auth_state["active"] = cfg.method in ("Forms", "Basic") and not cfg.needs_setup
    auth_state["method"] = cfg.method
    return app
```

**Integration test pattern** (test_setup_post_creates_credentials lines 244-264):
```python
def test_setup_post_creates_credentials(tmp_path: Path):
    """POST /setup with valid credentials creates account and shows API key."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general]\nlog_level = \"info\"\n")

    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "test123", "confirm_password": "test123"},
    )
    assert response.status_code == 200
    assert "Account Created" in response.text
```

**Auth cookie test helper** (lines 43-47):
```python
_TEST_PASSWORD = "testpass123"
_TEST_PASSWORD_HASH = hash_password(_TEST_PASSWORD)
_TEST_SESSION_SECRET = generate_session_secret()
_TEST_API_KEY = "a" * 32
```

**Authenticated request pattern** (line 344-345):
```python
cookie = sign_session("admin", _TEST_SESSION_SECRET)
response = client.get("/login", cookies={"triggarr_session": cookie})
```

## Shared Patterns

### Config Mutation Sequence
**Source:** `triggarr/web/routes.py` lines 1056-1078 (setup_post)
**Apply to:** All three new POST endpoints (`/settings/password`, `/settings/security`, `/settings/api-key/regenerate`)

Every config mutation must follow this exact sequence:
1. Acquire `request.app.state.search_lock`
2. Read current settings from `request.app.state.settings`
3. Build updated settings via `model_copy(update={...})` or reconstruct from `_settings_to_dict`
4. Write via `_atomic_toml_write`
5. `os.chmod(config_path, 0o600)`
6. Reload: `request.app.state.settings = load_settings(config_path)`
7. `_sync_auth_state(request.app.state.settings)`
8. Refresh log redaction: `collect_secrets` + `setup_logging`

### Inline Error Display
**Source:** `triggarr/templates/setup.html` lines 23-25
**Apply to:** `partials/security_password.html`
```html
{% if errors and errors.field_name %}
<p class="text-red-500 text-sm mt-1" aria-live="polite">{{ errors.field_name }}</p>
{% endif %}
```

### Form Input Styling
**Source:** `triggarr/templates/settings.html` lines 15-16, 27-28
**Apply to:** All new form fields in Security section
```
Input: class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm"
Label: class="block text-sm text-triggarr-muted mb-1"
Select: class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm"
```

### Save Button Styling
**Source:** `triggarr/templates/settings.html` lines 181-184
**Apply to:** Security section Save button, Change Password button
```html
<button type="submit"
        class="bg-triggarr-green hover:bg-triggarr-green-dark text-white font-medium px-4 py-2 rounded text-sm transition-colors">
    Save
</button>
```

### SecretStr Extraction Boundary
**Source:** `triggarr/web/routes.py` `_settings_to_dict()` lines 189-212
**Apply to:** settings_page GET handler (auth context), API key regenerate endpoint
```python
# Extract .get_secret_value() only at template rendering boundary or TOML write
auth.api_key.get_secret_value()
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have close analogs in the existing codebase |

## Metadata

**Analog search scope:** `triggarr/web/`, `triggarr/templates/`, `triggarr/auth.py`, `tests/`
**Files scanned:** 15+
**Pattern extraction date:** 2026-04-14
