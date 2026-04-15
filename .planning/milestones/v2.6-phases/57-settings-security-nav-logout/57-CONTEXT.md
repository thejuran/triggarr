# Phase 57: Settings Security & Nav Logout - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manage their authentication settings -- change password, switch auth mode (Forms/Basic/External), view/copy/regenerate API key -- from a dedicated Security section on the Settings page. Includes disabled-auth warning banner and contextual mode-switching warnings. Nav logout already wired in Phase 56 (base.html).

</domain>

<decisions>
## Implementation Decisions

### Security Section Placement
- **D-01:** Security section appears **after General, before app instance sections** on the Settings page. General remains the top section (most frequently edited), Security is second.
- **D-02:** Security section uses a **separate form** from the existing settings form. Password change, auth mode, and API key management are independent from general/app settings. Own Save button, own validation.
- **D-03:** Disabled-auth warning banner appears at the **top of the entire Settings page**, above all sections. Full-width red banner, unmissable regardless of scroll position.

### Password Change UX
- **D-04:** Validation errors shown **inline per-field** -- red text below the specific field that failed. "Current password is incorrect" below current password field, "Passwords do not match" below confirm field. Consistent with login page error pattern (Phase 56 D-04).
- **D-05:** After successful password change: **green success message** ("Password updated") appears, all three password fields clear. No page reload.
- **D-06:** Password form submits via **htmx partial submit** (hx-post) to a dedicated endpoint (e.g., `POST /settings/password`). Only the password section re-renders on response. No full page reload.

### API Key Management UX
- **D-07:** API key displayed as **fully masked** (`••••••••••••••••`) by default with an eye icon toggle to reveal. Copy button works regardless of visibility (copies actual key value). Matches *arr convention.
- **D-08:** Regenerating API key requires **confirmation dialog** -- click Regenerate shows inline warning: "This will invalidate the current API key. Any integrations using it will stop working." with Confirm/Cancel buttons.
- **D-09:** After regeneration: **inline replacement** -- key field updates in-place with new key fully visible (auto-revealed), green "Key regenerated" message. Key stays visible until user navigates away or toggles.

### Auth Mode Switching
- **D-10:** Auth mode change takes effect **on save, next request**. User selects mode from dropdown, clicks Save in the Security section. Config writes to TOML, middleware picks up new mode on next request. Current session remains valid.
- **D-11:** **Inline contextual warnings** appear below the dropdown when a mode is selected: External -> "Login page will be bypassed. Ensure your reverse proxy handles auth." Basic -> "Browser will show a native popup instead of the login page." Forms -> no warning (default).
- **D-12:** Auth mode dropdown is part of a **combined Security save** -- one Save button for the Security section handles auth mode + any other security settings. Password change has its own submit via htmx (D-06) since it requires current password validation.

### Disabled Mode Warning (design spec requirement)
- **D-13:** Dropdown only offers Forms/Basic/External -- **no Disabled option** in the UI. Disabled mode is config-file-only (deliberate friction per design spec). Warning banner (D-03) tells the user auth mode can only be changed back from the config file.

### Claude's Discretion
- Exact htmx attributes and swap targets for password and API key partials
- Whether auth mode save and API key regenerate use the same endpoint or separate ones
- Confirmation dialog implementation (htmx inline expand vs JS modal)
- How the eye toggle and copy button are implemented (vanilla JS, matches setup page pattern)
- CSS/layout details within the AIDesigner design

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Specification
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- Full auth design: config schema, settings UI section spec (auth method dropdown, password change, API key display/regenerate, disabled warning banner)

### Prior Phase Context
- `.planning/phases/54-auth-config-helpers/54-CONTEXT.md` -- AuthConfig model, auth.py helpers (hash_password, verify_password, generate_api_key), SecretStr discipline, TOML serialization
- `.planning/phases/55-auth-middleware-health-endpoint/55-CONTEXT.md` -- Middleware placement, auth check order, config access via app.state.settings.auth
- `.planning/phases/56-first-run-setup-login/56-CONTEXT.md` -- Login page error pattern (inline red text), AIDesigner pixel-exact convention, logout wired in nav, clipboard copy pattern from setup success

### Existing Code (must understand before modifying)
- `triggarr/templates/settings.html` -- Current settings page with General + per-app sections; Security section inserts after General
- `triggarr/web/routes.py` -- `settings_page()` GET handler, `save_settings()` POST handler, `_settings_to_dict()` for TOML serialization
- `triggarr/templates/base.html` -- Nav bar with conditional logout link (lines 51-59, already working)
- `triggarr/auth.py` -- `hash_password()`, `verify_password()`, `generate_api_key()` helpers
- `triggarr/models/config.py` -- `AuthConfig` model with `needs_setup`/`is_disabled` properties
- `triggarr/config.py` -- `_atomic_toml_write()`, `load_settings()` for persisting config changes

### Requirements
- `.planning/REQUIREMENTS.md` -- SET-01, SET-02, SET-03, SET-04, LOGIN-05, UI-03 mapped to this phase

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/auth.py` -- hash_password(), verify_password(), generate_api_key() ready for settings endpoints
- `_settings_to_dict()` in routes.py -- already serializes auth fields (password_hash, api_key, session_secret) for TOML
- `_atomic_toml_write()` -- atomic config persistence, reuse for security settings save
- Clipboard copy pattern from setup success page (navigator.clipboard.writeText with "Copied" feedback)
- `auth_state` dict in routes.py -- already tracks active/method state for template rendering
- htmx already loaded in base.html -- use hx-post/hx-swap for partial submits

### Established Patterns
- Settings sections use `bg-triggarr-card rounded-lg border border-triggarr-border p-5` card pattern
- Form inputs use `bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm`
- Existing save_settings reads form data, rebuilds config dict, writes TOML, reloads settings
- Routes use FastAPI APIRouter with Jinja2 TemplateResponse
- htmx patterns for dynamic content (polling, form submissions)

### Integration Points
- `triggarr/templates/settings.html` -- Add Security section card after General section
- `triggarr/web/routes.py` -- Add POST /settings/password, POST /settings/security, POST /settings/api-key/regenerate endpoints
- `triggarr/templates/partials/` -- Add security-related partial templates for htmx swaps
- Settings page GET handler -- pass auth config data (method, masked API key, is_disabled) to template

</code_context>

<specifics>
## Specific Ideas

- AIDesigner MCP generates the Security section HTML artifact -- pixel-exact implementation in Jinja2
- Password change endpoint validates current password via verify_password() before allowing change
- API key regenerate endpoint calls generate_api_key() and writes to config atomically
- Auth mode dropdown: `<select>` with Forms/Basic/External options; JavaScript onChange shows/hides inline warning text
- Disabled warning banner: red bg, spans full width, text explains auth is disabled and can only be re-enabled from config file
- Eye toggle for API key: vanilla JS toggles between masked dots and actual key text; similar pattern to password visibility toggles

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 57-settings-security-nav-logout*
*Context gathered: 2026-04-14*
