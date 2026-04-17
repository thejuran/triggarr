# Phase 62: Activity Rail & Log Viewer - Research

**Researched:** 2026-04-17
**Domain:** Jinja2 template restyling (Tailwind CSS v4, Phosphor Icons, htmx partials)
**Confidence:** HIGH

## Summary

Phase 62 is a pure visual restyling of two existing Jinja2 template partials: `activity_rail.html` and `log_viewer.html`. No new routes, no new data models, no new JavaScript functions. The existing htmx polling, JS handlers (`toggleLogPause`, `toggleLogExpand`), and backend data flow remain untouched. The work is replacing inline SVGs with Phosphor icon classes, restructuring the activity rail from a flat timeline to card-based entries with speech bubble pointers and double-circle timeline dots, and restyling the log viewer header with Phosphor controls and refined badge/filter styling.

The CONTEXT.md contains 18 locked decisions (D-01 through D-18) that prescribe exact Tailwind classes, colors, spacing, and structural patterns. The UI-SPEC provides a complete component inventory with pixel-level class specifications. Together, these form a deterministic implementation contract -- the planner's job is to sequence the work and ensure test coverage, not make design decisions.

**Primary recommendation:** Split into two plans -- one for activity rail (larger structural change), one for log viewer (simpler restyling) -- each modifying its template, updating CSS if needed, and updating its test file.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Card style determined by outcome type: grabbed/partial = solid card (`bg-triggarr-card`, solid border), searched/failed/unresolved = dashed card (`bg-triggarr-bg`, `border-dashed`)
- **D-02:** Timeline dot colors: grabbed = `bg-triggarr-primary`, partial = `bg-amber-400`, searched = `bg-yellow-500`, failed = `bg-red-500`, unresolved = `bg-gray-500`
- **D-03:** Speech bubble pointer: `absolute -left-[5px] top-4 w-2 h-2 rotate-45` matching card background and border style
- **D-04:** Double-circle timeline dots: outer `w-7 h-7 rounded-full bg-triggarr-card border-2 border-triggarr-bg` containing inner `w-2.5 h-2.5 rounded-full` with outcome color
- **D-05:** Vertical timeline line: `absolute left-[38px] top-6 bottom-6 w-px bg-triggarr-border`
- **D-06:** App badge row: `w-1.5 h-1.5 rounded-full` app-colored dot + `text-[10px] font-mono text-triggarr-muted uppercase tracking-wider font-bold` label
- **D-07:** Position-based opacity: entries 1-2 = 100%, entry 3 = `opacity-75`, entry 4+ = `opacity-60`
- **D-08:** LIVE badge uses green (`bg-triggarr-green`/`text-triggarr-green`), overriding artifact's red
- **D-09:** Header: `text-[13px] font-bold uppercase tracking-widest text-triggarr-muted`, sticky with `bg-triggarr-bg/95 backdrop-blur-md`
- **D-10:** Footer: `ph-arrow-right` icon with `group-hover:translate-x-1 transition-transform`
- **D-11:** Title rename "Application Log" to "System Logs", add `ph-terminal-window` icon
- **D-12:** Replace inline SVGs with Phosphor: `ph-pause` and `ph-corners-out`, size `text-[15px]`
- **D-13:** TAILING badge border container: `px-2 py-0.5 rounded bg-triggarr-bg border border-triggarr-border`
- **D-14:** Level filter format "Level: INFO" etc., `font-mono bg-triggarr-bg border border-triggarr-border text-[11px]`
- **D-15:** Vertical divider `w-px h-4 bg-triggarr-border` between filter and buttons
- **D-16:** Log container `bg-[#0b1120]` with `bg-triggarr-card` header bar
- **D-17:** GRAB row highlight: keyword-based detection, `bg-triggarr-primary/10 border-l-2 border-triggarr-primary` with `[GRAB]` level label
- **D-18:** Non-grab rows: `hover:bg-white/5` with group hover transitions, `text-[13px] leading-relaxed`

