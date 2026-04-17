# Phase 63: Header Favicon Icon - Pattern Map

**Mapped:** 2026-04-17
**Files analyzed:** 9 (1 new SVG, 6 PNG/ICO replacements, 1 template modified, 1 new test)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/static/favicon.svg` | static-asset (binary/XML source of truth) | static-file-serve | `triggarr/static/apple-touch-icon.png` (existing in-place favicon) | role-match (SVG instead of raster) |
| `triggarr/static/favicon-16x16.png` | static-asset (regenerated) | static-file-serve | existing `favicon-16x16.png` | exact (same path/name, new bytes) |
| `triggarr/static/favicon-32x32.png` | static-asset (regenerated) | static-file-serve | existing `favicon-32x32.png` | exact (same path/name, new bytes) |
| `triggarr/static/apple-touch-icon.png` | static-asset (regenerated) | static-file-serve | existing `apple-touch-icon.png` | exact (same path/name, new bytes) |
| `triggarr/static/android-chrome-192x192.png` | static-asset (regenerated) | static-file-serve | existing `android-chrome-192x192.png` | exact (same path/name, new bytes) |
| `triggarr/static/android-chrome-512x512.png` | static-asset (regenerated) | static-file-serve | existing `android-chrome-512x512.png` | exact (same path/name, new bytes) |
| `triggarr/static/favicon.ico` | static-asset (regenerated) | static-file-serve | existing `favicon.ico` | exact (same path/name, new bytes) |
| `triggarr/templates/base.html` | template | request-response | itself (current version) | exact (2 edits: head + left zone) |
| `tests/test_header_redesign.py` OR new `tests/test_header_favicon.py` | test | request-response + filesystem | `tests/test_header_redesign.py` (asset-existence + markup assertions) | exact |

**Notes on classification:**
- All raster files are **drop-in replacements** — filenames and paths stay byte-identical to the current bundle (confirmed from `triggarr/static/site.webmanifest` and current `<link>` tags), so no markup churn for the fallback chain.
- `favicon.svg` is a **new static asset** (already landed in repo at 3,043 bytes — user-dropped per D-02).
- Template edit is **two surgical insertions**, not a restructure (see Pattern Assignments below).
- The in-place replacement character of this phase means the **closest analog for most files is the file itself** — the pattern being replicated is the existing naming/serving convention, not a new code pattern.

## Pattern Assignments

### `triggarr/static/favicon.svg` (new static-asset)

**Analog:** `triggarr/static/apple-touch-icon.png` (sibling raster favicon asset, same directory, same static-serve route)

**Placement pattern** (`/Users/julianamacbook/triggarr/triggarr/static/`):
```
triggarr/static/
├── android-chrome-192x192.png    (existing)
├── android-chrome-512x512.png    (existing)
├── apple-touch-icon.png          (existing)
├── favicon-16x16.png             (existing)
├── favicon-32x32.png             (existing)
├── favicon.ico                   (existing)
├── favicon.svg                   (NEW — already dropped by user, 3043 bytes)
└── site.webmanifest              (existing, no changes needed)
```

**Inspection finding for D-03 resolution (already landed):**
Read `/Users/julianamacbook/triggarr/triggarr/static/favicon.svg` lines 1-20:
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="Cleaned video search favicon">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#243553"/>
      <stop offset="100%" stop-color="#0F1A30"/>
    </linearGradient>
    ...
  </defs>
  <rect x="0" y="0" width="512" height="512" rx="64" fill="url(#bg)"/>
```

**Consequence:** SVG has a **baked-in rounded-square dark-gradient background** (`#243553` → `#0F1A30`, `rx="64"`). Not transparent. Renders as a self-contained tile on the `bg-triggarr-bg/95` header — **no CSS adjustments required**. D-03 resolved: no alt-text or background class additions needed for transparent-SVG edge cases.

**Serving:** The file is served by the existing FastAPI `StaticFiles` mount at `/static/` (see `triggarr/web/routes.py:57` — `STATIC_DIR = _PKG_DIR / "static"`). No route registration needed.

---

### `triggarr/static/favicon-*.png`, `apple-touch-icon.png`, `android-chrome-*.png`, `favicon.ico` (regenerated binaries)

