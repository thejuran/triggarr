# Phase 49: Stats & Health Strip - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 49-stats-health-strip
**Areas discussed:** Health strip layout, Grab Rate card sizing, Health badge thresholds, Per-app bar colors

---

## Health Strip Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Own htmx partial (replace health_summary.html) | Strip replaces the existing card, same polling endpoint | |
| Merge into stats_row partial | Combine health + stats into one polled section | |

**User's choice:** Extracted from mockup spec — strip is a standalone element above the stats grid (L195-212), not inside a card. Keeps its own partial.
**Notes:** Mockup defines exact classes. "Last sync" timestamp not in current backend — left to Claude's discretion.

---

## Grab Rate Card Sizing

| Option | Description | Selected |
|--------|-------------|----------|
| md:col-span-2 always | Hero card spans 2 columns regardless of filter state | |
| Collapse to col-span-1 when filtered | Shrink hero when showing single-app stats | |

**User's choice:** Extracted from mockup — `md:col-span-2` in a `grid-cols-2 md:grid-cols-5` grid. Always 2 columns.
**Notes:** Instance filter hides irrelevant stat cards but hero card always shows overall rate.

---

## Health Badge Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Mockup default (87% = Healthy) | Only "Healthy" shown in mockup, no other states | |
| Define all three states | Healthy/Warn/Critical with threshold values | |

**User's choice:** Extracted from mockup — only "Healthy" state shown. Thresholds left to Claude's discretion. Recommended: >=70% Healthy, >=40% Warn, <40% Critical.
**Notes:** Badge colors follow Tailwind green/amber/red pattern.

---

## Per-App Bar Colors

| Option | Description | Selected |
|--------|-------------|----------|
| Follow mockup exactly | Radarr=orange-400, Sonarr=blue-400, Lidarr=green-400 | |
| Match existing app colors | Use whatever colors are already used for these apps elsewhere | |

**User's choice:** Follow mockup exactly — colors are explicitly defined in L227-239.
**Notes:** Colors applied via inline `style` for dynamic width, not Tailwind classes.

---

## Claude's Discretion

- "Last sync" timestamp computation
- Health badge threshold exact values
- No-data badge behavior
- Filtered app highlighting in hero card

## Deferred Ideas

- Sparkline trend chart (FUT-01) — later milestone
- App card shadow-sm — Phase 50 scope
