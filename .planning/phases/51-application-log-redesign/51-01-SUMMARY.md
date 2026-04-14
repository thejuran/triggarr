# Plan 51-01 Summary: CSS + Template Rewrite

**Status:** Complete
**Commit:** 341d98a

## What was done

1. **CSS (input.css):** Added 5 new CSS blocks:
   - `@keyframes scanline` -- bottom-to-top 8s animation
   - `.terminal-pane` -- #050505 near-black with subtle grid lines
   - `.scanline-overlay` -- 25% opacity overlay with pointer-events: none
   - `#log-viewer.expanded` -- fixed bottom pane, 320px, z-40
   - `body.log-expanded` -- padding-bottom: 320px

2. **Template (log_viewer.html):** Complete rewrite with:
   - Terminal pane aesthetic (terminal-pane class, scanline overlay)
   - TAILING badge with dot-pulse in header
   - Level filter dropdown (All/ERROR/WARNING/INFO/DEBUG)
   - Pause button with onclick="toggleLogPause(this)" and data-pause-btn
   - Expand button with onclick="toggleLogExpand()"
   - Column-aligned rows: timestamp, level (w-14 shrink-0), source (w-20 shrink-0), message
   - ERROR rows: bg-red-500/5 border-l-2 border-l-red-500
   - DEBUG rows: opacity-60
   - Source tags: Radarr orange, Sonarr blue, Lidarr green
   - No script tags in partial

## Verification

- 10/10 applicable tests pass (2 server-side filter tests deferred to Plan 02)
- 9/9 existing log-related tests pass
- Ruff lint: clean
- output.css rebuilt successfully
