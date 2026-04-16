# Phase 61: Stat Cards & App Cards - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 61-stat-cards-app-cards
**Areas discussed:** Stat card scaling, Mini progress bars, App card structure, Artifact fidelity

---

## Stat Card Scaling

### Hero Number Sizing

| Option | Description | Selected |
|--------|-------------|----------|
| Artifact-exact sizing | text-[32px] for Movies/Series/Albums, text-[36px] for Grab Rate | |
| Uniform text-[32px] | Same size for all hero numbers including Grab Rate | ✓ |
| You decide | Claude picks based on artifact and visual balance | |

**User's choice:** Uniform text-[32px]
**Notes:** User prefers consistent sizing across all cards

### Phosphor Icons

| Option | Description | Selected |
|--------|-------------|----------|
| Match artifact exactly | Inspect design.html to determine exact icons per card | ✓ |
| Semantic mapping | Pick icons by meaning (ph-film-reel, ph-television, etc.) | |
| You decide | Claude picks after inspecting artifact | |

**User's choice:** Match artifact exactly

### Next Scan Card

| Option | Description | Selected |
|--------|-------------|----------|
| Keep current behavior | Restyle to match artifact but preserve countdown timer | ✓ |
| Remove Next Scan card | Drop entirely if artifact doesn't include it | |
| You decide | Match whatever the artifact shows | |

**User's choice:** Keep current behavior

---

## Mini Progress Bars

| Option | Description | Selected |
|--------|-------------|----------|
| Match artifact exactly | Inspect design.html for exact bar height, radius, labels | ✓ |
| Keep current bars, just recolor | Existing bars with new color tokens | |
| You decide | Claude matches artifact while keeping data wiring | |

**User's choice:** Match artifact exactly

---

## App Card Structure

### Connection Status Display

| Option | Description | Selected |
|--------|-------------|----------|
| Pill in card header | Small green/red pill badge next to title, separated by border-bottom | ✓ |
| Keep current dot indicator | Current dot restyled | |
| You decide | Claude matches artifact treatment | |

**User's choice:** Pill in card header

### Recessed Sub-Cards

| Option | Description | Selected |
|--------|-------------|----------|
| Match artifact exactly | Inspect design.html for exact bg, padding, radius | ✓ |
| Simple inset style | bg-triggarr-bg/50 with rounded-lg and p-3 | |
| You decide | Claude picks best treatment from artifact | |

**User's choice:** Match artifact exactly

### Lidarr Color

| Option | Description | Selected |
|--------|-------------|----------|
| Green for Lidarr | triggarr-green (#22c55e) for borders/accents | ✓ |
| Match artifact only | Only use colors the artifact defines | |
| You decide | Claude picks appropriate Lidarr color | |

**User's choice:** Green for Lidarr

---

## Artifact Fidelity

### Matching Level

| Option | Description | Selected |
|--------|-------------|----------|
| Pixel-exact where possible | Replicate every Tailwind class, spacing, color from design.html | ✓ |
| Spirit over letter | Match visual feel but allow adjustments | |
| Artifact as guideline | Use for color/layout direction, optimize for real data | |

**User's choice:** Pixel-exact where possible

### Responsive Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Stack to single column | Cards stack vertically on mobile | |
| Keep current responsive behavior | Current grid breakpoints stay, just restyle within | ✓ |
| You decide | Maintain current breakpoints unless artifact differs | |

**User's choice:** Keep current responsive behavior

---

## Claude's Discretion

- Exact card subtitle layout for STAT-04
- Phosphor icon integration into existing template structure
- Card shadow/elevation if artifact uses one
- Lidarr-specific stat card icon and accent

## Deferred Ideas

None
