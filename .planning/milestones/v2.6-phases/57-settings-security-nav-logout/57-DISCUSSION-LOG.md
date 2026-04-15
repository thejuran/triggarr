# Phase 57: Settings Security & Nav Logout - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 57-settings-security-nav-logout
**Areas discussed:** Security section placement, Password change UX, API key management UX, Auth mode switching

---

## Security Section Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Top, before General | Security is the most important section -- users see it first. Matches *arr convention. | |
| After General, before apps | General stays at top (most frequently edited), Security comes second. | ✓ |
| Bottom, after all sections | Appended after app instance sections. Least disruptive but buries security controls. | |

**User's choice:** After General, before apps
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Separate form | Security section has its own Save/Submit button. Independent validation. | ✓ |
| Same form as existing | One big form, one Save button. Simpler but harder to validate independently. | |

**User's choice:** Separate form
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Top of Settings page | Unmissable -- red banner spans full width above all sections. | ✓ |
| Inside Security section | Warning appears at top of Security card only. More contextual but could be missed. | |

**User's choice:** Top of Settings page
**Notes:** None

---

## Password Change UX

| Option | Description | Selected |
|--------|-------------|----------|
| Inline per-field | Red text below the specific field that failed. Matches login page pattern. | ✓ |
| Single banner above form | One error message at top of Security section. Simpler but less precise. | |
| You decide | Claude picks best approach. | |

**User's choice:** Inline per-field
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Green success message, fields clear | Brief green text, all password fields cleared. No page reload. | ✓ |
| Full page reload with flash | Page reloads with success flash message. Simpler but disrupts scroll. | |
| You decide | Claude picks based on existing patterns. | |

**User's choice:** Green success message, fields clear
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| htmx partial submit | Password section submits via hx-post to dedicated endpoint. Only section re-renders. | ✓ |
| Standard form POST | Full form POST, server redirects back. Simpler but full page reload. | |

**User's choice:** htmx partial submit
**Notes:** None

---

## API Key Management UX

| Option | Description | Selected |
|--------|-------------|----------|
| Fully masked with reveal toggle | Shows dots with eye icon toggle. Copy works regardless. Matches *arr pattern. | ✓ |
| Partially masked | Shows first 4 and last 4 chars. Helps identify which key. | |
| Always visible | Full 32-char hex always shown. Simplest but less secure. | |

**User's choice:** Fully masked with reveal toggle
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm dialog | Click Regenerate shows warning about invalidation with Confirm/Cancel. | ✓ |
| Instant with undo | Regenerate immediately, show brief Undo option. | |
| Instant, no confirmation | Click and done. No safety net. | |

**User's choice:** Confirm dialog
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Inline replacement | Key field updates in-place with new key visible. Green message. | ✓ |
| Modal with copy | New key in modal dialog with copy button, like setup success. | |

**User's choice:** Inline replacement
**Notes:** None

---

## Auth Mode Switching

| Option | Description | Selected |
|--------|-------------|----------|
| On save, next request | Change writes to config, takes effect on next request. Current session valid. | ✓ |
| Immediate with re-login | Changing mode immediately logs out and redirects. More dramatic. | |
| You decide | Claude picks based on middleware architecture. | |

**User's choice:** On save, next request
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Inline warning per mode | Contextual note below dropdown when mode selected. External/Basic get warnings. | ✓ |
| No warnings | Trust user knows what they're doing. Simpler. | |
| Confirm dialog on save | Confirmation dialog explains consequences before applying. | |

**User's choice:** Inline warning per mode
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Combined Security save | One Save button for auth mode + other security settings. | ✓ |
| Independent htmx submit | Auth mode has own save button. More granular but cluttered. | |

**User's choice:** Combined Security save
**Notes:** None

---

## Claude's Discretion

- Exact htmx attributes and swap targets for password and API key partials
- Whether auth mode save and API key regenerate use the same endpoint or separate ones
- Confirmation dialog implementation (htmx inline expand vs JS modal)
- Eye toggle and copy button implementation details
- CSS/layout details within AIDesigner design

## Deferred Ideas

None -- discussion stayed within phase scope
