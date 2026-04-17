# Phase 62: Activity Rail & Log Viewer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 62-activity-rail-log-viewer
**Areas discussed:** Card style mapping, Opacity fading, LIVE badge color, Log viewer details

---

## Card Style Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| By outcome type (Recommended) | Grabbed/partial = solid card. Searched/failed/unresolved = dashed card. Maps resolved outcomes to prominent style, pending to subdued. | ✓ |
| By position only | First 2 entries always solid, rest always dashed regardless of outcome. | |
| By recency | Entries < 30 min old = solid, > 30 min = dashed. Time-based. | |

**User's choice:** By outcome type
**Notes:** Grabbed/partial get solid bg-triggarr-card cards; searched/failed/unresolved get dashed border bg-triggarr-bg cards. Timeline dots colored by outcome (green=grabbed, amber=partial, yellow=searched, red=failed, gray=unresolved).

---

## Opacity Fading

| Option | Description | Selected |
|--------|-------------|----------|
| Position-based steps (Recommended) | Entries 1-2 at 100%, entry 3 at 75%, entry 4+ at 60%. Match artifact exactly. | ✓ |
| Gradual position fade | Smooth gradient: 100%, 90%, 80%, 70%, 60%, 50%... down to floor of 40%. | |
| Time-based fade | < 1hr = 100%, 1-6hr = 75%, 6hr+ = 60%. Based on actual entry age. | |

**User's choice:** Position-based steps
**Notes:** Simple Jinja2 loop index conditional. Matches artifact's exact opacity values.

---

## LIVE Badge Color

| Option | Description | Selected |
|--------|-------------|----------|
| Keep green (Recommended) | Override artifact's red. Use triggarr-green for consistency with TAILING badge and connection status pill. | ✓ |
| Match artifact (red) | Use red-400 as artifact shows. Creates visual distinction between LIVE and TAILING indicators. | |
| You decide | Claude picks based on color system coherence. | |

**User's choice:** Keep green
**Notes:** Green = active/healthy is the established UI language across the dashboard.

---

## GRAB Row Highlight

| Option | Description | Selected |
|--------|-------------|----------|
| Keyword detection (Recommended) | Detect grab-related messages by content keywords. Apply green highlight. No new log level needed. | ✓ |
| Skip GRAB highlight | Treat as artifact decoration. Keep current level-based coloring only. | |
| You decide | Claude picks approach balancing fidelity with simplicity. | |

**User's choice:** Keyword detection
**Notes:** Detect messages containing grab-related keywords and apply bg-triggarr-primary/10 border-l-2 border-triggarr-primary treatment with [GRAB] label.

---

## Log Viewer Title

| Option | Description | Selected |
|--------|-------------|----------|
| Match artifact: System Logs | Change title, add ph-terminal-window icon. | ✓ |
| Keep: Application Log | Keep current title, just add Phosphor icon. | |

**User's choice:** Match artifact: System Logs
**Notes:** Full rename to "System Logs" with Phosphor terminal-window icon, matching artifact exactly.

---

## Claude's Discretion

- Exact keyword list for GRAB row detection
- triggarr-elevated token handling for card hover states
- Log row source tag extraction approach
- scanline-overlay treatment in new container

## Deferred Ideas

None — discussion stayed within phase scope