### Claude's Discretion
- Exact keyword list for GRAB row detection (grab/grabbed/found release/sent to client etc.)
- Whether to add `triggarr-elevated` token if it doesn't exist for card hover states
- Log row source tag extraction (keep or adjust current `[Radarr]`/`[Sonarr]`/`[Lidarr]` prefix detection)
- How to handle `scanline-overlay` -- keep, remove, or adapt to new container style

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RAIL-01 | Activity rail items use card-based layout with speech bubble pointer and colored timeline dots | D-01 through D-05 define exact card/dot/pointer structure; UI-SPEC Component Inventory provides complete class lists |
| RAIL-02 | App badges use font-mono with colored dot indicators | D-06 defines exact badge structure with `font-mono` and `w-1.5 h-1.5 rounded-full` colored dot |
| RAIL-03 | Older entries fade with decreasing opacity | D-07 defines position-based stepped fading via Jinja2 loop index |
| LOG-01 | Log viewer uses refined header with Phosphor icons for pause/expand controls | D-11, D-12 define Phosphor icon replacements and header restructuring |
| LOG-02 | TAILING badge uses font-mono with pulsing green dot | D-13 defines border container wrapping existing dot-pulse badge |
| LOG-03 | Log level filter uses font-mono styled select dropdown | D-14 defines "Level: X" format with font-mono styling |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Activity rail card layout | Frontend Server (Jinja2) | -- | Server-rendered HTML partial, no client logic |
| Timeline dot rendering | Frontend Server (Jinja2) | -- | Conditional Jinja2 classes based on outcome data |
| Opacity fading | Frontend Server (Jinja2) | -- | Loop-index-based CSS classes applied server-side |
| Log viewer header icons | Frontend Server (Jinja2) | Browser (JS) | HTML structure is server-rendered; JS handlers already exist |
| GRAB row highlight | Frontend Server (Jinja2) | -- | Keyword detection in Jinja2 template conditional |
| Log level filter | Frontend Server (Jinja2) | Browser (JS) | Select element rendered server-side; onchange JS already exists |
| CSS theme tokens | CDN/Static | -- | input.css compiled by Tailwind CLI |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | v4 (already installed) | Utility-first CSS | Project standard, all styling via utilities [VERIFIED: input.css uses `@import "tailwindcss"` v4 syntax] |
| Jinja2 | (bundled with FastAPI) | Template rendering | Project standard for all partials [VERIFIED: existing templates] |
| Phosphor Icons | vendored at `static/vendor/phosphor/` | Icon library | Project standard since Phase 60 [VERIFIED: existing `ph ph-*` usage in templates] |
| htmx | (already loaded) | Partial polling/swap | Project standard for live updates [VERIFIED: existing `hx-get`/`hx-trigger` patterns] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Geist Mono | self-hosted woff2 | Monospace font | Badges, timestamps, log body, filter dropdown [VERIFIED: input.css @font-face declarations] |

No new packages needed. No `npm install` or `uv add` required.

## Architecture Patterns

### System Architecture Diagram

```
Browser Request (every 5s polling)
        |
        v
  FastAPI Route Handler
  (/partials/activity-rail or /partials/log-viewer)
        |
        v
  Jinja2 Template Rendering
  (activity_rail.html or log_viewer.html)
        |
        +---> app.state.db (search_log entries for rail)
        +---> log_buffer (LogEntry objects for log viewer)
        |
        v
  HTML Partial Response
        |
        v
  htmx outerHTML swap (replaces #activity-rail or #log-viewer)
```

No changes to this flow. Phase 62 only modifies the Jinja2 templates and CSS.

### Recommended Project Structure
```
triggarr/
  templates/
    partials/
      activity_rail.html    # MODIFY: card-based layout, speech bubbles, double-circle dots
      log_viewer.html        # MODIFY: Phosphor icons, System Logs title, GRAB highlights
  static/
    css/
      input.css              # MODIFY: update/replace timeline-item/timeline-dot CSS classes
tests/
  test_activity_rail.py      # MODIFY: update assertions for new class names
  test_log_viewer.py         # MODIFY: update assertions for new class names, add GRAB tests
```

