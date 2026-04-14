# Phase 51: Application Log Redesign - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 51-application-log-redesign
**Areas discussed:** Source tag extraction, Terminal pane behavior, Log row interactions, Scanline visual intensity

---

## Source Tag Extraction

| Option | Description | Selected |
|--------|-------------|----------|
| Parse from message text | Extract [Radarr]/[Sonarr]/[Lidarr] prefix from existing log messages in the Jinja2 template using a filter. Zero backend changes. | ✓ |
| Add source field to LogEntry | Add optional source field to log buffer's LogEntry dataclass. Requires changes to log_buffer.py and logging.py. | |
| You decide | Claude picks the approach | |

**User's choice:** Parse from message text (Recommended)
**Notes:** No backend changes needed — keeps the scope focused on the template/CSS redesign.

---

## Terminal Pane Behavior

### Toggle Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Pure CSS class toggle | Add/remove 'expanded' class via inline onclick handler. No new JS dependencies. Mockup already defines CSS for both states. | ✓ |
| htmx hx-swap with two templates | Separate inline and expanded partials. Click triggers htmx swap. More htmx-native but duplicates markup. | |
| You decide | Claude picks the approach | |

**User's choice:** Pure CSS class toggle (Recommended)

### Auto-Scroll

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, always pin to bottom | New entries appear at bottom, pane scrolls to keep them visible. Standard terminal behavior. | ✓ |
| No, manual scroll only | User scrolls manually. New entries appear but pane doesn't auto-scroll. | |
| Smart scroll | Auto-scroll only if user is at the bottom. If scrolled up, don't jump back. | |

**User's choice:** Yes, always pin to bottom (Recommended)

---

## Log Row Interactions

| Option | Description | Selected |
|--------|-------------|----------|
| Skip for now | Keep focused on 6 LOG requirements. Pause/filter can be a future phase. | |
| Include pause button only | Add pause toggle that stops htmx polling. Simple and useful for reading errors. | |
| Include both pause and filter | Full mockup fidelity — pause polling + filter by level/source. | ✓ |

**User's choice:** Include both pause and filter

### Filter Control

| Option | Description | Selected |
|--------|-------------|----------|
| Level dropdown | Simple dropdown to filter by log level: All / ERROR / WARNING / INFO / DEBUG. | ✓ |
| Level + source multi-filter | Filter by both level AND source app. Two dropdowns or chip-based filter bar. | |
| You decide | Claude picks what fits the header space | |

**User's choice:** Level dropdown (Recommended)

---

## Scanline Visual Intensity

| Option | Description | Selected |
|--------|-------------|----------|
| Subtle | Scanlines at ~15% opacity on dark (#0a0a0a) background. Visible but not distracting. | |
| Full retro | Scanlines at 25% opacity on near-black (#050505). Strong CRT terminal vibe. | ✓ |
| Minimal | Dark background only, no scanlines. Clean and functional. | |

**User's choice:** Full retro
**Notes:** Unmistakable terminal aesthetic — the expanded pane should feel like a real terminal.
