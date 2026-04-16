# Phase 60: Foundation & Header - Research

**Researched:** 2026-04-15
**Domain:** Jinja2 template + Tailwind CSS v4 header redesign, Phosphor Icons vendoring, font discipline
**Confidence:** HIGH

## Summary

Phase 60 is a pixel-exact visual port of the header section from the finalized AIDesigner artifact into Triggarr's existing Jinja2/Tailwind CSS v4 codebase. The primary modifications target `base.html` (header/nav restructuring) and `input.css` (new color tokens). The only new external dependency is the `@phosphor-icons/web` icon font, which must be vendored locally following the project's offline-first pattern.

The existing codebase is well-structured for these changes. Tailwind CSS v4 is already running via `pytailwindcss`, Geist Mono fonts are already self-hosted, and the `dot-pulse` CSS animation needed for the connection status pill already exists. The main technical challenge is making health data available in `base.html` (currently only passed to the dashboard template context), and correctly vendoring the Phosphor Icons font files.

**Primary recommendation:** Structure work as: (1) vendor Phosphor Icons, (2) add CSS tokens, (3) restructure header layout in base.html, (4) wire connection status pill with health data as a Jinja2 global, (5) enforce font discipline on body element.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Vendor the @phosphor-icons/web package (CSS + WOFF2 font files) into `/static/vendor/phosphor/` and serve locally. No CDN in production -- Triggarr must work fully offline.
- **D-02:** Use `<i class="ph ph-icon-name">` markup matching the artifact for easy 1:1 porting.
- **D-03:** Match artifact exactly -- absolute-centered nav (`absolute left-1/2 -translate-x-1/2`) with fixed-width `w-64` left/right zones. Replaces current `flex justify-between` layout.
- **D-04:** Header uses `py-4` padding (increased from current `py-3`).
- **D-05:** HDR-06 deferred -- do NOT add the in-header app icon in this phase. The current favicon PNGs have white dot anti-aliasing artifacts that need manual fixing first.
- **D-06:** Green/red toggle based on existing instance health data. All instances connected -> "Connection Stable" (green pulsing dot + green text). Any instance disconnected -> "Connection Issue" (red dot + red text).
- **D-07:** Pill positioned in the right `w-64` zone of the header, matching artifact placement.

### Claude's Discretion
- Font discipline implementation details (how to enforce system sans-serif as default, which selectors to use for Geist Mono restrictions)
- Nav link active state styling (current border-b-2 approach can be adapted to match artifact)
- Logout link hover-to-red behavior from artifact

