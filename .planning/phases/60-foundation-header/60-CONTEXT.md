# Phase 60: Foundation & Header - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Pixel-exact port of the header and font discipline from the AIDesigner artifact. Delivers: system sans-serif body text, Geist Mono restricted to designated elements, spacious header with Phosphor icons, center-aligned nav, connection status pill, and favicon in header (deferred pending asset fix).

</domain>

<decisions>
## Implementation Decisions

### Phosphor Icons Strategy
- **D-01:** Vendor the @phosphor-icons/web package (CSS + WOFF2 font files) into `/static/vendor/phosphor/` and serve locally. No CDN in production — Triggarr must work fully offline, same pattern as existing Geist Mono fonts and htmx.js.
- **D-02:** Use `<i class="ph ph-icon-name">` markup matching the artifact for easy 1:1 porting.

### Header Layout
- **D-03:** Match artifact exactly — absolute-centered nav (`absolute left-1/2 -translate-x-1/2`) with fixed-width `w-64` left/right zones. Replaces current `flex justify-between` layout.
- **D-04:** Header uses `py-4` padding (increased from current `py-3`).

### Favicon in Header
- **D-05:** HDR-06 deferred — do NOT add the in-header app icon in this phase. The current favicon PNGs have white dot anti-aliasing artifacts that need manual fixing first. Add the header icon once cleaned-up assets are available.

### Connection Status Pill
- **D-06:** Green/red toggle based on existing instance health data (same connectivity data that powers app card badges). All instances connected → "Connection Stable" (green pulsing dot + green text). Any instance disconnected → "Connection Issue" (red dot + red text).
- **D-07:** Pill positioned in the right `w-64` zone of the header, matching artifact placement.

### Claude's Discretion
- Font discipline implementation details (how to enforce system sans-serif as default, which selectors to use for Geist Mono restrictions)
- Nav link active state styling (current border-b-2 approach can be adapted to match artifact)
- Logout link hover-to-red behavior from artifact

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Spec
- `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html` — Finalized AIDesigner artifact; the pixel-exact source of truth for all visual changes

### Requirements
- `.planning/REQUIREMENTS.md` §Header (HDR-01 through HDR-06) — Header requirements for this phase
- `.planning/REQUIREMENTS.md` §Font Discipline (FONT-01, FONT-02) — Font restriction rules

### Existing Templates
- `triggarr/templates/base.html` — Current header/nav implementation to be modified
- `triggarr/static/css/input.css` — Tailwind theme config, existing Geist Mono font-faces, dot-pulse animation

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dot-pulse` CSS animation in `input.css` — already implements the pulsing green dot effect needed for the status pill
- Geist Mono font-faces (Regular + Medium weights) already in `input.css`
- Custom Tailwind theme with `triggarr-*` color tokens including `triggarr-green`, `triggarr-bg`, `triggarr-card`, `triggarr-border`, `triggarr-muted`
- Favicon PNGs in `triggarr/static/` (16x16, 32x32, apple-touch-icon, android-chrome sizes)

### Established Patterns
- Jinja2 templates with `{% block %}` inheritance from `base.html`
- Static assets served via `request.url_for('static', path=...)`
- Auth-conditional rendering: `{% if auth_state.active %}` for logout link
- Active nav link styling with `border-b-2 border-triggarr-green`

### Integration Points
- `base.html` `<nav>` block — primary modification target for header changes
- `input.css` `@theme` block — may need new color tokens (e.g., `triggarr-radarr`, `triggarr-sonarr` if not already present)
- Instance health data already available in dashboard context for status pill wiring

</code_context>

<specifics>
## Specific Ideas

- Artifact uses `bg-triggarr-bg/95 backdrop-blur-md` for header background (current uses `bg-triggarr-card/80`)
- Artifact nav links use `font-semibold` for active and `font-medium` for inactive
- Artifact logout hover goes to `red-400` (current has no color change on hover)
- Version badge in artifact uses `font-mono` with uppercase tracking-wider styling

</specifics>

<deferred>
## Deferred Ideas

- **HDR-06 favicon in header** — blocked on manual favicon asset fix (white dot artifacts in current PNGs). Implement once cleaned-up source files are re-exported.
- **Functional connection status states** — current scope covers connected/disconnected binary. Richer states (partial, degraded, reconnecting) could come in a future phase.

</deferred>

---

*Phase: 60-foundation-header*
*Context gathered: 2026-04-15*
