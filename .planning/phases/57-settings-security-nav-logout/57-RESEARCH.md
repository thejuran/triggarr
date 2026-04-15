# Phase 57: Settings Security & Nav Logout - Research

**Researched:** 2026-04-14
**Domain:** FastAPI + htmx settings UI, password/API key management, auth mode switching
**Confidence:** HIGH

## Summary

Phase 57 adds a Security section to the existing Settings page with three functional areas: auth method switching (Forms/Basic/External dropdown), password change (current + new + confirm), and API key management (masked display, copy, regenerate). The phase also implements a disabled-auth warning banner. All backend helpers already exist (`hash_password`, `verify_password`, `generate_api_key` in `triggarr/auth.py`), the config model (`AuthConfig`) is complete, and `_settings_to_dict` already serializes auth fields. The main work is: (1) new POST endpoints for password change, security save, and API key regeneration, (2) htmx partial templates for inline re-rendering, (3) the Security section HTML in `settings.html`, and (4) tests.

The existing Settings page uses a single `<form>` wrapping General + per-app sections with one Save button. The Security section must be a **separate form** outside this existing form (D-02) with its own Save button for auth mode. The password change submits via htmx `hx-post` to a dedicated endpoint (D-06). API key regeneration is a separate POST with inline confirmation (D-08).

**Primary recommendation:** Add three new POST endpoints (`/settings/password`, `/settings/security`, `/settings/api-key/regenerate`), two htmx partial templates (`partials/security_password.html`, `partials/security_apikey.html`), and insert the Security section into `settings.html` between General and app sections. Follow the established pattern of `_settings_to_dict` -> `_atomic_toml_write` -> `_sync_auth_state` for all config mutations.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Security section appears after General, before app instance sections on the Settings page
- **D-02:** Security section uses a separate form from the existing settings form. Own Save button, own validation
- **D-03:** Disabled-auth warning banner appears at the top of the entire Settings page, above all sections. Full-width red banner
- **D-04:** Validation errors shown inline per-field -- red text below the specific field that failed
- **D-05:** After successful password change: green success message, all three password fields clear. No page reload
- **D-06:** Password form submits via htmx partial submit (hx-post) to a dedicated endpoint. Only the password section re-renders
- **D-07:** API key displayed as fully masked by default with eye icon toggle to reveal. Copy button works regardless of visibility
- **D-08:** Regenerating API key requires confirmation dialog -- inline warning with Confirm/Cancel buttons
- **D-09:** After regeneration: inline replacement -- key field updates in-place with new key fully visible, green "Key regenerated" message
- **D-10:** Auth mode change takes effect on save, next request. Config writes to TOML, middleware picks up new mode
- **D-11:** Inline contextual warnings appear below the dropdown when a mode is selected (External/Basic show warnings, Forms no warning)
- **D-12:** Auth mode dropdown is part of a combined Security save -- one Save button for auth mode
- **D-13:** Dropdown only offers Forms/Basic/External -- no Disabled option in the UI. Disabled mode is config-file-only

