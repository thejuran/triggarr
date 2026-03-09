# Phase 3: Web UI - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Status dashboard and config editor for Fetcharr. Users can view automation status (last/next run, queue positions, item counts, connection health, search history) and edit all settings via a web UI. Built with FastAPI + Jinja2 + htmx. No auth (runs behind Tailscale/VPN).

</domain>

<decisions>
## Implementation Decisions

### Dashboard layout
- Side-by-side app cards: Radarr card on left, Sonarr card on right
- Each card shows: connection status, last run, next run, queue position, wanted/cutoff counts, enable/disable toggle, "Search Now" button
- Shared chronological search log below the cards, with app label per entry
- Separate settings page at /settings (dashboard is read-only status)
- Minimal top bar navigation: "Fetcharr" brand + Dashboard / Settings links

### Visual style & theme
- Dark mode only — fits the *arr ecosystem
- Visual reference: Radarr/Sonarr style (dark backgrounds, colored accent bars, functional and dense)
- Green accent color for active states, buttons, highlights — distinct from Radarr (orange) and Sonarr (blue)
- Tailwind CSS via pytailwindcss (Phase 4 Dockerfile already references pytailwindcss builder stage)

### Config editor UX
- Per-app sections: Radarr section with all its fields, Sonarr section with all its fields
- Each section has enable/disable toggle at the top
- Explicit save button — changes don't apply until user clicks "Save"
- Hot reload on save — new settings take effect immediately (scheduler interval updates, connections re-validate, no restart needed)
- API keys masked in form (placeholders shown), only accepted on write
- "Search Now" button lives on the dashboard app cards, not the settings page

### Error & status display
- Connection errors shown inline on the app card — red/orange border or badge with "Unreachable since [time]"
- No transient feedback (no toasts) — dashboard updates via htmx polling, new log entries and timestamps just appear
- htmx polling interval: every 5 seconds
- Green dot/badge on each card when connected — positive confirmation at a glance

### Claude's Discretion
- Exact Tailwind color palette values (within green accent + dark theme)
- Typography and spacing details
- Loading/skeleton states during initial page load
- Search log entry formatting and max visible entries
- Form validation error presentation
- "Search Now" button disabled state while search is in progress

</decisions>

<specifics>
## Specific Ideas

- Style should feel like Radarr/Sonarr — functional, dense, dark. Not trying to be flashy, just informative.
- Green accent differentiates Fetcharr from Radarr (orange) and Sonarr (blue) in the user's tab bar.
- Dashboard is the "glance" page — you open it, see everything is running, close it. Settings is only visited when something needs changing.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-web-ui*
*Context gathered: 2026-02-23*
