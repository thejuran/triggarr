# Plan 66-04: SEC-01 part 1 — Inline event-handler migration — SUMMARY

**Date:** 2026-05-26
**Plan:** 66-04-PLAN.md
**Requirement:** SEC-01 (part 1 of 2; part 2 is plan 66-05)
**Type:** execute
**Wave:** 2
**Status:** Complete

## What Shipped

Migrated all 13 inline event-handler attributes (`onclick=`, `onchange=`) across 6 template files to `addEventListener` calls / `data-action=` markers. CSP Level 3 nonces don't cover inline event handlers, so this prepares the ground for plan 66-05 dropping `'unsafe-inline'` from `script-src`.

## Tasks Completed

| Task | Type | Outcome |
|------|------|---------|
| 1. Migrate base.html, setup.html, settings.html (3 templates, ~6 handlers) | execute | Changelog modal (3), copy API key (1), auth-method select (1), remove-button stopPropagation (1). Plus new delegated `#apikey-section` click listener in settings.html. |
| 2. Migrate partials (security_apikey.html × 5, log_viewer.html × 3) + add `bindLogViewerControls` in dashboard.html | execute | data-action markers added; new rebind helper called from htmx:afterSwap + DOMContentLoaded. |
| 3. Extend tests/test_log_viewer.py with grep + data-action assertions | execute | New test + 2 pre-existing tests updated to match new shape. |

## Files Changed

| File | +/- |
|------|-----|
| `triggarr/templates/base.html` | +6 −3 |
| `triggarr/templates/setup.html` | +3 −1 |
| `triggarr/templates/settings.html` | +31 −5 |
| `triggarr/templates/partials/security_apikey.html` | +5 −5 |
| `triggarr/templates/partials/log_viewer.html` | +3 −3 |
| `triggarr/templates/dashboard.html` | +27 −0 |
| `tests/test_log_viewer.py` | +30 −4 |

## Test Results

- `tests/test_log_viewer.py` — 20 passed (+1 new)
- Full suite — 929 passed
- `uv run ruff check triggarr/ tests/` — All checks passed

## Key Architecture

Two patterns chosen based on swap behavior:

1. **Stable elements (base.html badge, setup.html copy button, settings.html auth-method select + remove buttons):** `id="..."` + `document.getElementById(...).addEventListener(...)` inside the existing inline `<script>` block. The elements never get swapped, so a one-shot binding suffices.

2. **Swapped-in elements (security_apikey.html partial → `#apikey-section`; log_viewer.html partial → `#log-viewer`):** `data-action="..."` markers + listeners attached to a parent that stays mounted across swaps.
   - `#apikey-section`: single **delegated** listener — `event.target.closest('[data-action]')` + switch on `dataset.action`. The parent `#apikey-section` is in `settings.html`, not in the partial — survives `hx-swap='innerHTML'` of the partial.
   - `#log-viewer`: `bindLogViewerControls(viewer)` helper re-queries `[data-action]` descendants and re-attaches listeners on every `htmx:afterSwap` (the entire `#log-viewer` element is `hx-swap='outerHTML'` every 5s, so previously-attached listeners are discarded with the old DOM).

## D-05 Grep Gate (Revised CONTEXT)

```bash
grep -rnE 'on(click|change|submit|load|blur|focus|keydown|keyup|input)=' triggarr/templates/
# returns 0 lines
```

Zero inline event-handler attributes remain. This is the **necessary precondition** for plan 66-05 dropping `'unsafe-inline'` from CSP `script-src` — without it, every page would break under the new policy.

## Decisions Covered

- D-05 (revised) ✓ — all 13 inline handler attributes migrated; 2-step ordering enforced via 66-05 `depends_on: [66-04]`.

## Notes for Plan 66-05

- The 4 inline `<script>` blocks in base.html / dashboard.html / setup.html / settings.html are still present and will get `nonce="{{ csp_nonce }}"` attributes added in 66-05.
- CSP `script-src` still contains `'unsafe-inline'` at the end of this plan — that is dropped in 66-05.
- Browser behavior is identical to before this plan (verified via 929/929 passing tests + the new partial render assertion).