### Claude's Discretion
- Exact htmx attributes and swap targets for password and API key partials
- Whether auth mode save and API key regenerate use the same endpoint or separate ones
- Confirmation dialog implementation (htmx inline expand vs JS modal)
- How the eye toggle and copy button are implemented (vanilla JS, matches setup page pattern)
- CSS/layout details within the AIDesigner design

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SET-01 | User can change auth method (Forms/Basic/External) from the Settings security section | Auth mode dropdown in Security section, POST `/settings/security` writes method to TOML via `_atomic_toml_write`, `_sync_auth_state` updates middleware behavior |
| SET-02 | User can change password via current + new + confirm form in Settings | Password change form with htmx POST to `/settings/password`, uses `verify_password` + `hash_password` from `triggarr/auth.py`, inline error/success via partial re-render |
| SET-03 | User can view (masked), copy, and regenerate the API key from Settings | Masked display with eye toggle (vanilla JS), copy via `navigator.clipboard.writeText` (setup.html pattern), regenerate via POST `/settings/api-key/regenerate` with inline confirm |
| SET-04 | User sees a warning banner in Settings if auth is disabled via config file | Full-width red banner at top of settings page, conditional on `settings.auth.is_disabled`, explains config-file-only re-enable |
| LOGIN-05 | User can disable auth via config file only (not UI), with startup warning logged every 60s | Dropdown omits "Disabled" option (D-13); banner (SET-04) explains config-file-only. Startup warning already implemented in Phase 54/55 |
| UI-03 | Settings security section generated via AIDesigner as HTML artifact; implementation matches pixel-exact | Use AIDesigner MCP to generate Security section HTML, then port pixel-exact into `settings.html` Jinja2 template |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password change validation | API / Backend | -- | Current password verification must happen server-side (bcrypt) |
| Auth mode persistence | API / Backend | -- | TOML config write + middleware reload is purely server-side |
| API key regeneration | API / Backend | -- | CSPRNG key generation and config write are server-side |
| API key masking/reveal | Browser / Client | -- | Eye toggle is purely visual, JS only |
| API key clipboard copy | Browser / Client | -- | navigator.clipboard.writeText is browser API |
| Inline form submission | Browser / Client | API / Backend | htmx sends POST, server returns partial HTML |
| Mode-switch warnings | Browser / Client | -- | JavaScript onChange shows/hides static warning text |
| Disabled-auth banner | Frontend Server (SSR) | -- | Jinja2 conditional rendering based on `auth.is_disabled` |

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (project dep) | Route handlers for new POST endpoints | Already used for all routes |
| htmx | (static/js/htmx.min.js) | Partial form submission and inline swap | Already loaded in base.html |
| Jinja2 | (project dep) | Template rendering for partials and Security section | Already used for all templates |
| bcrypt | (project dep) | Password hashing via `hash_password`/`verify_password` | Already in auth.py |
| Pydantic | (project dep) | Config validation before TOML write | Already validates all settings |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| itsdangerous | (transitive) | Session cookie signing after password change | Already used for session management |
| tomli-w | (project dep) | Atomic TOML config writes | Already used via `_atomic_toml_write` |

**No new dependencies required.** All needed libraries are already installed. [VERIFIED: pyproject.toml inspection]

## Architecture Patterns

### System Architecture Diagram

```
User clicks Save/Submit in Security section
  |
  v
htmx hx-post (partial submit)
  |
  +--> POST /settings/password
  |      |-> verify_password(current, stored_hash)
  |      |-> hash_password(new_password)
  |      |-> _settings_to_dict() -> _atomic_toml_write()
  |      |-> reload settings, _sync_auth_state()
  |      |-> return partials/security_password.html (success/error)
  |
  +--> POST /settings/security
  |      |-> validate auth method (Forms/Basic/External only)
  |      |-> _settings_to_dict() -> _atomic_toml_write()
  |      |-> reload settings, _sync_auth_state()
  |      |-> redirect to /settings (full page)
  |
  +--> POST /settings/api-key/regenerate
         |-> generate_api_key()
         |-> _settings_to_dict() -> _atomic_toml_write()
         |-> reload settings
         |-> return partials/security_apikey.html (new key visible)
```

### Recommended Project Structure (additions only)

```
triggarr/
├── templates/
│   ├── settings.html               # MODIFY: add Security section + disabled banner
│   └── partials/
│       ├── security_password.html   # NEW: htmx swap target for password form
│       └── security_apikey.html     # NEW: htmx swap target for API key section
├── web/
│   └── routes.py                    # MODIFY: add 3 new POST endpoints
└── auth.py                          # EXISTING: no changes needed
```

### Pattern 1: htmx Partial Form Submission (password change)

**What:** Password form submits via `hx-post` to a dedicated endpoint that returns only the password section HTML (not the full page). This enables inline error/success without page reload.

**When to use:** Any form that needs inline validation feedback (D-04, D-05, D-06).

**Example:**
```html
<!-- In settings.html -->
<div id="password-section">
  {% include "partials/security_password.html" %}
</div>
```

```html
<!-- partials/security_password.html -->
<form hx-post="{{ request.url_for('change_password') }}"
      hx-target="#password-section"
      hx-swap="innerHTML">
  <div>
    <label class="block text-sm text-triggarr-muted mb-1">Current Password</label>
    <input type="password" name="current_password" autocomplete="current-password"
           class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
    {% if errors and errors.current_password %}
    <p class="text-red-500 text-sm mt-1" aria-live="polite">{{ errors.current_password }}</p>
    {% endif %}
  </div>
  <!-- new_password, confirm_password similar -->
  {% if success %}
  <p class="text-green-500 text-sm mt-2">{{ success }}</p>
  {% endif %}
  <button type="submit" class="bg-triggarr-green ...">Change Password</button>
</form>
```
[VERIFIED: matches existing setup.html error pattern and htmx usage in base.html]