**Analog:** the existing files at the same paths (same names, same sizes, same purpose — only bytes differ).

**Regeneration workflow pattern** (D-05):
```
1. User runs triggarr/static/favicon.svg through realfavicongenerator.net
2. User drops the full output bundle into triggarr/static/ (overwrites existing files)
3. Verify file set:
   - favicon-16x16.png       (current size: 829 bytes)
   - favicon-32x32.png       (current size: 2,158 bytes)
   - apple-touch-icon.png    (current size: 41,612 bytes, 180×180)
   - android-chrome-192x192.png (current size: 45,422 bytes)
   - android-chrome-512x512.png (current size: 315,455 bytes)
   - favicon.ico             (current size: 15,406 bytes, contains 16+32 stacked)
```

**Verification checklist excerpts** (for plan action):
```bash
# All six files must exist and be non-empty
test -s triggarr/static/favicon-16x16.png
test -s triggarr/static/favicon-32x32.png
test -s triggarr/static/apple-touch-icon.png
test -s triggarr/static/android-chrome-192x192.png
test -s triggarr/static/android-chrome-512x512.png
test -s triggarr/static/favicon.ico

# Dimensions should match manifest expectations
# (file(1) reports PNG dimensions; `identify` from ImageMagick if available)
file triggarr/static/favicon-16x16.png    # "PNG image data, 16 x 16"
file triggarr/static/android-chrome-512x512.png  # "PNG image data, 512 x 512"
```