### Pattern 1: Card-Based Timeline Entry (Activity Rail)
**What:** Each timeline entry is a `flex gap-4 items-start` row containing a double-circle dot and a card with speech bubble pointer
**When to use:** All activity rail entries
**Example:**
```html
{# Source: 62-UI-SPEC.md Component Inventory / 62-CONTEXT.md D-01 through D-04 #}
<div class="flex gap-4 items-start {% if loop.index == 3 %}opacity-75{% elif loop.index > 3 %}opacity-60{% endif %}">
  {# Double-circle dot #}
  <div class="w-7 h-7 rounded-full bg-triggarr-card border-2 border-triggarr-bg flex items-center justify-center shrink-0 z-10 mt-1">
    <div class="w-2.5 h-2.5 rounded-full bg-triggarr-primary"></div>
  </div>
  {# Card with speech bubble pointer #}
  <div class="flex-1 min-w-0 bg-triggarr-card border border-triggarr-border rounded-lg p-3 relative hover:bg-triggarr-elevated transition-colors">
    <div class="absolute -left-[5px] top-4 w-2 h-2 rotate-45 bg-inherit border-l border-b border-triggarr-border"></div>
    {# Card content: app badge, title, outcome + timestamp #}
  </div>
</div>
```

### Pattern 2: GRAB Row Detection (Log Viewer)
**What:** Keyword-based conditional in Jinja2 to detect grab-related log messages and apply green highlight
**When to use:** Each log row rendering
**Example:**
```html
{# Source: 62-CONTEXT.md D-17, 62-UI-SPEC.md GRAB Row Highlight #}
{% set is_grab = entry.message.lower() is search("grab") or
                 entry.message.lower() is search("found release") or
                 entry.message.lower() is search("sent to client") %}
{% if is_grab %}
<div class="flex gap-4 bg-triggarr-primary/10 hover:bg-triggarr-primary/20 px-2 py-0.5 rounded transition-colors group border-l-2 border-triggarr-primary">
  <span class="text-triggarr-muted shrink-0">{{ timestamp }}</span>
  <span class="text-triggarr-primary font-bold w-14 shrink-0">[GRAB]</span>
  <span class="text-triggarr-text truncate group-hover:text-white transition-colors">{{ entry.message }}</span>
</div>
{% endif %}
```

**Note on Jinja2 `search` filter:** Jinja2 does not have a built-in `search` test. Use `"keyword" in entry.message.lower()` instead. [VERIFIED: standard Jinja2 does not include regex search as a test]

### Pattern 3: Phosphor Icon Replacement (Log Viewer)
**What:** Replace inline SVG elements with Phosphor icon `<i>` tags
**When to use:** Pause button, expand button, terminal title icon, footer arrow
**Example:**
```html
{# Source: 62-CONTEXT.md D-12, Phase 60 Phosphor vendoring #}
{# Before (inline SVG): #}
<svg class="w-4 h-4" viewBox="0 0 24 24">...</svg>

{# After (Phosphor): #}
<i class="ph ph-pause text-[15px]"></i>
```

### Anti-Patterns to Avoid
- **Dynamic Tailwind class construction:** Never use `bg-triggarr-{{ variable }}` -- Tailwind JIT cannot scan dynamic strings. Always write full class strings in Jinja2 conditionals. [VERIFIED: Phase 61 PATTERNS.md documents this explicitly]
- **Removing htmx wiring:** Never modify `id`, `hx-get`, `hx-trigger`, or `hx-swap` attributes on the root elements. Only change `class` and inner HTML. [VERIFIED: Phase 61 PATTERNS.md establishes this rule]
- **Breaking JS handler wiring:** The `toggleLogPause(this)` and `toggleLogExpand()` onclick handlers must remain on the new Phosphor icon buttons. [VERIFIED: 62-CONTEXT.md integration points]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Icon rendering | Custom SVG sprites | Phosphor Icons (`ph ph-*` classes) | Already vendored, consistent with Phase 60/61 |
| Pulsing dot animation | Custom CSS animation | Existing `dot-pulse` class in input.css | Already implemented and tested |
| Monospace font | System monospace fallback | `font-mono` / `font-geist-mono` class | Self-hosted Geist Mono already configured |
| Live polling | Custom WebSocket | htmx `hx-trigger="every 5s"` | Already working, no reason to change |