### Pattern 2: Config Mutation (save_settings established pattern)

**What:** All config changes follow the same pattern: build dict -> validate with Pydantic -> atomic TOML write -> update `app.state.settings` -> `_sync_auth_state()`.

**When to use:** All three new endpoints.

**Example:**
```python
@router.post("/settings/password")
async def change_password(request: Request) -> HTMLResponse:
    form = await request.form()
    settings = request.app.state.settings
    auth = settings.auth
    
    # Validate current password
    current = form.get("current_password", "")
    if not verify_password(current, auth.password_hash.get_secret_value()):
        return templates.TemplateResponse(
            request=request,
            name="partials/security_password.html",
            context={"errors": {"current_password": "Current password is incorrect"}},
        )
    
    # Validate new password
    new_pw = form.get("new_password", "")
    confirm = form.get("confirm_password", "")
    if new_pw != confirm:
        return templates.TemplateResponse(...)
    
    # Mutate config atomically
    new_hash = hash_password(new_pw)
    config_dict = _settings_to_dict(settings)
    config_dict["auth"]["password_hash"] = new_hash
    new_settings = SettingsModel(**config_dict)
    
    async with request.app.state.search_lock:
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
        )
        request.app.state.settings = new_settings
        _sync_auth_state(new_settings)
    
    return templates.TemplateResponse(
        request=request,
        name="partials/security_password.html",
        context={"success": "Password updated"},
    )
```
[VERIFIED: follows exact pattern from save_settings at routes.py:478-570]

### Pattern 3: Clipboard Copy (from setup.html)

**What:** Copy API key to clipboard with visual feedback.

**Example:**
```javascript
function copyApiKey(btn) {
    var key = document.getElementById('api-key-value').dataset.key;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(key).then(function() {
            btn.textContent = 'Copied!';
            setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
        });
    } else {
        // Fallback for non-secure contexts
        var range = document.createRange();
        range.selectNodeContents(document.getElementById('api-key-value'));
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        document.execCommand('copy');
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
    }
}
```
[VERIFIED: directly from setup.html lines 71-88]

### Pattern 4: Eye Toggle for API Key Masking

**What:** Toggle between masked dots and actual key value using vanilla JS. The actual key value is stored in a `data-key` attribute and the display toggles between masked and revealed.

**Example:**
```javascript
function toggleApiKeyVisibility(btn) {
    var display = document.getElementById('api-key-display');
    var key = display.dataset.key;
    if (display.dataset.revealed === 'true') {
        display.textContent = '\u2022'.repeat(32);
        display.dataset.revealed = 'false';
    } else {
        display.textContent = key;
        display.dataset.revealed = 'true';
    }
}
```
[ASSUMED: standard pattern, no existing eye toggle in codebase to reference]

### Anti-Patterns to Avoid
- **Nested `<form>` tags:** The existing settings page has one `<form>` wrapping General + app sections. The Security section form MUST be placed outside this form. Check the existing pattern at the bottom of settings.html (lines 189-191) where add-instance forms are placed outside the main form.
- **Full page reload for password change:** D-06 explicitly requires htmx partial submit. Do not use a standard form POST with redirect.
- **Exposing API key in page source:** The API key should be passed as a `data-*` attribute or loaded via htmx, but it IS part of the authenticated Settings page so this is acceptable. The key must still follow SecretStr discipline -- only extract `.get_secret_value()` at the template rendering boundary.
- **Modifying auth.py:** The helpers are complete. Do not add new functions there unless strictly necessary.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom hash function | `hash_password()` / `verify_password()` from `triggarr/auth.py` | bcrypt with 12 rounds, already tested |
| API key generation | Custom random string | `generate_api_key()` from `triggarr/auth.py` | CSPRNG via `secrets.token_hex(16)`, already tested |
| Atomic config write | Direct file write | `_atomic_toml_write()` from `triggarr/config.py` | fsync + rename pattern, handles failures cleanly |
| Config serialization | Manual dict building | `_settings_to_dict()` from `triggarr/web/routes.py` | Handles SecretStr extraction correctly |
| Auth state sync | Manual template variable setting | `_sync_auth_state()` from `triggarr/web/routes.py` | Updates nav bar logout visibility |
| CSRF protection | Token-based CSRF | `OriginCheckMiddleware` already active | Validates Origin/Referer on all POST requests |
| Clipboard copy | Custom clipboard logic | Existing pattern from setup.html | navigator.clipboard.writeText with fallback |