**site.webmanifest compatibility** (confirming no manifest edit needed):
```json
{
  "name": "Triggarr",
  "short_name": "Triggarr",
  "icons": [
    {"src": "/static/android-chrome-192x192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/android-chrome-512x512.png", "sizes": "512x512", "type": "image/png"}
  ],
  "theme_color": "#0f172a",
  "background_color": "#0f172a",
  "display": "standalone"
}
```
Filenames in `site.webmanifest` already match the realfavicongenerator.net default output shape. **No manifest edit required** unless Claude decides to update `theme_color` (noted as Claude's discretion in CONTEXT.md).

---

### `triggarr/templates/base.html` (template, request-response) — Edit #1: SVG `<link>` in `<head>`

**Analog:** itself — existing `<link rel="icon">` tags at `triggarr/templates/base.html` lines 7-11.

**Existing `<link>` block** (lines 7-11, read verbatim):
```html
  <link rel="icon" type="image/x-icon" href="{{ request.url_for('static', path='favicon.ico') }}">
  <link rel="icon" type="image/png" sizes="32x32" href="{{ request.url_for('static', path='favicon-32x32.png') }}">
  <link rel="icon" type="image/png" sizes="16x16" href="{{ request.url_for('static', path='favicon-16x16.png') }}">
  <link rel="apple-touch-icon" sizes="180x180" href="{{ request.url_for('static', path='apple-touch-icon.png') }}">
  <link rel="manifest" href="{{ request.url_for('static', path='site.webmanifest') }}">
```

**Insertion pattern** (add SVG primary as **the first icon link**, before the `.ico` fallback):
```html
  <link rel="icon" type="image/svg+xml" href="{{ request.url_for('static', path='favicon.svg') }}">
  <link rel="icon" type="image/x-icon" href="{{ request.url_for('static', path='favicon.ico') }}">
  <link rel="icon" type="image/png" sizes="32x32" href="{{ request.url_for('static', path='favicon-32x32.png') }}">
  <link rel="icon" type="image/png" sizes="16x16" href="{{ request.url_for('static', path='favicon-16x16.png') }}">
  <link rel="apple-touch-icon" sizes="180x180" href="{{ request.url_for('static', path='apple-touch-icon.png') }}">
  <link rel="manifest" href="{{ request.url_for('static', path='site.webmanifest') }}">
```

**Rationale for order** (browsers walk `<link rel="icon">` in document order, using the first one they understand):
- SVG first → modern browsers use scalable vector (no anti-aliasing artifacts — closes HDR-06 / D-05)
- `.ico` second → legacy IE/Edge fallback
- PNG 32×32 / 16×16 → size-hinted rasters for older browsers
- `apple-touch-icon` → iOS home-screen, separate rel value
- `manifest` → PWA, unchanged

---

### `triggarr/templates/base.html` (template, request-response) — Edit #2: Icon `<img>` in left zone

**Analog:** `triggarr/templates/base.html` lines 22-39 (existing left-zone flex structure).

**Existing left zone structure** (read verbatim from lines 22-39):
```html
    <div class="px-6 py-4 flex items-center justify-between">
      {# Left zone: Logo + Version Badge + Update Badge (D-03: w-64 fixed width) #}
      <div class="flex items-center gap-3 w-64 shrink-0">
        <span class="text-triggarr-green font-bold text-xl tracking-tight">Triggarr</span>
        <button onclick="openChangelog()" type="button"
                class="font-geist-mono px-2 py-0.5 rounded-md bg-triggarr-card border border-triggarr-border text-triggarr-muted text-[10px] font-bold uppercase tracking-wider relative top-px hover:text-white transition-colors cursor-pointer"
                title="View changelog">
          v{{ triggarr_version }}
        </button>
        {% if update_info and update_info.update_available %}
        <a href="{{ update_info.html_url if update_info.get('html_url', '').startswith('https://github.com/') else '#' }}" target="_blank" rel="noopener"
           class="inline-flex items-center gap-1.5 text-xs bg-triggarr-green/15 text-triggarr-green px-2 py-0.5 rounded-full hover:bg-triggarr-green/25 transition-colors"
           title="Update available — click to view release">
          <span class="w-1.5 h-1.5 rounded-full bg-triggarr-green dot-pulse"></span>
          v{{ update_info.latest_version }} available
        </a>
        {% endif %}
      </div>
```

**Nested sub-flex pattern to achieve icon→text `gap-2` while preserving text→badge `gap-3`** (per D-08):

```html
      {# Left zone: Icon + Logo + Version Badge + Update Badge (D-03: w-64 fixed width) #}
      <div class="flex items-center gap-3 w-64 shrink-0">
        {# Icon + "Triggarr" text group with tighter gap-2 between them (D-07, D-08, D-09) #}
        <div class="flex items-center gap-2">
          <img src="{{ request.url_for('static', path='favicon.svg') }}" alt="" class="w-6 h-6">
          <span class="text-triggarr-green font-bold text-xl tracking-tight">Triggarr</span>
        </div>
        <button onclick="openChangelog()" type="button"
                class="font-geist-mono px-2 py-0.5 rounded-md bg-triggarr-card border border-triggarr-border text-triggarr-muted text-[10px] font-bold uppercase tracking-wider relative top-px hover:text-white transition-colors cursor-pointer"
                title="View changelog">
          v{{ triggarr_version }}
        </button>
        {% if update_info and update_info.update_available %}
        <a href="{{ update_info.html_url if update_info.get('html_url', '').startswith('https://github.com/') else '#' }}" target="_blank" rel="noopener"
           class="inline-flex items-center gap-1.5 text-xs bg-triggarr-green/15 text-triggarr-green px-2 py-0.5 rounded-full hover:bg-triggarr-green/25 transition-colors"
           title="Update available — click to view release">
          <span class="w-1.5 h-1.5 rounded-full bg-triggarr-green dot-pulse"></span>
          v{{ update_info.latest_version }} available
        </a>
        {% endif %}
      </div>
```

**What changed — minimal diff:**
- Wrapped `<span class="text-triggarr-green font-bold text-xl tracking-tight">Triggarr</span>` in a new `<div class="flex items-center gap-2">` sub-container
- Added `<img src="{{ request.url_for('static', path='favicon.svg') }}" alt="" class="w-6 h-6">` as the first child of that sub-container (D-06, D-07, D-09)
- `w-64 shrink-0` and outer `gap-3` preserved → version badge and update badge still sit at `gap-3` from the grouped icon+text unit (the sub-flex counts as one flex item in the outer flex)
- No other children changed; version badge button, update badge anchor, and Jinja conditional untouched

**Class breakdown for the new image:**
- `w-6 h-6` → 24×24px render (D-07, slightly larger than 20px logo text for brand-anchor visual weight)
- `alt=""` → decorative empty alt (D-06 + CONTEXT.md discretion — screen readers announce the adjacent "Triggarr" text)
- No `aria-hidden="true"` needed; empty alt already implies decorative per WAI-ARIA 1.1

**Class breakdown for the new sub-flex:**
- `flex items-center` → same alignment as parent, so baseline stays consistent
- `gap-2` → 8px between icon and "Triggarr" text (D-08)
- No `w-*` or `shrink` → sizes to content, counts as one item in the outer `gap-3 w-64` flex

---

### `tests/test_header_favicon.py` (new test) OR extended assertions in `tests/test_header_redesign.py`

**Analog:** `tests/test_header_redesign.py` lines 285-295 (asset-existence + base.html link verification pattern).

**Pattern #1 — Asset-existence assertion** (`tests/test_header_redesign.py` lines 285-288, read verbatim):
```python
def test_phosphor_font_files_vendored():
    """Phosphor CSS and WOFF2 files exist in vendor directory."""
    assert (STATIC_DIR / "vendor" / "phosphor" / "style.css").exists()
    assert (STATIC_DIR / "vendor" / "phosphor" / "Phosphor.woff2").exists()
```

**Adapted for favicon bundle:**
```python
def test_favicon_bundle_exists():
    """HDR-06: Full favicon bundle (SVG master + regenerated raster fallbacks) present."""
    assert (STATIC_DIR / "favicon.svg").exists()
    assert (STATIC_DIR / "favicon.ico").exists()
    assert (STATIC_DIR / "favicon-16x16.png").exists()
    assert (STATIC_DIR / "favicon-32x32.png").exists()
    assert (STATIC_DIR / "apple-touch-icon.png").exists()
    assert (STATIC_DIR / "android-chrome-192x192.png").exists()
    assert (STATIC_DIR / "android-chrome-512x512.png").exists()


def test_favicon_files_non_empty():
    """HDR-06: Favicon bundle files are non-empty (catches accidental zero-byte drops)."""
    for name in (
        "favicon.svg",
        "favicon.ico",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "apple-touch-icon.png",
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
    ):
        path = STATIC_DIR / name
        assert path.stat().st_size > 0, f"{name} is empty"
```

**Pattern #2 — base.html markup verification** (`tests/test_header_redesign.py` lines 291-294, read verbatim):
```python
def test_phosphor_css_linked_in_base_html():
    """Phosphor CSS is linked in base.html head."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert "vendor/phosphor" in base_html
```

**Adapted for favicon markup:**
```python
def test_favicon_svg_linked_as_primary_in_base_html():
    """HDR-06: SVG <link> present and precedes .ico fallback."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert 'type="image/svg+xml"' in base_html
    assert "favicon.svg" in base_html
    # SVG link must come before .ico so browsers prefer it
    svg_idx = base_html.index("favicon.svg")
    ico_idx = base_html.index("favicon.ico")
    assert svg_idx < ico_idx, "SVG favicon link must precede .ico fallback"


def test_header_icon_img_present_in_base_html():
    """HDR-06: Header left zone contains favicon.svg <img> tag at w-6 h-6 sizing."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    # <img> reference to favicon.svg (separate from <link rel=icon>)
    assert "<img" in base_html
    assert 'path=\'favicon.svg\'' in base_html or "path=\"favicon.svg\"" in base_html
    assert "w-6 h-6" in base_html
```

**Pattern #3 — Request-rendered HTML assertion** (uses `client` fixture from `test_header_redesign.py` lines 28-111; requires the full mocked-app fixture already proven in that file):
```python
def test_header_icon_rendered_with_static_url(client):
    """HDR-06: Dashboard renders favicon.svg <img> via request.url_for('static')."""
    response = client.get("/")
    assert response.status_code == 200
    # Static URL resolved to actual path (root_path-aware)
    assert "/static/favicon.svg" in response.text
    # The icon <img> and the SVG <link rel=icon> both appear
    assert response.text.count("favicon.svg") >= 2
```

**Imports pattern** (copy from `tests/test_header_redesign.py` lines 22-25):
```python
from triggarr.web.routes import STATIC_DIR, auth_state, router

TEMPLATES_DIR = STATIC_DIR.parent / "templates"
```

**Choice between new file vs. extending existing:**
- **Preferred:** Add new module `tests/test_header_favicon.py` scoped to HDR-06. Mirrors the one-module-per-phase convention (`test_ui_foundations.py` = Phase 48, `test_header_redesign.py` = Phase 60, so Phase 63 gets its own file). Matches project testing style already established across 30+ test modules.
- **Alternative:** Append the four test functions above to `tests/test_header_redesign.py` in a new `# --- Favicon / HDR-06 ---` section. Only valid if planner judges that keeping HDR-* tests co-located outweighs per-phase isolation.

**pytest-asyncio note:** `asyncio_mode=auto` (per CLAUDE.md) means async fixtures (like `test_app`) need no decorator. Tests that use the `client` fixture stay synchronous — same as all existing tests in `test_header_redesign.py`.

---

## Shared Patterns

### Static Asset Reference via `request.url_for('static', ...)`
**Source:** `triggarr/templates/base.html` lines 7-14 (every static asset link uses this, six separate examples).

**Apply to:** Both new template insertions (SVG `<link>` and header `<img>`).

```jinja2
{{ request.url_for('static', path='favicon.svg') }}
```

**Why this pattern is mandatory:**
- Root-path-aware — survives reverse-proxy prefix stripping (confirmed by CONTEXT.md §Established Patterns: "see Phase 23 decision")
- Consistent with every other static ref in the template (output.css, phosphor stylesheet, htmx.min.js, all existing favicon links, site.webmanifest)
- `StaticFiles` mount registers the route name `"static"` via FastAPI's `app.mount("/static", StaticFiles(...), name="static")` pattern (seen in `tests/test_header_redesign.py` line 33)

**Alternatives to avoid:**
- Hard-coded `/static/favicon.svg` (breaks under reverse proxy with `root_path` set)
- `url_for()` without `request.` prefix (FastAPI's Jinja2 integration requires `request` context)
- Jinja `url_for` helper from Flask conventions (not applicable in FastAPI)

---

### Three-Zone Header Flex Structure
**Source:** `triggarr/templates/base.html` lines 21-94 (established in Phase 60 Plan 02 — see `.planning/phases/60-foundation-header/60-02-PLAN.md`).

**Apply to:** All header-markup edits in this phase must preserve the three-zone invariant.

```html
<header class="sticky top-0 z-50 w-full border-b border-triggarr-border bg-triggarr-bg/95 backdrop-blur-md">
  <div class="px-6 py-4 flex items-center justify-between">
    <!-- ZONE 1: Left, w-64 shrink-0 (logo + badges) -->
    <div class="flex items-center gap-3 w-64 shrink-0">...</div>

    <!-- ZONE 2: Center, absolute-positioned nav -->
    <nav class="hidden md:flex items-center gap-6 absolute left-1/2 -translate-x-1/2">...</nav>

    <!-- ZONE 3: Right, w-64 shrink-0 (connection pill) -->
    <div class="flex items-center justify-end w-64 shrink-0">...</div>
  </div>
</header>
```

**Invariants this phase must NOT break:**
- Left zone stays `w-64 shrink-0` — absolute-centered nav depends on balanced left+right widths
- Left zone outer flex stays `gap-3 items-center` — version/update badges rely on `gap-3`
- Order of top-level children in left zone: [logo-unit, version badge, update badge]
- The **only structural change** is wrapping the existing `<span>Triggarr</span>` + new `<img>` in a sub-flex (`gap-2`), leaving outer zone untouched

---

### Phase 60 Plan 02 as Closest Header-Edit Analog
**Source:** `.planning/phases/60-foundation-header/60-02-PLAN.md` (the restructure that built the current left zone).

**Apply to:** The plan for Phase 63 follows the same shape:
- `files_modified:` one template + the recompiled `output.css` (because new Tailwind utilities `w-6 h-6` may not be compiled yet — `w-6` is common enough to likely already exist)
- `<task type="auto">` for each change, with explicit `<verify>` grep
- `<acceptance_criteria>` lists exact strings to assert present/absent in file

**Phase 60 Plan 02 verify step pattern** (read verbatim from line 230):
```bash
grep -q "py-4" triggarr/templates/base.html && grep -q "ph ph-squares-four" triggarr/templates/base.html && echo "PASS"
```

**Adapted for Phase 63:**
```bash
grep -q 'type="image/svg+xml"' triggarr/templates/base.html \
  && grep -q "favicon.svg" triggarr/templates/base.html \
  && grep -q "w-6 h-6" triggarr/templates/base.html \
  && grep -q 'alt=""' triggarr/templates/base.html \
  && test -s triggarr/static/favicon.svg \
  && test -s triggarr/static/favicon.ico \
  && test -s triggarr/static/apple-touch-icon.png \
  && test -s triggarr/static/android-chrome-192x192.png \
  && test -s triggarr/static/android-chrome-512x512.png \
  && test -s triggarr/static/favicon-16x16.png \
  && test -s triggarr/static/favicon-32x32.png \
  && echo "PASS"
```

---

### Tailwind CSS Recompilation After Utility Changes
**Source:** `.planning/phases/60-foundation-header/60-02-PLAN.md` Task 2 (lines 259-289).

**Apply to:** If any previously-unused utility class (e.g., `w-6`, `h-6`) is introduced to the template, `output.css` must be recompiled.

```bash
cd /Users/julianamacbook/triggarr && uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css
```

**Risk check for Phase 63:** `w-6` and `h-6` are likely already in `output.css` from prior phases (`text-[18px]` nav icons used other sizing; `w-2 h-2` and `w-1.5 h-1.5` exist in dot animations). The plan should still include a recompile step as a belt-and-suspenders precaution, matching Phase 60 Plan 02 Task 2.

---

### Test Module Conventions
**Source:** `tests/test_header_redesign.py` lines 1-25 (and the broader `tests/` directory — 30+ test modules).

**Apply to:** New `tests/test_header_favicon.py` file.

```python
"""Phase 63 header favicon (HDR-06) tests.

Verifies SVG primary <link>, raster fallback bundle existence, and header
icon <img> presence. Closes Phase 60 D-05 / HDR-06.
"""

from __future__ import annotations

from triggarr.web.routes import STATIC_DIR

TEMPLATES_DIR = STATIC_DIR.parent / "templates"
```

**Module docstring convention:** Opens with `"""Phase N <subject> tests.` — see `test_ui_foundations.py:1` ("Phase 48 UI foundations smoke tests.") and `test_header_redesign.py:1` ("Phase 60 header redesign tests.").

**`from __future__ import annotations` is standard across the test suite** (seen in `test_ui_foundations.py:8`, `test_header_redesign.py:7`).

**`TEMPLATES_DIR = STATIC_DIR.parent / "templates"` is the established idiom** for reading template source (used in both existing UI test modules).

**Pure-synchronous tests for static markup checks** — no need for the async `test_app` fixture unless a request-rendered assertion is added. Asset-existence and template-string checks stay sync, keeping the module light.

---

## No Analog Found

None. Every file in this phase has a direct analog:
- All seven static files are either in-place replacements or co-located siblings of existing favicons
- Template edits reuse the existing `<link rel="icon">` pattern and the existing left-zone flex structure
- Test patterns come directly from `test_header_redesign.py` (same UI-testing genre, same repo)

---

## Metadata

**Analog search scope:**
- `triggarr/templates/` (base.html, base-auth.html)
- `triggarr/static/` (existing favicon bundle, site.webmanifest)
- `tests/` (test_header_redesign.py, test_ui_foundations.py)
- `.planning/phases/60-foundation-header/` (60-UI-SPEC.md, 60-02-PLAN.md, 60-02-SUMMARY.md, 60-PATTERNS.md)

**Files scanned:** ~12 source/spec files, plus file-listing of `triggarr/static/`.

**Pattern extraction date:** 2026-04-17

**Key insight for planner:** This is one of the **simplest pattern-replicate phases** possible — every line of new markup and every new file has a byte-for-byte neighbor already in the repo. The plan should be ~2 tasks (asset drop + template edit) with a third recompile-and-test task, mirroring Phase 60 Plan 02's shape almost exactly but with far less surface area.