## Common Pitfalls

### Pitfall 1: CSS Class Conflicts with Existing timeline-item/timeline-dot
**What goes wrong:** The current `input.css` defines `.timeline-item` and `.timeline-dot` CSS classes (lines 152-173) with specific positioning. The new card-based layout uses fundamentally different positioning (flex row with gap instead of padding-left with absolute dots).
**Why it happens:** If old CSS classes remain but template structure changes, orphaned styles cause visual glitches.
**How to avoid:** Either (a) remove/replace the `.timeline-item` and `.timeline-dot` CSS rules in input.css and use pure Tailwind utilities in the template, or (b) rename/update the CSS classes to match the new structure. Option (a) is cleaner since the UI-SPEC specifies all classes inline.
**Warning signs:** Timeline dots appearing in wrong position, double borders, unexpected padding.

### Pitfall 2: Speech Bubble Pointer Border Mismatch
**What goes wrong:** The speech bubble pointer (`rotate-45` diamond) must visually continue the card's border. If the card uses `border-dashed` but the pointer uses `border-solid`, it looks broken.
**Why it happens:** D-03 specifies the pointer border style must match the card (solid for grabbed/partial, dashed for searched/failed/unresolved).
**How to avoid:** Use Jinja2 conditionals to apply matching border style to both card and pointer elements.
**Warning signs:** Pointer appears as solid diamond on a dashed card.

### Pitfall 3: Opacity Fading Affects Hover States
**What goes wrong:** `opacity-75` and `opacity-60` on the wrapper div affect ALL children including hover states, making hover less visible on faded entries.
**Why it happens:** CSS opacity is inherited and cannot be overridden by children.
**How to avoid:** This is the intended design per D-07. The opacity fading is a deliberate visual hierarchy. No mitigation needed -- just be aware that hover elevation on faded entries will be subtler.
**Warning signs:** N/A -- this is expected behavior.

### Pitfall 4: Log Filter Option Text Change Breaks Tests
**What goes wrong:** Current filter uses "All", "ERROR", "WARNING", "INFO", "DEBUG" as option text. D-14 changes to "Level: INFO", "Level: WARN", "Level: ERROR", "Level: DEBUG". The test `test_log_viewer_level_filter_dropdown` checks for `value="ERROR"` etc., which remains unchanged. But "WARNING" changes to "WARN" in display text.
**Why it happens:** D-14 uses "WARN" not "WARNING" in the display text.
**How to avoid:** Keep `value` attributes as `ERROR`, `WARNING`, `INFO`, `DEBUG` for server-side filtering (backend expects these). Only change the display `<option>` text to "Level: WARN" etc. Note the asymmetry: value="WARNING" but display text "Level: WARN".
**Warning signs:** Server-side level filtering stops working if values change.

### Pitfall 5: terminal-pane Class Removal Breaks Expanded State
**What goes wrong:** The existing `#log-viewer.expanded` CSS rules in input.css target `#log-viewer` specifically. If the `terminal-pane` class is removed (D-16 replaces it with `bg-[#0b1120]`), the expand functionality still works since CSS targets the ID not the class. However, the test `test_log_viewer_expand_button` asserts `"terminal-pane" in response.text`.
**Why it happens:** Test asserts on a class being removed.
**How to avoid:** Update test assertion. The `.terminal-pane` background CSS can be removed/updated since `bg-[#0b1120]` replaces it.
**Warning signs:** Test failure on `terminal-pane` assertion.

