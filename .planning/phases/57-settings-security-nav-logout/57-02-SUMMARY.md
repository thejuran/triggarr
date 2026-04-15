---
phase: 57-settings-security-nav-logout
plan: 02
subsystem: web/security-settings-ui
tags: [templates, security, htmx, settings, ui]
dependency_graph:
  requires: [triggarr/web/routes.py (Plan 01 endpoints), triggarr/auth.py]
  provides: [Security section UI on settings page, password change form, API key management, auth method dropdown]
  affects: [triggarr/templates/settings.html, triggarr/templates/partials/security_password.html, triggarr/templates/partials/security_apikey.html]
tech_stack:
  added: []
  patterns: [htmx partial swap, inline SVG icons, conditional Jinja2 type attributes, vanilla JS interactions]
key_files:
  created: []
  modified:
    - triggarr/templates/settings.html
    - triggarr/templates/partials/security_password.html
    - triggarr/templates/partials/security_apikey.html
    - tests/test_auth_routes.py
decisions:
  - Split settings.html into three separate forms (General, Security, per-app) to avoid nested form tags
  - Used inline SVGs instead of Phosphor icons (not in project)
  - API key auto-reveal after regeneration via conditional type attribute driven by revealed=True context
metrics:
  duration_seconds: 213
  completed: "2026-04-15T03:53:21Z"
  tasks_completed: 1
  tasks_total: 2
---

# Phase 57 Plan 02: Settings Security Section Templates Summary

Pixel-exact Security section UI for Settings page with disabled-auth banner, auth method dropdown, password change form, and API key management.

## Task Results

| Task | Name | Type | Commit | Status |
|------|------|------|--------|--------|
| 1 | Create partial templates and modify settings.html with Security section | auto | c231ddf | DONE |
| 2 | Visual verification of Settings Security section | checkpoint:human-verify | -- | AWAITING |

## What Was Built

### Settings Page Restructuring
- Split the single `<form>` into three independent forms: General settings, Security section, and per-app settings
- Eliminated nested form tags (HTML-illegal) by closing General form before Security section
- Security section placed between General and per-app sections per D-01

### Disabled Auth Warning Banner (D-03)
- Full-width red banner (`bg-red-900/30 border-red-900/80`) at top of settings page
- Conditionally shown when `auth_is_disabled` is true
- Warning icon (inline SVG) + bold "Authentication Override" title + description text
- Positioned above all sections for maximum visibility

### Auth Method Dropdown (D-10, D-11, D-12, D-13)
- Select with Forms/Basic/External options (no Disabled -- config-file-only per D-13)
- Contextual amber warnings via JavaScript `updateMethodWarning()`:
  - External: "Login page will be bypassed. Ensure your reverse proxy handles auth."
  - Basic: "Browser will show a native popup instead of the login page."
  - Forms: no warning
- Warning auto-initializes on page load if non-Forms method is selected
- Own Save button submits to `save_security` endpoint

### Password Change Form (D-04, D-05, D-06)
- htmx partial at `partials/security_password.html` with `hx-post` to `change_password` endpoint
- Inline per-field validation errors with `border-red-500/80` highlight and `aria-live="polite"`
- Green success message on password update
- Three fields: Current Password, New Password, Confirm New Password
- All fields use `autocomplete` attributes for browser password manager support

### API Key Management (D-07, D-08, D-09)
- Masked by default via `type="password"` with eye toggle button (inline SVG icons)
- `data-key` attribute stores actual key for clipboard copy regardless of visibility
- Copy button with "Copied!" feedback (2s timeout)
- Regenerate button shows inline confirmation dialog (D-08):
  - Red accent bar, warning text, Confirm/Cancel buttons
  - Confirmation triggers htmx POST to `regenerate_api_key_endpoint`
- Auto-reveal after regeneration (D-09): conditional `type="{{ 'text' if is_revealed else 'password' }}"` renders revealed when endpoint returns `revealed=True`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_settings_page_auth_context assertion**
- **Found during:** Task 1 verification
- **Issue:** Test asserted "admin" in response text, but the new Security section no longer displays the username as static text (replaced by functional security controls)
- **Fix:** Changed assertion to check for `password-section` and `apikey-section` IDs instead
- **Files modified:** tests/test_auth_routes.py
- **Commit:** c231ddf

## Known Stubs

None -- all UI elements are fully wired to Plan 01 backend endpoints.

## Self-Check: PENDING

Self-check will complete after visual verification checkpoint.