### Deferred Ideas (OUT OF SCOPE)
- **HDR-06 favicon in header** -- blocked on manual favicon asset fix (white dot artifacts in current PNGs)
- **Functional connection status states** -- current scope covers connected/disconnected binary only
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FONT-01 | Body text uses system sans-serif (not Geist Mono) | Tailwind v4 default sans-serif is already active; no `--font-sans` override in theme. Verified `font-family` only appears in `@font-face` declarations. No changes needed for body default -- just verify no regressions. |
| FONT-02 | Geist Mono applied only to designated elements | Existing `font-geist-mono` utility already in use on correct elements (log viewer, activity rail, etc.). Version badge in header needs `font-mono` added per artifact. |
| HDR-01 | Header has increased vertical padding (py-4) | Direct class change: `py-3` -> `py-4` in base.html header div |
| HDR-02 | Navigation links use text-[15px] with Phosphor icons | Requires vendored Phosphor Icons. Icon map: Dashboard=ph-squares-four, History=ph-clock-counter-clockwise, Settings=ph-gear, Logout=ph-sign-out |
| HDR-03 | Navigation is center-aligned with gap-6 spacing | Three-zone layout with absolute-centered nav per D-03 |
| HDR-04 | Logout link separated by vertical pipe divider with sign-out icon | CSS divider `w-px h-4 bg-triggarr-border mx-1` replaces text pipe; logout gets ph-sign-out icon with hover:text-red-400 |
| HDR-05 | "Connection Stable" status pill with pulsing green dot | Reuses existing `dot-pulse` CSS class; requires health data available in base.html context |
| HDR-06 | Favicon/app icon in header | **DEFERRED per D-05** -- not implemented this phase |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Header layout/styling | Browser / Client (CSS) | -- | Pure CSS/HTML changes in Jinja2 templates |
| Font discipline | Browser / Client (CSS) | -- | Tailwind utility classes control font assignment |
| Phosphor Icons loading | CDN / Static | -- | Vendored font files served as static assets |
| Connection status pill data | API / Backend | Browser / Client | Health data computed server-side, rendered in template |
| Nav active state logic | Frontend Server (SSR) | -- | Jinja2 conditionals on `request.url.path` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | v4.2.2 | Utility-first CSS framework | Already installed via pytailwindcss [VERIFIED: local CLI] |
| @phosphor-icons/web | 2.1.2 | Icon font library (CSS + WOFF2) | Decision D-01, artifact uses Phosphor [VERIFIED: npm registry] |
| Jinja2 | (bundled) | Template engine | Already in use for all templates [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytailwindcss | (dev dep) | Python wrapper for Tailwind CLI | CSS compilation during development [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @phosphor-icons/web (CSS font) | Individual SVG icons | Font approach gives simpler markup (`<i>` tags), matches artifact exactly; SVGs would require per-icon management |

**No installation needed** -- Phosphor Icons are vendored as static files, not installed as a dependency.

## Architecture Patterns

### System Architecture Diagram

```
[Browser Request] --> [FastAPI/Jinja2 SSR]
                         |
                         +--> base.html (header with nav, connection pill)
                         |      |
                         |      +--> Static Assets
                         |             +--> output.css (Tailwind compiled)
                         |             +--> vendor/phosphor/style.css + Phosphor.woff2
                         |             +--> fonts/GeistMono-*.woff2
                         |
                         +--> dashboard.html (extends base.html)
                         +--> history.html (extends base.html)
                         +--> settings.html (extends base.html)
```

### Recommended Project Structure
```
triggarr/static/
├── css/
│   ├── input.css          # Tailwind source (modify: add tokens)
│   └── output.css         # Compiled (regenerated)
├── fonts/
│   ├── GeistMono-Regular.woff2   # Existing
│   └── GeistMono-Medium.woff2    # Existing
├── vendor/
│   └── phosphor/
│       ├── style.css       # Regular weight CSS (from @phosphor-icons/web)
│       └── Phosphor.woff2  # Regular weight font (144KB)
└── js/
    └── htmx.min.js        # Existing

triggarr/templates/
├── base.html              # Primary modification target
└── ...
```

### Pattern 1: Three-Zone Header Layout
**What:** Absolute-centered navigation with fixed-width left/right zones
**When to use:** When nav must be visually centered regardless of left/right zone content width
**Example:**
```html
<!-- Source: AIDesigner artifact design.html lines 60-95 -->
<header class="sticky top-0 z-50 w-full border-b border-triggarr-border bg-triggarr-bg/95 backdrop-blur-md">
  <div class="px-6 py-4 flex items-center justify-between">
    <!-- Left zone: fixed width -->
    <div class="flex items-center gap-3 w-64 shrink-0">...</div>
    <!-- Center: absolute-positioned nav -->
    <nav class="hidden md:flex items-center gap-6 absolute left-1/2 -translate-x-1/2">...</nav>
    <!-- Right zone: fixed width -->
    <div class="flex items-center justify-end w-64 shrink-0">...</div>
  </div>
</header>
```

### Pattern 2: Health Data as Jinja2 Global
**What:** Expose connection health summary to all templates via `templates.env.globals`
**When to use:** When base.html needs data that's currently only in a single route's context
**Example:**
```python
# Source: existing pattern in triggarr/web/routes.py lines 64-74
# Current globals: triggarr_version, update_info, auth_state
# Add: health_summary as a callable or dict that base.html can use

# Option A: Lazy callable (preferred -- avoids computing health on every page)
# Register a function that computes health on demand in the template
templates.env.globals["get_health_summary"] = lambda request: _build_health_summary(request)

# Option B: htmx partial load (simpler, no Python changes)
# base.html includes a placeholder, htmx loads /partials/health-summary on page load
```
**Recommendation:** Option B (htmx partial) is simpler and more consistent with the project's existing htmx patterns. The `/partials/health-summary` endpoint already exists. However, this means a brief flash before the pill loads. Option A avoids the flash but requires passing `request` through Jinja2 globals which is complex. A third option: use Jinja2 context processors via Starlette middleware to inject health data on every response. [ASSUMED]

### Pattern 3: Phosphor Icons Vendoring
**What:** Extract only the "regular" weight from @phosphor-icons/web and serve locally
**When to use:** Offline-first applications that cannot depend on CDN
**Example:**
```bash
# Extract regular weight files from npm package
cd /tmp && npm pack @phosphor-icons/web
tar -xf phosphor-icons-web-2.1.2.tgz
# Copy only what's needed:
# package/src/regular/style.css -> static/vendor/phosphor/style.css
# package/src/regular/Phosphor.woff2 -> static/vendor/phosphor/Phosphor.woff2
```
**Critical:** The `style.css` references font files with relative paths (`url("./Phosphor.woff2")`), so the CSS and WOFF2 must be in the same directory. [VERIFIED: inspected style.css from npm package]

### Anti-Patterns to Avoid
- **Loading all Phosphor weights:** The package includes 6 weights (thin, light, regular, bold, fill, duotone). Only "regular" (`ph ph-*` classes) is needed. Loading all weights would add ~800KB+ of unnecessary font files.
- **Using CDN for Phosphor:** Violates D-01 (offline-first) and project conventions.
- **Overriding Tailwind's default font-sans:** The body already uses system sans-serif by default in TW v4. Adding an explicit `--font-sans` override would be redundant and fragile.
- **Adding `font-mono` to the body:** This would break FONT-01. Geist Mono must only be applied to designated elements via `font-geist-mono` utility.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Icon system | Custom SVG sprite sheet | @phosphor-icons/web CSS font | 4600+ icons, consistent sizing via font-size, artifact already uses `ph ph-*` classes |
| Pulsing dot animation | New keyframe animation | Existing `dot-pulse` class in input.css | Already tested and shipped in v2.5 |
| Font discipline enforcement | Manual font-family on every element | Tailwind v4 default sans-serif + selective `font-geist-mono` | TW v4 already sets system sans as default; just apply mono where needed |

**Key insight:** This phase leverages existing infrastructure heavily. The dot-pulse animation, Geist Mono font setup, color token system, and template inheritance are all already working.

## Common Pitfalls

### Pitfall 1: Health Data Not Available in base.html
**What goes wrong:** The connection status pill is in base.html (shared header), but `health` is only passed in the dashboard route's template context. History and Settings pages would show no pill or crash.
**Why it happens:** Health data was added for dashboard-specific display, not as a global.
**How to avoid:** Either (a) add health data as a Jinja2 global/context processor, or (b) use htmx to load the pill content from the existing `/partials/health-summary` endpoint, or (c) create a new lightweight partial just for the header pill. The existing `_build_health_summary()` function needs access to `request.app.state`, which Jinja2 globals can receive via `request`.
**Warning signs:** Pill renders on dashboard but is empty/broken on history or settings pages.

### Pitfall 2: Phosphor CSS Font Path Mismatch
**What goes wrong:** Icons show as blank squares because the browser can't find the WOFF2 font file.
**Why it happens:** The vendored `style.css` uses relative paths (`url("./Phosphor.woff2")`). If the CSS and font files aren't in the same directory, the paths break.
**How to avoid:** Place both `style.css` and `Phosphor.woff2` in `static/vendor/phosphor/`. Load the CSS via a `<link>` tag referencing the static path. Do NOT try to import Phosphor CSS into `input.css` (Tailwind compilation would change the relative path context).
**Warning signs:** `<i class="ph ph-squares-four">` renders as empty/invisible.

### Pitfall 3: Absolute Nav Overlapping Content
**What goes wrong:** The absolute-centered nav can overlap the left or right zone if the viewport is narrow or the zones have long content.
**Why it happens:** `absolute left-1/2 -translate-x-1/2` positions the nav based on the container, not respecting sibling widths.
**How to avoid:** The `w-64` fixed zones and `hidden md:flex` on the nav provide guard rails. Below `md` breakpoint, nav is hidden entirely. At `md`+ the zones provide enough space. Test at exactly 768px (md breakpoint) to verify no overlap.
**Warning signs:** Nav links sitting on top of the logo or connection pill at intermediate widths.

### Pitfall 4: Active Nav Bottom Bar Misalignment
**What goes wrong:** The green active indicator bar doesn't align flush with the header's bottom border.
**Why it happens:** The `-bottom-[21px]` value is precisely calculated for `py-4` padding + content height. If padding or font size changes, this value becomes wrong.
**How to avoid:** Keep the artifact's exact value. The bar positioning depends on: `py-4` (16px top+bottom), content line height, and the bar's own position. Do not adjust `py-4` without recalculating the bar offset.
**Warning signs:** Green bar floating above or below the header border line.

### Pitfall 5: Phosphor style.css Size (4627 lines)
**What goes wrong:** The regular weight `style.css` contains CSS rules for all ~1500+ icons in the regular set. This is a large file to vendor.
**Why it happens:** Phosphor's CSS font approach defines a CSS class for every icon glyph.
**How to avoid:** This is expected and acceptable. The CSS is cacheable, loads once, and is ~110KB uncompressed (much smaller gzipped). Do not attempt to tree-shake the CSS -- the font approach requires all class definitions to be present.
**Warning signs:** None -- this is normal for icon font libraries.

### Pitfall 6: Logout Button Must Remain a POST Form
**What goes wrong:** Changing the logout `<form method="post">` to an `<a>` tag for styling consistency breaks CSRF protection.
**Why it happens:** The artifact uses `<a>` tags for all nav links including logout, but logout is an action that must use POST.
**How to avoid:** Keep the `<form method="post">` with `<button type="submit">` pattern. Style the button to look like a link using Tailwind classes. The UI-SPEC already documents this correctly.
**Warning signs:** GET requests to logout endpoint, or CSRF validation failures.

## Code Examples

### Version Badge (FONT-02 + artifact match)
```html
<!-- Source: AIDesigner artifact design.html line 65, UI-SPEC Section 2 -->
<button onclick="openChangelog()" type="button"
        class="font-mono px-2 py-0.5 rounded-md bg-triggarr-card border border-triggarr-border
               text-triggarr-muted text-[10px] font-bold uppercase tracking-wider relative top-px
               hover:text-white transition-colors cursor-pointer"
        title="View changelog">
  v{{ triggarr_version }}
</button>
```
Note: Changed from artifact's `<span>` to `<button>` to preserve existing `openChangelog()` behavior. Uses `font-mono` which maps to the existing `--font-geist-mono` theme value in TW v4. [VERIFIED: TW v4 `@theme` `--font-geist-mono` creates `font-geist-mono` utility, but `font-mono` is the standard TW utility that maps to the default mono stack]

**Important correction:** In Tailwind v4 with the current `@theme` config, `font-geist-mono` is the custom utility (uses the `--font-geist-mono` value). The standard `font-mono` utility uses Tailwind's built-in mono stack. Since `--font-geist-mono` includes "Geist Mono" as the first entry, use `font-geist-mono` to ensure Geist Mono renders. The artifact uses `font-mono` which in its TW config maps to Geist Mono -- but in Triggarr's config the equivalent is `font-geist-mono`. [VERIFIED: input.css line 13]

### Connection Pill -- Connected State
```html
<!-- Source: AIDesigner artifact design.html lines 87-91, UI-SPEC Section 9 -->
<!-- NOTE: Artifact uses triggarr-primary/triggarr-primaryDark class names. Plans translate
     these to triggarr-green/triggarr-green-dark (same hex values, no alias token needed). -->
<div class="flex items-center justify-end w-64 shrink-0">
  <div class="flex items-center gap-2 pl-3 pr-3 py-1.5 rounded-lg bg-triggarr-card border border-triggarr-green-dark/40">
    <div class="relative w-2 h-2 rounded-full bg-triggarr-green dot-pulse"></div>
    <span class="text-triggarr-green text-[13px] font-medium mt-0.5">Connection Stable</span>
  </div>
</div>
```

### Connection Pill -- Disconnected State
```html
<div class="flex items-center justify-end w-64 shrink-0">
  <div class="flex items-center gap-2 pl-3 pr-3 py-1.5 rounded-lg bg-triggarr-card border border-triggarr-danger/40">
    <div class="relative w-2 h-2 rounded-full bg-triggarr-danger"></div>
    <span class="text-triggarr-danger text-[13px] font-medium mt-0.5">Connection Issue</span>
  </div>
</div>
```
Note: No `dot-pulse` class on disconnected state (static dot).

### Phosphor Icons Link Tag
```html
<!-- Add after output.css link in base.html <head> -->
<link rel="stylesheet" href="{{ request.url_for('static', path='vendor/phosphor/style.css') }}">
```

### New Color Tokens in input.css
```css
/* Add to @theme block in input.css */
--color-triggarr-radarr: #f59e0b;
--color-triggarr-sonarr: #3b82f6;
--color-triggarr-danger: #ef4444;
--color-triggarr-primaryDark: #16a34a;
/* NOTE: No --color-triggarr-primary token. The artifact's triggarr-primary (#22c55e) is
   identical to the existing triggarr-green. Plans use triggarr-green directly. */
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind CSS v3 config | Tailwind CSS v4 @theme block | TW v4 (2024) | Theme tokens defined in CSS, not JS config [VERIFIED: input.css] |
| @phosphor-icons/web via CDN | Self-hosted vendored font | D-01 decision | Offline-first, no external dependencies |
| Icon fonts (FontAwesome era) | SVG icons or icon fonts per-project | ~2020 ongoing | Phosphor CSS font is still a valid approach for this use case |

**Deprecated/outdated:**
- Tailwind CSS v3 `tailwind.config.js` -- this project uses TW v4 CSS-native config [VERIFIED: no tailwind.config.js exists]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | htmx partial loading is the simplest approach for connection pill data in base.html | Pitfall 1 / Pattern 2 | Minor -- alternative approaches (Jinja2 global, middleware) also work but may need more code changes |
| A2 | The `font-mono` Tailwind utility in TW v4 maps to the built-in monospace stack, NOT to `--font-geist-mono` | Code Examples | Could cause version badge to render in system monospace instead of Geist Mono; use `font-geist-mono` instead |
| A3 | Phosphor regular weight CSS is ~110KB uncompressed and acceptable to vendor entirely | Pitfall 5 | If size is a concern, could subset -- but this is unlikely for a self-hosted app |

## Open Questions (RESOLVED)

1. **How should health data reach base.html for the connection pill?**
   - **RESOLVED:** Use htmx partial loading. A new `/partials/connection-pill` endpoint serves a lightweight HTML fragment. The header right zone in base.html includes an htmx placeholder with `hx-trigger="load, every 30s"` that fetches the pill on page load and refreshes every 30 seconds. This avoids modifying the Python route context layer and is consistent with the project's existing htmx patterns (e.g., `/partials/health-summary`). The brief flash before first load is acceptable for a status indicator.

2. **Should `triggarr-primary` alias be added alongside `triggarr-green`?**
   - **RESOLVED: No.** The artifact's `triggarr-primary` (#22c55e) is the same hex value as the existing `triggarr-green` token. Adding an alias would be unnecessary indirection. Plans translate artifact class names (`text-triggarr-primary` -> `text-triggarr-green`, `bg-triggarr-primary` -> `bg-triggarr-green`) during implementation. The `triggarr-primaryDark` token IS added because there is no existing equivalent with that name (it maps to `triggarr-green-dark` but is needed for artifact border classes like `border-triggarr-primaryDark/40`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytailwindcss | CSS compilation | Yes | TW v4.2.2 | -- |
| npm (for Phosphor vendoring) | One-time asset extraction | Yes | -- | Manual download from npm registry |
| ruff | Linting Python changes | Yes | -- | -- |
| pytest | Test verification | Yes | -- | -- |

**Missing dependencies with no fallback:** None

**Missing dependencies with fallback:** None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_ui_foundations.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FONT-01 | Body text uses system sans-serif | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_body_no_geist_mono -x` | Wave 0 |
| FONT-02 | Geist Mono only on designated elements | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_font_mono_restricted -x` | Wave 0 |
| HDR-01 | Header py-4 padding | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_header_padding -x` | Wave 0 |
| HDR-02 | Nav links with Phosphor icons at text-[15px] | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_nav_phosphor_icons -x` | Wave 0 |
| HDR-03 | Center-aligned nav with gap-6 | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_nav_centered -x` | Wave 0 |
| HDR-04 | Logout pipe divider + sign-out icon | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_logout_divider -x` | Wave 0 |
| HDR-05 | Connection status pill | unit (template assertion) | `uv run pytest tests/test_header_redesign.py::test_connection_pill -x` | Wave 0 |
| HDR-06 | Favicon in header | manual-only | N/A -- DEFERRED per D-05 | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_header_redesign.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_header_redesign.py` -- covers HDR-01 through HDR-05, FONT-01, FONT-02
- [ ] Phosphor icon CSS + WOFF2 vendored files in `triggarr/static/vendor/phosphor/`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (logout link) | Existing POST form with CSRF -- MUST NOT change to GET |
| V3 Session Management | no | -- |
| V4 Access Control | no | -- |
| V5 Input Validation | no | No new user inputs in this phase |
| V6 Cryptography | no | -- |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Logout via GET request | Tampering | Keep `<form method="post">` with `<button type="submit">` (existing pattern) |
| XSS via Jinja2 template | Tampering | Jinja2 auto-escaping (already enabled) |
| Icon font from untrusted CDN | Tampering | Vendored locally per D-01 -- no CDN dependency |

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys (not relevant to this phase but must not regress)
- Loguru for logging (not relevant but must not regress)
- Atomic file writes (not relevant but must not regress)
- pytest-asyncio with asyncio_mode=auto
- Tailwind CSS compilation: `uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css`
- Docker build must continue to work after changes

## Sources

### Primary (HIGH confidence)
- AIDesigner artifact `design.html` lines 60-95 -- header HTML structure [VERIFIED: read directly]
- `triggarr/templates/base.html` -- current header implementation [VERIFIED: read directly]
- `triggarr/static/css/input.css` -- current Tailwind theme and animations [VERIFIED: read directly]
- `triggarr/web/routes.py` -- health data flow, Jinja2 globals, route context [VERIFIED: read directly]
- `@phosphor-icons/web` npm package v2.1.2 -- package structure, CSS font approach [VERIFIED: npm registry + tarball inspection]
- `60-UI-SPEC.md` -- approved design contract for this phase [VERIFIED: read directly]

### Secondary (MEDIUM confidence)
- Tailwind CSS v4 `@theme` behavior -- custom font utilities from CSS variables [VERIFIED: existing working code in input.css]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all dependencies verified against npm registry and existing codebase
- Architecture: HIGH - existing patterns well-documented, artifact provides pixel-exact spec
- Pitfalls: HIGH - identified through direct code inspection of template context flow and font path analysis

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable -- no fast-moving dependencies)
