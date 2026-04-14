# Plan 51-02 Summary: Route Filter + Dashboard JS

**Status:** Complete
**Commit:** d0a27fc

## What was done

1. **Route (routes.py):** Modified `partial_log_viewer` to accept optional `level` query parameter:
   - Validates against `_VALID_LEVELS = {"ERROR", "WARNING", "INFO", "DEBUG"}` whitelist
   - Invalid values silently treated as "All" (no filter)
   - `level.upper()` normalizes case
   - `selected_level` passed to template context for dropdown state persistence

2. **Dashboard JS (dashboard.html):** Added script block outside the partial:
   - `htmx:afterSwap` listener: auto-scrolls log body, re-applies expanded and paused state
   - `toggleLogExpand()`: toggles expanded class on #log-viewer and log-expanded on body
   - `toggleLogPause(btn)`: toggles hx-trigger between "every 5s" and "none", stores state on body
   - `DOMContentLoaded` listener: initial auto-scroll

## Warnings

- Script block renders even on empty-config pages (no apps). Functions early-return if #log-viewer is absent. No functional impact.

## Verification

- 12/12 log viewer tests pass
- 656/656 full suite tests pass
- Ruff lint: clean