### Pitfall 6: Scanline Overlay Decision
**What goes wrong:** The current log viewer has a `.scanline-overlay` div with a green gradient animation. The UI-SPEC and CONTEXT.md don't explicitly mention it. If kept, it may clash with the new `bg-[#0b1120]` background.
**How to avoid:** This is a Claude's Discretion item. Recommendation: remove it. The new design aesthetic is cleaner (card-based header, explicit row styling) and the scanline effect is a v1 terminal aesthetic that conflicts with the refined v2.7 look. The existing test that checks for `scanline-overlay` will need updating.

## Code Examples

### Activity Rail: Complete Entry Structure
```html
{# Source: 62-UI-SPEC.md Component Inventory, 62-CONTEXT.md D-01 through D-07 #}
{% for entry in entries %}
<div class="flex gap-4 items-start{% if loop.index == 3 %} opacity-75{% elif loop.index > 3 %} opacity-60{% endif %}">
  {# Double-circle timeline dot (D-04) #}
  <div class="w-7 h-7 rounded-full bg-triggarr-card border-2 border-triggarr-bg flex items-center justify-center shrink-0 z-10 mt-1">
    {% if entry.outcome == 'grabbed' %}
    <div class="w-2.5 h-2.5 rounded-full bg-triggarr-primary"></div>
    {% elif entry.outcome == 'partial' %}
    <div class="w-2.5 h-2.5 rounded-full bg-amber-400"></div>
    {% elif entry.outcome == 'searched' %}
    <div class="w-2.5 h-2.5 rounded-full bg-yellow-500"></div>
    {% elif entry.outcome == 'failed' %}
    <div class="w-2.5 h-2.5 rounded-full bg-red-500"></div>
    {% else %}
    <div class="w-2.5 h-2.5 rounded-full bg-gray-500"></div>
    {% endif %}
  </div>

  {# Card (D-01) - solid for grabbed/partial, dashed for others #}
  {% if entry.outcome in ['grabbed', 'partial'] %}
  <div class="flex-1 min-w-0 bg-triggarr-card border border-triggarr-border rounded-lg p-3 relative hover:bg-triggarr-elevated transition-colors">
    <div class="absolute -left-[5px] top-4 w-2 h-2 rotate-45 bg-inherit border-l border-b border-triggarr-border"></div>
  {% else %}
  <div class="flex-1 min-w-0 bg-triggarr-bg border border-dashed border-triggarr-border rounded-lg p-3 relative">
    <div class="absolute -left-[5px] top-4 w-2 h-2 rotate-45 bg-triggarr-bg border-l border-b border-dashed border-triggarr-border"></div>
  {% endif %}

    {# App badge row (D-06) #}
    <div class="flex items-center gap-1.5 mb-1.5">
      {% if entry.app == 'Radarr' %}
      <span class="w-1.5 h-1.5 rounded-full bg-triggarr-radarr"></span>
      {% elif entry.app == 'Sonarr' %}
      <span class="w-1.5 h-1.5 rounded-full bg-triggarr-sonarr"></span>
      {% elif entry.app == 'Lidarr' %}
      <span class="w-1.5 h-1.5 rounded-full bg-triggarr-green"></span>
      {% endif %}
      <span class="text-[10px] font-mono text-triggarr-muted uppercase tracking-wider font-bold">
        {{ entry.app }}{% if entry.instance_id and entry.instance_id != 'Default' %} {{ entry.instance_id }}{% endif %}
      </span>
    </div>

    {# Media title #}
    <p class="text-[13px] font-bold text-triggarr-text truncate mb-2">{{ entry.name }}</p>

    {# Outcome pill + timestamp #}
    <div class="flex items-center justify-between">
      {# outcome pill - text only, no SVG icons #}
      {% if entry.outcome == 'grabbed' %}
      <span class="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-triggarr-primary/10 text-triggarr-primary border border-triggarr-primary/20">grabbed</span>
      {% elif entry.outcome == 'searched' %}
      <span class="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-yellow-500/10 text-yellow-500 border border-yellow-500/20">searched</span>
      {# ... other outcomes #}
      {% endif %}
      <span class="text-[10px] font-mono text-triggarr-muted">{{ entry.timestamp | relative_time }}</span>
    </div>
  </div>
</div>
{% endfor %}
```

