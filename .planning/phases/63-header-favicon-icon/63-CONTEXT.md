# Phase 63: Header Favicon Icon - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Close HDR-06: replace the aliased favicon bundle with a user-supplied SVG source, regenerate all PNG sizes + favicon.ico from it, and place a 24×24 app icon to the left of the "Triggarr" logo text in the header. Gap closure for Phase 60 D-05.

</domain>

<decisions>
## Implementation Decisions

### Source Asset
- **D-01:** User supplies a pre-cleaned master SVG (currently on user's desktop as `favicon.svg`). SVG is the master format — eliminates white-dot anti-aliasing fringe at all sizes, permanently resolving Phase 60 D-05.
- **D-02:** SVG lands at `triggarr/static/favicon.svg` (alongside existing `favicon.*` files). No new subdirectory.
- **D-03:** SVG background state (baked-in rounded-square vs transparent glyph) is unknown at discussion time — Claude inspects the file once user drops it into the repo and adjusts CSS/alt-text if transparent rendering affects header appearance.

### Cleanup Scope
- **D-04:** Full bundle regeneration. Replace existing `favicon-16x16.png`, `favicon-32x32.png`, `apple-touch-icon.png`, `android-chrome-192x192.png`, `android-chrome-512x512.png`, `favicon.ico` with new versions generated from the SVG. Add `favicon.svg` as the primary `<link rel="icon" type="image/svg+xml">` entry in `base.html`. Closes HDR-06 and fixes browser tab + PWA icon aliasing in one pass.

### Regeneration Workflow
- **D-05:** User runs `favicon.svg` through **realfavicongenerator.net** and drops the full output bundle into `triggarr/static/`. This matches how the original bundle was created (origin confirmed by filename set + `site.webmanifest` shape), so filenames drop in cleanly without markup changes. Plan includes an asset-drop task with verification checklist (all expected files present, correct dimensions, no white-dot artifacts at 16×16).

### Header Markup
- **D-06:** Render the header icon as `<img src="{{ request.url_for('static', path='favicon.svg') }}" alt="">` — direct reference to the static SVG. Browser-cacheable, no inline SVG bloat, colors bake in with the file. Uses `request.url_for` for root_path awareness (matches established pattern).

### Header Visual Spec
- **D-07:** Icon renders at 24×24px (`w-6 h-6`) — slightly larger than the 20px logo text for brand-anchor visual weight.
- **D-08:** 8px gap (`gap-2`) between icon and "Triggarr" logo text. The existing left-zone flex uses `gap-3` — implementation will nest the icon + "Triggarr" span in a sub-flex with `gap-2` so the version badge still sits at `gap-3` from the logo text.
- **D-09:** Icon is the first child of the left `w-64` zone (leftmost element), preserving existing zone order: [icon, Triggarr text, version badge, update badge].

### Claude's Discretion
- Nested flex structure to achieve icon-to-text `gap-2` while preserving text-to-badge `gap-3`
- Alt text choice (`alt=""` decorative since "Triggarr" text is adjacent, vs `alt="Triggarr"`) — default to decorative empty alt
- Whether to update `site.webmanifest` theme_color (currently `#0f172a` — Tailwind slate-900; may want to stay as-is or swap to triggarr-bg)
- Test strategy: visual-regression snapshot vs asset-existence assertion vs skip (favor existence + size assertions — binary files not suitable for byte-exact tests across regenerations)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §Header (HDR-06) — Refined favicon/app icon to left of "Triggarr" logo text

### Prior Phase Context (gap closure source)
- `.planning/phases/60-foundation-header/60-CONTEXT.md` §Favicon in Header (D-05) — Original deferral reason (white dot anti-aliasing artifacts in favicon PNGs)
- `.planning/phases/60-foundation-header/60-UI-SPEC.md` — Header design spec (text-xl logo, w-64 left zone, gap-3 inner spacing)

### Design Spec
- `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html` — AIDesigner artifact (note: artifact does NOT show an icon beside "Triggarr"; HDR-06 intent came from SeedSyncarr's placement — this phase adds the icon the artifact omitted)

### Existing Templates & Assets
- `triggarr/templates/base.html` lines 7–11 — Existing `<link rel="icon">` tags to update (add SVG primary)
- `triggarr/templates/base.html` lines 22–39 — Left zone header div (insertion point for icon)
- `triggarr/static/site.webmanifest` — PWA manifest referencing android-chrome PNGs

### External Tool
- https://realfavicongenerator.net — User-operated tool for regenerating the PNG + .ico bundle from the master SVG

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/static/` directory already serves all favicon files via FastAPI static mount — new files drop in without route changes
- `base.html` already has `<link rel="icon">` tags for 16/32 + apple-touch + manifest — adding SVG primary is a one-line insertion, PNG fallbacks stay
- Left-zone flex pattern in `base.html` line 24 (`flex items-center gap-3 w-64 shrink-0`) — icon becomes first child, may need nested sub-flex for gap-2 to text

### Established Patterns
- Static asset references use `{{ request.url_for('static', path='...') }}` (root_path-aware, reverse-proxy safe — see Phase 23 decision)
- No JavaScript needed — icon is pure markup, follows existing htmx-only interaction model
- File-naming follows favicon generator output (favicon.*, apple-touch-icon.png, android-chrome-*.png) — keep this convention so realfavicongenerator.net output drops in byte-for-byte

### Integration Points
- `triggarr/templates/base.html` — two edit locations: `<head>` (add SVG link), header left zone (add icon `<img>`)
- `triggarr/static/` — six binary file replacements + one new SVG file
- `triggarr/static/site.webmanifest` — no changes required unless theme_color decision revisits it

### Metadata Scan Findings (2026-04-17)
- Existing PNGs have all text chunks stripped (no tEXt/iTXt/zTXt/iCCP) — no embedded generator tag
- Filename set (favicon-16x16, favicon-32x32, apple-touch-icon at 180px, android-chrome-192/512, favicon.ico with 16/32 stacked, site.webmanifest) + manifest shape (`theme_color: #0f172a`, `background_color: #0f172a`) matches realfavicongenerator.net / favicon.io default output exactly
- Original commit: `34bcd1b` (2026-03-10) — co-authored with Claude, no tool named

</code_context>

<specifics>
## Specific Ideas

- Icon design (from inspecting existing 512×512): green film reel inside a magnifying glass, green on dark-gradient rounded square — user is supplying a cleaned-up SVG of this same mark
- SVG primary link pattern: `<link rel="icon" type="image/svg+xml" href="{{ request.url_for('static', path='favicon.svg') }}">` — browsers prefer SVG when present, fall back to PNG automatically
- Icon sizing: `w-6 h-6` (24×24) chosen to read slightly larger than 20px logo text for brand-anchor weight — not exact logo-height match (that would be `w-5 h-5`)
- Version badge in left zone: `gap-3` from Triggarr text must be preserved — implementation detail: nest icon + span in a flex-gap-2 wrapper sitting inside the outer flex-gap-3 container

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within HDR-06 scope. No scope-creep attempts surfaced.

</deferred>

---

*Phase: 63-header-favicon-icon*
*Context gathered: 2026-04-17*
