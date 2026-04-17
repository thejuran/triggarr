---
phase: 63-header-favicon-icon
plan: 01
subsystem: ui/header + static-assets
tags: [favicon, header, svg, static-assets, tailwind, tests]
dependency_graph:
  requires: []
  provides: [clean-favicon-bundle, svg-primary-favicon-link, header-app-icon]
  affects:
    - triggarr/templates/base.html
    - triggarr/static/favicon.svg
    - triggarr/static/favicon.ico
    - triggarr/static/favicon-16x16.png
    - triggarr/static/favicon-32x32.png
    - triggarr/static/apple-touch-icon.png
    - triggarr/static/android-chrome-192x192.png
    - triggarr/static/android-chrome-512x512.png
    - triggarr/static/css/output.css
    - tests/test_header_favicon.py
tech_stack:
  added: []
  patterns: [svg-primary-icon-link, nested-flex-gap-override, static-asset-via-url_for]
key_files:
  created:
    - triggarr/static/favicon.svg
    - tests/test_header_favicon.py
  modified:
    - triggarr/templates/base.html
    - triggarr/static/favicon.ico
    - triggarr/static/favicon-16x16.png
    - triggarr/static/favicon-32x32.png
    - triggarr/static/apple-touch-icon.png
    - triggarr/static/android-chrome-192x192.png
    - triggarr/static/android-chrome-512x512.png
    - triggarr/static/css/output.css
decisions:
  - "realfavicongenerator.net's current output uses web-app-manifest-{192,512}.png and omits favicon-16x16/32x32 entirely (modern SVG-primary pipeline). Mapped its output back onto the plan's filename contract: renamed web-app-manifest-* → android-chrome-* (preserves unchanged site.webmanifest refs), rendered 16x16/32x32 from the clean in-repo SVG via macOS qlmanage at exact target size. 96x96 PNG and tool-provided site.webmanifest/favicon.svg from the zip discarded."
  - "Used qlmanage (QuickLook thumbnailer) rather than sips for 16x16/32x32 generation — sips doesn't accept SVG input; qlmanage renders the vector at exact pixel size, bypassing any downscale re-aliasing that caused the original Mar 11 white-dot artifact."
metrics:
  completed: "2026-04-17T22:00:00Z"
  tasks_completed: 3
  tasks_total: 3
  tests_passed: 6
  tests_total_suite: 857
  files_created: 2
  files_modified: 8
requirements_closed:
  - HDR-06
---

# Phase 63 Plan 01: Header Favicon Icon Summary