### Log Viewer: Header with Phosphor Icons
```html
{# Source: 62-UI-SPEC.md Log Header Bar, 62-CONTEXT.md D-11 through D-15 #}
<div class="flex items-center justify-between px-4 py-2 border-b border-triggarr-border bg-triggarr-card">
  <div class="flex items-center gap-3">
    <i class="ph ph-terminal-window text-triggarr-muted text-lg"></i>
    <span class="font-bold text-xs text-triggarr-text tracking-wide">System Logs</span>
    <div class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-triggarr-bg border border-triggarr-border">
      <span class="relative w-1.5 h-1.5 rounded-full bg-triggarr-primary dot-pulse"></span>
      <span class="text-[10px] font-mono font-bold uppercase tracking-widest text-triggarr-primary">Tailing</span>
    </div>
  </div>
  <div class="flex items-center gap-3">
    <select onchange="..." class="font-mono bg-triggarr-bg border border-triggarr-border text-[10px] text-triggarr-text rounded px-2 py-1 outline-none">
      <option value="">Level: ALL</option>
      <option value="INFO">Level: INFO</option>
      <option value="WARNING">Level: WARN</option>
      <option value="ERROR">Level: ERROR</option>
      <option value="DEBUG">Level: DEBUG</option>
    </select>
    <div class="w-px h-4 bg-triggarr-border"></div>
    <button type="button" title="Pause stream" data-pause-btn onclick="toggleLogPause(this)"
            class="text-triggarr-muted hover:text-triggarr-text transition-colors">
      <i class="ph ph-pause text-[15px]"></i>
    </button>
    <button type="button" title="Expand log to terminal" onclick="toggleLogExpand()"
            class="text-triggarr-muted hover:text-triggarr-text transition-colors">
      <i class="ph ph-corners-out text-[15px]"></i>
    </button>
  </div>
</div>
```

