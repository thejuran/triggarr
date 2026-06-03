# Phase 74: Count-Only Refresh - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 74-count-only-refresh
**Areas discussed:** Button placement & label, In-flight & success UX, Failure feedback, Helper shape (refactor)

---

## Button placement & label

### Layout (connected footer)

| Option | Description | Selected |
|--------|-------------|----------|
| Two side-by-side | Split footer into Search Now (primary) + Refresh counts (secondary), each ~half width with a gap. | ✓ |
| Refresh stacked below | Search Now full-width on top, slimmer Refresh counts row beneath. | |
| Icon-only refresh beside | Compact icon-only refresh button to the right of a dominant Search Now. | |

**User's choice:** Two side-by-side (chose "1" after viewing ASCII mockups of options 1 and 2).
**Notes:** User asked to see mockups of options 1 and 2 before deciding (picked "Other → show me 1 and 2"). Presented both as ASCII footer sketches with the real markup; user selected option 1. `flex gap-2`, each button `flex-1`; Search Now keeps primary styling, Refresh counts secondary/lighter with `ph-arrows-clockwise`.

### Disconnected state

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Retry only | Disconnected footer unchanged — single "Retry Connection" button; Refresh counts only in connected state. | ✓ |
| Retry + Refresh side-by-side | Mirror connected layout in disconnected state too. | |
| Replace Retry with Refresh | Drop Retry, use Refresh counts as the single reconnect-and-recount action. | |

**User's choice:** Keep Retry only.
**Notes:** A disconnected card has no counts to refresh; Retry already re-probes reachability. Zero change to the disconnected branch.

---

## In-flight & success UX

### In-flight behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Search Now exactly | `hx-disabled-elt="this"` dim+disable while fetching, full-card swap on return. | ✓ |
| Disable both buttons in-flight | Disable Search Now + Refresh counts together during a refresh. | |
| Add a spinning icon | Mirror Search Now plus a CSS-spinning arrows-clockwise icon. | |

**User's choice:** Mirror Search Now exactly.
**Notes:** Reuses the v2.9-walkthrough-hardened in-flight affordance; `search_lock` already serializes server-side so disabling the sibling is unnecessary.

### Success cue

| Option | Description | Selected |
|--------|-------------|----------|
| No extra cue — card swap only | Rely on the full-card swap as confirmation, like Search Now. | ✓ |
| Brief "counts updated" flash | Transient note / highlight after swap. | |
| Timestamp the refresh | "counts as of HH:MM" field on the card. | |

**User's choice:** No extra cue — card swap only.
**Notes:** Avoids new transient UI / new partial state.

---

## Failure feedback

| Option | Description | Selected |
|--------|-------------|----------|
| Disconnected card is enough | Fetch failure renders the card's existing disconnected state on swap; mirrors search_now (always 200 + card). | ✓ |
| Distinct refresh-failed banner | Transient "couldn't refresh counts" message distinct from the steady disconnected state. | |
| Toast / out-of-band message | htmx OOB toast notification on failure. | |

**User's choice:** Disconnected card is enough.
**Notes:** Same visual language as any connection loss; no new error path; no notification pattern introduced.

---

## Helper shape (refactor)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-app helpers | refresh_radarr_counts / _sonarr / _lidarr, each extracting its own cycle's prefix. | ✓ |
| Shared core + callbacks | One refresh_counts core parameterized by app-specific filter/tag callbacks. | |
| Leave it to the planner | Capture only hard constraints, let plan-phase decide structure. | |

**User's choice:** Per-app helpers.
**Notes:** Matches existing per-app `run_*_cycle` structure → lowest-risk behavior-preserving extraction. Mitigate filter-sequence drift by still calling the shared `filter_*`/`cap_batch_sizes` primitives inside each helper.

---

## Claude's Discretion

- Exact secondary-button Tailwind classes for "Refresh counts".
- Shared vs. sibling `last_*_time` rate-limit dict (CONTEXT D-08 prefers a sibling `last_refresh_time`; planner confirms).
- Test fixture organization (new module vs. extending existing engine/route tests) — follow existing conventions.

## Deferred Ideas

- "Counts as of HH:MM" refresh timestamp on the card — declined (new partial state / beyond spec surface).
- Refresh-failed toast / out-of-band notification pattern — declined (no notification pattern exists today; scope creep).
- Animated spinning refresh icon — declined in favor of mirroring Search Now's dim-only affordance.
