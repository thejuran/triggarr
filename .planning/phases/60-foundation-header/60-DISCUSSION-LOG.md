# Phase 60: Foundation & Header - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 60-foundation-header
**Areas discussed:** Phosphor icons strategy, Header layout approach, Favicon in header, Connection status pill

---

## Phosphor Icons Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Vendor the web font | Download @phosphor-icons/web assets (CSS + WOFF2) and serve from /static/. ~180KB for regular weight. | ✓ |
| Inline SVG partials | Copy only ~10 needed icons as Jinja2 SVG partials. Smallest bundle but different markup. | |
| Python SVG helper | Use a Python package or Jinja2 filter to render SVGs by name. | |

**User's choice:** Vendor the web font
**Notes:** User asked about the "no CDN in production" requirement — confirmed it's because Triggarr runs on home servers/NAS boxes that may be offline or behind firewalls. Must work fully offline like existing vendored assets (Geist Mono, htmx).

---

## Header Layout Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Match artifact exactly | Absolute-centered nav with w-64 left/right zones. Pixel-exact match. | ✓ |
| Adapt to current layout | Keep justify-between flex, add new elements. Simpler but nav not perfectly centered. | |

**User's choice:** Match artifact exactly
**Notes:** None — straightforward decision.

---

## Favicon in Header

| Option | Description | Selected |
|--------|-------------|----------|
| Existing favicon PNG | Use favicon-32x32.png as <img> next to logo. | |
| Skip until favicon fixed | Don't add header icon until favicon artifacts cleaned up. | ✓ |
| Phosphor icon placeholder | Use a Phosphor icon as temporary stand-in. | |

**User's choice:** Skip until favicon is fixed
**Notes:** User identified white dot anti-aliasing artifacts in current favicon PNGs (visible on browser tabs). Reviewed all favicon sizes — issue is edge pixels blending against wrong background color. Created manual task to re-export from source with proper anti-aliasing against #0f172a background. HDR-06 deferred until asset is fixed.

---

## Connection Status Pill

| Option | Description | Selected |
|--------|-------------|----------|
| Green/Red toggle | All connected → "Connection Stable" (green). Any disconnected → "Connection Issue" (red). | ✓ |
| Show count | Show N/M connected with color coding. | |
| Match artifact exactly (decorative) | Always shows "Connection Stable" regardless of state. | |

**User's choice:** Green/Red toggle (real health data)
**Notes:** User initially selected decorative, then corrected — wants it to reflect real connectivity, same data as existing app card connected/disconnected badges. Binary toggle, not count-based.

---

## Claude's Discretion

- Font discipline implementation details
- Nav link active state styling adaptation
- Logout link hover-to-red behavior

## Deferred Ideas

- HDR-06 favicon in header — blocked on manual favicon asset fix
- Richer connection status states (partial, degraded, reconnecting)
