---
phase: 60-foundation-header
plan: 01
subsystem: ui
tags: [phosphor-icons, tailwind-css, color-tokens, font-vendoring]

# Dependency graph
requires: []
provides:
  - "Phosphor Icons regular weight vendored in static/vendor/phosphor/"
  - "Color tokens: triggarr-radarr, triggarr-sonarr, triggarr-danger, triggarr-primaryDark"
  - "Phosphor CSS linked in base.html head"
  - "font-sans body class for FONT-01 system sans-serif default"
affects: [60-02, 60-03]

# Tech tracking
tech-stack:
  added: ["@phosphor-icons/web@2.1.2 (vendored regular weight only)"]
  patterns: ["Vendor icon fonts locally (no CDN) with woff2 format"]

key-files:
  created:
    - triggarr/static/vendor/phosphor/style.css
    - triggarr/static/vendor/phosphor/Phosphor.woff2
  modified:
    - triggarr/static/css/input.css
    - triggarr/static/css/output.css
    - triggarr/templates/base.html

key-decisions:
  - "Only regular weight Phosphor Icons vendored (saves ~800KB+ vs all weights)"
  - "Phosphor CSS linked via HTML tag, not imported into input.css (preserves relative font paths)"

patterns-established:
  - "Vendor fonts in static/vendor/{name}/ with CSS + woff2 only"
  - "Color tokens follow --color-triggarr-{name} naming convention"

requirements-completed: [FONT-01, FONT-02]

# Metrics
duration: 2min
completed: 2026-04-16
---

# Phase 60 Plan 01: Vendor Phosphor Icons and Color Tokens Summary

**Phosphor Icons regular weight vendored locally with 4 new Tailwind color tokens and font-sans body discipline**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-16T01:43:06Z
- **Completed:** 2026-04-16T01:44:45Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Vendored Phosphor Icons regular weight (style.css + Phosphor.woff2, ~144KB font) from @phosphor-icons/web@2.1.2
- Added 4 color tokens to Tailwind theme: triggarr-radarr (#f59e0b), triggarr-sonarr (#3b82f6), triggarr-danger (#ef4444), triggarr-primaryDark (#16a34a)
- Linked Phosphor CSS in base.html head (after output.css, before htmx)
- Added font-sans to body element establishing FONT-01 system sans-serif default

## Task Commits

Each task was committed atomically:

1. **Task 1: Vendor Phosphor Icons and add CSS color tokens** - `a17fa2f` (feat)
2. **Task 2: Add Phosphor stylesheet link and font-sans body class** - `d6a31cf` (feat)

## Files Created/Modified
- `triggarr/static/vendor/phosphor/style.css` - Phosphor Icons regular weight CSS with @font-face declaration
- `triggarr/static/vendor/phosphor/Phosphor.woff2` - Phosphor Icons regular weight font file (~144KB)
- `triggarr/static/css/input.css` - Added 4 color tokens to @theme block
- `triggarr/static/css/output.css` - Recompiled Tailwind CSS with new tokens
- `triggarr/templates/base.html` - Phosphor CSS link in head, font-sans on body

## Decisions Made
- Only vendored regular weight Phosphor Icons (not thin, light, bold, fill, duotone) -- saves ~800KB+ and only regular weight is needed per D-02
- Phosphor CSS linked via HTML link tag rather than @import in input.css -- avoids breaking relative font paths during Tailwind compilation (per RESEARCH.md Pitfall 2)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed dev dependencies in worktree**
- **Found during:** Task 1 (Tailwind CSS recompilation)
- **Issue:** pytailwindcss not installed in worktree venv, `uv run tailwindcss` failed
- **Fix:** Ran `uv sync --extra dev` to install all dev dependencies including pytailwindcss
- **Files modified:** None (venv only)
- **Verification:** Tailwind CSS compiled successfully after install
- **Committed in:** N/A (no file changes)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor environment setup needed for worktree. No scope creep.

## Issues Encountered
None beyond the dev dependency install noted above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phosphor Icons ready for use in templates via `<i class="ph ph-icon-name">` markup
- Color tokens available as Tailwind utilities (text-triggarr-radarr, bg-triggarr-danger, etc.)
- Plan 02 (header restructure) and Plan 03 (connection pill) can proceed

---
*Phase: 60-foundation-header*
*Completed: 2026-04-16*