### GRAB Row Keyword Detection
```html
{# Source: 62-CONTEXT.md D-17, Claude's Discretion on keyword list #}
{# Recommended keywords: grab, grabbed, found release, sent to client #}
{% set msg_lower = entry.message.lower() %}
{% set is_grab = "grab" in msg_lower or "found release" in msg_lower or "sent to client" in msg_lower %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat timeline with `.timeline-item` CSS | Card-based flex layout with inline Tailwind | Phase 62 | Complete activity rail restructure |
| Inline SVG icons in log viewer | Phosphor Icons `<i>` tags | Phase 60 (vendored), Phase 62 (log viewer adoption) | Consistent icon system |
| `terminal-pane` CRT aesthetic | Clean `bg-[#0b1120]` with card header | Phase 62 | Modern dark terminal look |
| SVG outcome icons in pills | Text-only outcome pills | Phase 62 | Simpler, matches artifact |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `triggarr-elevated` token (`#233346`) already exists in input.css as `triggarr-card-elevated` | Standard Stack | LOW -- token already verified in input.css, just need to confirm `hover:bg-triggarr-elevated` works or if alias needed |
| A2 | Removing `scanline-overlay` is acceptable (Claude's Discretion item) | Pitfalls | LOW -- user can override if they want to keep it |
| A3 | `font-mono` in Tailwind v4 maps to the custom `font-geist-mono` defined in @theme | Code Examples | LOW -- verified `--font-geist-mono` is defined in @theme but need to confirm Tailwind v4 maps `font-mono` to it |

**Clarification on A1:** The input.css defines both `--color-triggarr-card-elevated: #233346` and `--color-triggarr-elevated: #233346`. The UI-SPEC uses `hover:bg-triggarr-elevated` which maps to the latter. Both tokens exist. [VERIFIED: input.css lines 9-10]

**Clarification on A3:** In Tailwind CSS v4, `font-mono` maps to the `--font-mono` theme variable. The project defines `--font-geist-mono` but NOT `--font-mono`. The UI-SPEC uses `font-mono` throughout. The implementation must either: (a) add `--font-mono: "Geist Mono", ui-monospace, ...` to the @theme block, or (b) continue using `font-geist-mono` class instead of `font-mono`. Checking current usage pattern: the existing templates use `font-geist-mono` everywhere. The UI-SPEC says `font-mono` which would need the theme alias. [VERIFIED: input.css defines `--font-geist-mono` not `--font-mono`]

## Open Questions

1. **`font-mono` vs `font-geist-mono` in UI-SPEC**
   - What we know: input.css defines `--font-geist-mono`. UI-SPEC says `font-mono`. Existing templates use `font-geist-mono`.
   - What's unclear: Whether to add `--font-mono` alias to @theme or continue using `font-geist-mono` class.
   - Recommendation: Add `--font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;` to the @theme block so `font-mono` works. This is a one-line addition and aligns with Tailwind v4 conventions. Alternatively, keep using `font-geist-mono` for consistency with existing templates. Either works -- planner should pick one and be consistent.

2. **Scanline overlay disposition**
   - What we know: Current log viewer has `.scanline-overlay`. UI-SPEC does not mention it. Claude's Discretion item.
   - Recommendation: Remove it. The new design is cleaner. Update the test that checks for it.

3. **`triggarr-primary` token usage in TAILING badge**
   - What we know: UI-SPEC uses `bg-triggarr-primary` and `text-triggarr-primary` for TAILING badge dot and text. The token exists in input.css (added in Phase 61). Current template uses `bg-triggarr-green`/`text-triggarr-green`.
   - Recommendation: Use `triggarr-primary` per UI-SPEC. Both map to `#22c55e` so the visual result is identical, but using `triggarr-primary` is semantically correct.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` (pytest section) |
| Quick run command | `uv run pytest tests/test_activity_rail.py tests/test_log_viewer.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RAIL-01 | Card-based layout with speech bubble pointer and colored timeline dots | unit | `uv run pytest tests/test_activity_rail.py -x -q` | Yes (needs assertion updates) |
| RAIL-02 | App badges use font-mono with colored dot indicators | unit | `uv run pytest tests/test_activity_rail.py::test_entry_has_app_badge -x` | Yes (needs assertion updates) |
| RAIL-03 | Older entries fade with decreasing opacity | unit | `uv run pytest tests/test_activity_rail.py -x -q` | Yes (needs new test) |
| LOG-01 | Phosphor icons for pause/expand controls | unit | `uv run pytest tests/test_log_viewer.py::test_log_viewer_pause_button -x` | Yes (needs assertion updates) |
| LOG-02 | TAILING badge with font-mono and pulsing green dot | unit | `uv run pytest tests/test_log_viewer.py::test_log_viewer_tailing_indicator -x` | Yes (needs assertion updates) |
| LOG-03 | Log level filter with font-mono styled select | unit | `uv run pytest tests/test_log_viewer.py::test_log_viewer_level_filter_dropdown -x` | Yes (needs assertion updates) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_activity_rail.py tests/test_log_viewer.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_activity_rail.py` -- update assertions: remove `timeline-item`/`timeline-dot` checks, add card class checks (`bg-triggarr-card`, `border-dashed`, `w-7`, `w-2.5`), add speech bubble check, add opacity fading test
- [ ] `tests/test_log_viewer.py` -- update assertions: remove `terminal-pane`/`scanline-overlay` checks, add Phosphor icon checks (`ph ph-pause`, `ph ph-corners-out`, `ph ph-terminal-window`), add "System Logs" title check, add GRAB row highlight test, update TAILING badge assertions

### Tests Requiring Updates (Detail)

**test_activity_rail.py changes needed:**
| Current Test | Current Assertion | New Assertion |
|-------------|-------------------|---------------|
| `test_rail_has_sticky_classes` | `"sticky"`, `"top-20"` | `"sticky"`, `"top-[73px]"` (per UI-SPEC) |
| `test_timeline_dots_present` | `"timeline-item"`, `"timeline-dot"` | `"w-7 h-7 rounded-full"`, `"w-2.5 h-2.5 rounded-full"` |
| `test_entry_has_app_badge` | `"bg-orange-500/10"` | `"w-1.5 h-1.5 rounded-full"`, `"font-mono"` or `"font-geist-mono"` |
| `test_outcome_svg_icons` | `"<polyline"`, `"<circle"` | Remove entirely (outcome pills are text-only now) or replace with text-only pill assertions |

**New tests needed for test_activity_rail.py:**
- `test_card_based_layout`: assert `"bg-triggarr-card border border-triggarr-border rounded-lg p-3"` for grabbed entries
- `test_dashed_cards_for_non_grab`: assert `"border-dashed"` present
- `test_speech_bubble_pointer`: assert `"rotate-45"` present
- `test_opacity_fading`: seed 4+ entries, assert `"opacity-75"` and `"opacity-60"` present
- `test_double_circle_dots`: assert `"w-7 h-7"` and `"w-2.5 h-2.5"` present
- `test_rail_header_styling`: assert `"tracking-widest"`, `"text-[13px]"`, `"backdrop-blur-md"` present

**test_log_viewer.py changes needed:**
| Current Test | Current Assertion | New Assertion |
|-------------|-------------------|---------------|
| `test_log_viewer_expand_button` | `"scanline-overlay"`, `"terminal-pane"` | `"ph ph-corners-out"`, `"bg-[#0b1120]"` |
| `test_log_viewer_tailing_indicator` | `"dot-pulse"` | `"dot-pulse"` + `"px-2 py-0.5 rounded bg-triggarr-bg border border-triggarr-border"` |
| `test_log_viewer_pause_button` | (onclick handler check) | Add `"ph ph-pause"` assertion |

**New tests needed for test_log_viewer.py:**
- `test_system_logs_title`: assert `"System Logs"` in response, `"Application Log"` NOT in response
- `test_terminal_icon`: assert `"ph ph-terminal-window"` present
- `test_grab_row_highlight`: seed log entry with "grabbed" keyword, assert `"bg-triggarr-primary/10"` and `"[GRAB]"` present
- `test_level_filter_format`: assert `"Level: INFO"` in option text
- `test_log_header_bar`: assert `"bg-triggarr-card"` in header area
- `test_vertical_divider`: assert `"w-px h-4 bg-triggarr-border"` present

## Security Domain

Not applicable. This phase is pure CSS/HTML restyling with no authentication, data handling, input processing, or API changes. No ASVS categories apply.

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- `uv run pytest tests/ -x -q` must pass after changes
- `uv run ruff check triggarr/ tests/` must pass after changes
- Tailwind CSS rebuild: `uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css`
- No secrets in templates or logs (not relevant for this phase but standard gate)

## Sources

### Primary (HIGH confidence)
- `triggarr/templates/partials/activity_rail.html` -- current template structure (110 lines)
- `triggarr/templates/partials/log_viewer.html` -- current template structure (81 lines)
- `triggarr/static/css/input.css` -- current CSS theme and utility classes (174 lines)
- `tests/test_activity_rail.py` -- current rail test assertions (211 lines)
- `tests/test_log_viewer.py` -- current log viewer test assertions (229 lines)
- `.planning/phases/62-activity-rail-log-viewer/62-CONTEXT.md` -- 18 locked decisions
- `.planning/phases/62-activity-rail-log-viewer/62-UI-SPEC.md` -- complete component inventory
- `.planning/phases/61-stat-cards-app-cards/61-PATTERNS.md` -- established patterns for template restyling

### Secondary (MEDIUM confidence)
- Phase 61 plan structure -- used as reference for plan format expectations

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all libraries already in use
- Architecture: HIGH -- pure template restyling, no architectural changes
- Pitfalls: HIGH -- based on direct code analysis of existing templates and CSS

**Research date:** 2026-04-17
**Valid until:** 2026-05-17 (stable -- no external dependency changes expected)