Closes HDR-06 by shipping a cleaned-up favicon bundle rooted in an SVG master and adding a 24x24 app icon to the left of the "Triggarr" logo text. Eliminates the Phase 60 D-05 white-dot anti-aliasing artifact by sourcing all raster sizes from the clean SVG (directly via qlmanage for 16x16/32x32, via realfavicongenerator.net's own SVG pipeline for 180/192/512 and .ico).

## Task Results

| Task | Name | Commit | Gate |
|------|------|--------|------|
| 1 | User regenerates raster favicon bundle | a0bc2f6 | human-gated checkpoint (deviation handled — see notes) |
| 2 | Verify regenerated bundle | a0bc2f6 | automated — BUNDLE_OK |
| 3 | base.html edits + Tailwind recompile + test module | f9c665e | pytest + ruff + CSS idempotence |

## Changes Made

### Task 1: Regenerate favicon bundle
- Landed clean `favicon.svg` master (3043 bytes, viewBox 0 0 512 512, zero `<script>`/`on*=`/`xlink:href` matches)
- Extracted the user's realfavicongenerator.net zip from the Downloads folder (Apr 17 22:17 UTC)
- Dropped `favicon.ico` and `apple-touch-icon.png` directly from zip
- Renamed `web-app-manifest-{192,512}.png` → `android-chrome-{192,512}.png` to match unchanged `site.webmanifest` and base.html `<link>` targets
- Rendered `favicon-16x16.png` and `favicon-32x32.png` from the in-repo SVG master via `qlmanage -t -s {16,32}` (preserves vector crispness; bytes differ from the historical Mar 11 backup, confirming regeneration)

### Task 2: Verify bundle (all checks passed)
- SVG master: exists, non-empty, `viewBox="0 0 512 512"`, zero unsafe constructs
- All 6 raster files: non-empty, dimensions per `file(1)` (`16x16`, `32x32`, `180x180`, `192x192`, `512x512`)
- `favicon.ico`: MS Windows icon resource (3 icons, 48x48 + 32x32 at 32 bits/pixel)
- The new `favicon-16x16.png` bytes differ from the historical Mar 11 backup stored under `triggarr/static/favicon_io/` (D-05 white-dot fix confirmed)

### Task 3: Wire into header + add tests
- **base.html head:** inserted `<link rel="icon" type="image/svg+xml" href="{{ request.url_for('static', path='favicon.svg') }}">` as the first icon entry (modern browsers prefer SVG, closes HDR-06 for tab icon)
- **base.html left zone:** wrapped the existing `<span>Triggarr</span>` in a new inner `<div class="flex items-center gap-2">` sub-flex and prepended `<img src="...favicon.svg" alt="" class="w-6 h-6">` as the first child (D-06, D-07, D-09). Outer flex stays `flex items-center gap-3 w-64 shrink-0` so the version/update badges keep their gap-3 spacing from the logo text (D-08 invariant)
- **Tailwind recompile:** `uv run tailwindcss -i input.css -o output.css`. No-diff recompile confirmed idempotent (`w-6`, `h-6`, `gap-2` already present from prior phases)
- **tests/test_header_favicon.py:** 6 new tests — `test_favicon_bundle_exists`, `test_favicon_files_non_empty`, `test_favicon_svg_linked_as_primary_in_base_html`, `test_header_icon_img_present_in_base_html`, `test_header_icon_subflex_uses_gap_2`, `test_outer_left_zone_preserves_gap_3`

## Test Results

- Phase tests: `uv run pytest tests/test_header_favicon.py -x -q` → 6 passed in 0.01s
- Full suite: `uv run pytest tests/ -x -q` → 857 passed (25 pre-existing deprecation warnings in auth tests, unrelated to Phase 63)
- Lint: `uv run ruff check triggarr/ tests/` → All checks passed
- CSS: Recompile idempotent (bytes identical after second compile)

## Deviations from Plan

1. **realfavicongenerator.net output shape changed** since Mar 10 2026. The tool no longer emits `favicon-16x16.png`, `favicon-32x32.png`, or `android-chrome-*.png`; it emits `favicon-96x96.png`, `web-app-manifest-*.png`, and a different `site.webmanifest`. Kept the plan's filename contract by renaming/deriving as noted above. No template or manifest edits were needed because the in-repo `site.webmanifest` already targets `android-chrome-{192,512}.png` and base.html still links `favicon-{16,32}.png`.

2. **Zip's `favicon.svg` and `site.webmanifest` discarded.** Zip's SVG (7356 bytes) was a re-expanded version of the user's 3043-byte clean master; kept the cleaner in-repo one. Zip's `site.webmanifest` would have renamed manifest references to `web-app-manifest-*` — incompatible with in-repo manifest, discarded.

3. **Task 1 user signal came as "done" rather than the plan-suggested "bundle dropped".** Verified on disk that the drop had NOT happened (Mar 11 mtimes still present, bytes byte-identical to the historical backup), located the regenerated zip in the user's Downloads folder, performed the asset placement from there with user consent. Human checkpoint semantics preserved.

## Integration Points

- Browsers loading `/` now receive the SVG favicon first (`<link rel="icon" type="image/svg+xml">`). Legacy browsers fall through to `.ico`, then 32x32 / 16x16 PNGs, then apple-touch.
- PWA install (`site.webmanifest`) continues to serve `android-chrome-{192,512}.png` — no manifest edits needed.
- The header icon renders via `request.url_for('static', path='favicon.svg')` — root-path-aware, reverse-proxy safe (Phase 23 pattern).
- D-08 outer-flex invariant preserved: the absolute-centered nav (Zone 2) stays balanced because Zone 1 `w-64 shrink-0` is untouched.

## Requirements Closed

- **HDR-06** — "Refined favicon/app icon to left of 'Triggarr' logo text." Final gap closure for the v2.7 header scope; removes the last deferred item from Phase 60 D-05.