**Key insight:** Every backend operation needed for this phase already has a tested helper function. The phase is primarily about wiring these helpers into new endpoints and building the template UI.

## Common Pitfalls

### Pitfall 1: Nested Form Tags
**What goes wrong:** Placing the Security `<form>` inside the existing settings `<form>` creates invalid HTML. Browsers handle nested forms unpredictably -- inner form submissions may submit the outer form's data.
**Why it happens:** The Security section visually sits between General and app sections, tempting developers to insert it inside the existing form.
**How to avoid:** Close the existing `<form>` before the Security section, or restructure: place the Security section HTML outside the main form (like the add-instance forms at lines 189-191 of settings.html). The cleanest approach: end the main form after General, render Security section with its own form, then start per-app sections outside any form (they're part of the main settings form which wraps them).
**Warning signs:** Browser devtools showing form nesting warnings; htmx submissions sending unexpected fields.

### Pitfall 2: Race Condition on Config Write
**What goes wrong:** Two concurrent config mutations (e.g., password change + general settings save) can cause lost writes.
**Why it happens:** Both operations read settings, modify, and write. Without locking, one overwrites the other.
**How to avoid:** Always acquire `request.app.state.search_lock` before writing config, matching the pattern in `save_settings` (line 564). The existing lock is already used for all config mutations.
**Warning signs:** Config reverting after save; auth settings disappearing after general settings save.

### Pitfall 3: SecretStr Leaking into Templates
**What goes wrong:** Passing `auth.api_key` directly to a template renders as `SecretStr('**********')` instead of the actual value.
**Why it happens:** Pydantic SecretStr's `__str__` method is deliberately opaque.
**How to avoid:** Extract with `.get_secret_value()` at the template context boundary in the route handler. Pass the plain string to the template. This is consistent with CLAUDE.md: "call `.get_secret_value()` only at HTTP client init" -- template rendering is an equivalent extraction point.
**Warning signs:** Template showing literal `SecretStr(...)` text.

### Pitfall 4: Auth Mode Save Without Preserving Other Auth Fields
**What goes wrong:** Saving just the auth method clobbers password_hash, api_key, session_secret.
**Why it happens:** Building a partial config dict for the auth section without including all existing fields.
**How to avoid:** Always use `_settings_to_dict(settings)` as the base, then modify only the changed field. Reconstruct the full Settings model before writing.
**Warning signs:** Password stops working after changing auth method; API key changes unexpectedly.

### Pitfall 5: Forgetting _sync_auth_state After Config Change
**What goes wrong:** Nav bar logout link visibility doesn't update after auth mode change.
**Why it happens:** `_sync_auth_state` must be called after every settings mutation that touches auth config.
**How to avoid:** Add `_sync_auth_state(new_settings)` after every `request.app.state.settings = new_settings` assignment, matching the pattern in `save_settings` (line 570).
**Warning signs:** Logout link appearing/disappearing only after page refresh.

## Code Examples

### Settings Page GET Handler (adding auth context)
```python
# In settings_page(), add to template context:
auth = settings.auth
context = {
    # ... existing context ...
    "auth_method": auth.method,
    "auth_is_disabled": auth.is_disabled,
    "auth_api_key": auth.api_key.get_secret_value(),  # SecretStr extraction at template boundary
    "auth_username": auth.username,
}
```
[VERIFIED: follows pattern from settings_page at routes.py:368-400]

### Security Section Template Structure
```html
<!-- Disabled-auth warning banner (D-03) - ABOVE all sections -->
{% if auth_is_disabled %}
<div class="bg-red-900/30 border border-red-500/50 rounded-lg p-4 mb-6">
  <p class="text-red-400 text-sm font-medium">Authentication is disabled</p>
  <p class="text-red-400/70 text-xs mt-1">
    Auth mode is set to Disabled in the config file. 
    To re-enable, edit triggarr.toml and change method to "Forms", "Basic", or "External".
  </p>
</div>
{% endif %}

<!-- Security section (D-01: after General, before app sections) -->
<!-- This form is OUTSIDE the main settings form (D-02) -->
<section class="bg-triggarr-card rounded-lg border border-triggarr-border p-5">
  <h2 class="text-lg font-semibold mb-4">Security</h2>
  
  <!-- Auth Method (D-10, D-11, D-12, D-13) -->
  <form method="post" action="{{ request.url_for('save_security') }}">
    <div class="max-w-md">
      <label class="block text-sm text-triggarr-muted mb-1">Authentication Method</label>
      <select name="auth_method" onchange="updateMethodWarning(this.value)"
              class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
        {% for mode in ['Forms', 'Basic', 'External'] %}
        <option value="{{ mode }}" {% if auth_method == mode %}selected{% endif %}>{{ mode }}</option>
        {% endfor %}
      </select>
      <div id="method-warning" class="text-yellow-500 text-xs mt-1" style="display:none"></div>
    </div>
    <div class="flex justify-end mt-4">
      <button type="submit" class="bg-triggarr-green hover:bg-triggarr-green-dark text-white font-medium px-4 py-2 rounded text-sm transition-colors">
        Save
      </button>
    </div>
  </form>
  
  <hr class="border-triggarr-border my-5">
  
  <!-- Password Change (D-04, D-05, D-06) -->
  <div id="password-section">
    {% include "partials/security_password.html" %}
  </div>
  
  <hr class="border-triggarr-border my-5">
  
  <!-- API Key Management (D-07, D-08, D-09) -->
  <div id="apikey-section">
    {% include "partials/security_apikey.html" %}
  </div>
</section>
```
[VERIFIED: card styling matches existing sections in settings.html; form placement follows add-instance form pattern]

### Auth Method Warning JavaScript (D-11)
```javascript
function updateMethodWarning(value) {
    var el = document.getElementById('method-warning');
    if (value === 'External') {
        el.textContent = 'Login page will be bypassed. Ensure your reverse proxy handles auth.';
        el.style.display = 'block';
    } else if (value === 'Basic') {
        el.textContent = 'Browser will show a native popup instead of the login page.';
        el.style.display = 'block';
    } else {
        el.style.display = 'none';
    }
}
```
[ASSUMED: standard vanilla JS pattern, no existing equivalent in codebase]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full page reload for form validation | htmx partial swap (`hx-post` + `hx-target`) | Already in use | Enables inline errors (D-04) without page reload (D-05) |
| Single monolithic settings form | Separate forms per concern (D-02) | This phase | Prevents nested form issues, enables independent validation |
| Visible API keys in settings | Masked by default with toggle (D-07) | This phase | Follows *arr convention for credential display |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Eye toggle icon implementation uses vanilla JS toggle between masked dots and data-key attribute | Architecture Patterns, Pattern 4 | Low -- implementation detail, easily adjusted |
| A2 | Auth method warnings use JavaScript onChange handler on the select element | Code Examples | Low -- could also be htmx-driven but JS is simpler for static text |
| A3 | The search_lock should be acquired for auth config mutations (password, method, API key) | Common Pitfalls | Medium -- all existing config mutations use this lock, but auth-only changes may not conflict with search jobs. Safer to use it consistently |

## Open Questions

1. **Form structure in settings.html**
   - What we know: The existing settings page wraps General + per-app sections in a single `<form>`. Security section needs its own form (D-02). Add-instance forms are placed after the main form (lines 189-191).
   - What's unclear: Best way to restructure -- should the main form close before Security section (splitting General from apps), or should Security section go entirely below the main form but be visually positioned between General and apps via CSS order?
   - Recommendation: End the existing `<form>` after General section. Place Security section with its own forms. Then start a new `<form>` for per-app sections + main Save button. This keeps DOM order matching visual order without CSS tricks.

2. **Settings page GET handler -- should it pass auth context even when auth is disabled?**
   - What we know: `auth.is_disabled` is `True` when method is "Disabled". The Security section should still render (showing the disabled banner + current settings) so users can see the state.
   - What's unclear: Should the password change and API key management be interactive when auth is disabled?
   - Recommendation: Show the Security section with all controls functional. If auth is disabled, the user can still change password and regenerate API key (these affect config, not enforcement). The warning banner covers the UX.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ with pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_auth_routes.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SET-01 | Auth method change via POST /settings/security | integration | `uv run pytest tests/test_auth_routes.py -x -q -k test_security_save_method` | Wave 0 |
| SET-02 | Password change via POST /settings/password (valid + invalid current) | integration | `uv run pytest tests/test_auth_routes.py -x -q -k test_change_password` | Wave 0 |
| SET-03 | API key view/copy/regenerate via POST /settings/api-key/regenerate | integration | `uv run pytest tests/test_auth_routes.py -x -q -k test_regenerate_api_key` | Wave 0 |
| SET-04 | Warning banner visible when auth disabled | integration | `uv run pytest tests/test_auth_routes.py -x -q -k test_settings_disabled_banner` | Wave 0 |
| LOGIN-05 | No "Disabled" option in UI dropdown | integration | `uv run pytest tests/test_auth_routes.py -x -q -k test_settings_no_disabled_option` | Wave 0 |
| UI-03 | Security section pixel-exact from AIDesigner | manual-only | Visual comparison with AIDesigner artifact | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth_routes.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Add settings security tests to `tests/test_auth_routes.py` -- covers SET-01, SET-02, SET-03, SET-04, LOGIN-05

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | bcrypt hashing via `hash_password`, verify via `verify_password` -- existing helpers |
| V3 Session Management | yes | itsdangerous signed cookies, 30-day max age -- existing implementation |
| V4 Access Control | yes | AuthMiddleware deny-all + whitelist -- existing middleware |
| V5 Input Validation | yes | Pydantic model validation before config write; form field sanitization |
| V6 Cryptography | yes | bcrypt (password), secrets.token_hex (API key/session) -- never hand-rolled |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Password change without verifying current password | Elevation of Privilege | Always require and verify current password before accepting new hash |
| API key exposure in page source | Information Disclosure | Key in data attribute is acceptable (authenticated page); but never log it (loguru redacting sink) |
| Auth method downgrade to Disabled via POST | Tampering | Endpoint MUST validate method is in (Forms, Basic, External) only -- reject "Disabled" |
| CSRF on settings POST endpoints | Tampering | OriginCheckMiddleware validates Origin/Referer on all POST requests -- already active |
| Timing oracle on password verification | Information Disclosure | bcrypt.checkpw is constant-time -- already handled by verify_password |

## Project Constraints (from CLAUDE.md)

- **SecretStr:** All API keys use SecretStr; call `.get_secret_value()` only at HTTP client init or template rendering boundary
- **Loguru:** Never use print() or logging module; use loguru with redacting sink
- **Atomic writes:** All config writes use write-then-rename pattern (`_atomic_toml_write`)
- **Ruff linting:** E, F, I, UP, B, SIM rules; line length 120
- **pytest-asyncio:** asyncio_mode=auto
- **Pydantic validation:** Validate before any config write
- **AIDesigner pixel-exact:** UI-03 requires AIDesigner HTML artifact as hard spec

## Sources

### Primary (HIGH confidence)
- `triggarr/web/routes.py` -- settings_page, save_settings, _settings_to_dict, _sync_auth_state patterns
- `triggarr/auth.py` -- hash_password, verify_password, generate_api_key implementations
- `triggarr/models/config.py` -- AuthConfig model, Settings model
- `triggarr/templates/settings.html` -- existing settings page structure and CSS patterns
- `triggarr/templates/setup.html` -- clipboard copy pattern, error display pattern
- `triggarr/web/middleware.py` -- AuthMiddleware auth check order
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- design spec for Settings UI
- `CLAUDE.md` -- project conventions

### Secondary (MEDIUM confidence)
- `triggarr/templates/base.html` -- nav bar logout link (auth_state conditional)
- `triggarr/config.py` -- _atomic_toml_write, load_settings

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all dependencies already installed and verified in pyproject.toml
- Architecture: HIGH - all patterns established in existing codebase, no new patterns needed
- Pitfalls: HIGH - identified from direct code inspection of existing settings save flow

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable -- existing codebase patterns, no external dependencies)
