# Phase 61: Stat Cards & App Cards - Research

**Researched:** 2026-04-15
**Domain:** Jinja2/Tailwind CSS template restyling (Stat Cards + App Cards)
**Confidence:** HIGH

## Summary

This phase is a pure UI restyling of two existing Jinja2 template partials (`stats_row.html` and `app_card.html`) to match the finalized AIDesigner artifact. No backend changes are needed -- all data wiring and htmx behavior stays intact. The work is entirely in Tailwind utility classes, HTML structure, and Phosphor icon integration.

The artifact defines clear visual specs for stat cards (larger hero numbers, Phosphor icons, restructured mini progress bars) and app cards (colored left borders per app type, header with connection pill + bottom border, recessed sub-cards, app-colored Search Now button). The existing templates already have most of the data bindings; this phase reshapes their presentation layer.

**Primary recommendation:** Modify `stats_row.html` and `app_card.html` in place, class-by-class matching the artifact. No new files, routes, or backend changes needed. Update existing tests to match new class expectations.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Uniform text-[32px] for ALL stat card hero numbers (including Grab Rate). Do not use text-[36px] -- keep consistent sizing across all cards.
- **D-02:** Match Phosphor icons from the AIDesigner artifact exactly. Inspect design.html to determine which icon each card uses -- do not guess or use semantic alternatives.
- **D-03:** Keep the Next Scan card with its existing countdown timer behavior. Restyle to match artifact scale and spacing but preserve the current data wiring.
- **D-04:** Match the artifact's mini progress bar styling exactly -- inspect design.html for bar height, corner radius, label placement, and spacing. Use existing triggarr-radarr (orange #f59e0b) and triggarr-sonarr (blue #3b82f6) color tokens. Keep the existing data wiring in stats_row.html.
- **D-05:** App card connection status displays as a small pill badge in the card header row, next to the instance title, separated by a bottom border per CARD-02.
- **D-06:** Recessed sub-cards for Missing/Cutoff stats match the artifact exactly -- inspect design.html for exact bg treatment, padding, border radius, and internal layout.
- **D-07:** Lidarr app cards use green (triggarr-green #22c55e) for their left border and accents, distinct from Radarr orange and Sonarr blue.
- **D-08:** Search Now button uses app-colored hover accent per CARD-04.
- **D-09:** Pixel-exact match to the AIDesigner artifact where possible. Inspect design.html class-by-class and replicate Tailwind classes, spacing, and colors. Only deviate for dynamic content or responsive behavior.
- **D-10:** Keep current responsive breakpoints (grid-cols-1 md:cols-2 xl:cols-3 for app cards). Do not change responsive behavior unless the artifact explicitly suggests different breakpoints.

### Claude's Discretion
- Exact card subtitle layout for STAT-04 (match artifact)
- How to integrate colored Phosphor icons into existing stat card template structure
- Card shadow/elevation treatment if artifact uses one
- Handling of Lidarr-specific stat cards (Albums) icon and accent color

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STAT-01 | Stat cards use p-5 padding with text-[32px]/text-[36px] hero numbers | Artifact analysis: p-5 confirmed, D-01 locks text-[32px] uniform. Current cards already have p-5 on Grab Rate but p-4 on others -- upgrade all to p-5. |
| STAT-02 | Grab Rate card includes per-app mini progress bars (orange Radarr, blue Sonarr) | Artifact uses h-1 rounded-full bars with text-[10px] labels above, side-by-side layout. Current uses h-6px vertical stack -- restructure to artifact layout. |
| STAT-03 | Movies/Series/Next Scan cards have colored Phosphor icons matching app type | Artifact icons: ph-film-strip (radarr orange), ph-television (sonarr blue), ph-clock-countdown (muted), ph-chart-line-up (green for Grab Rate). |
| STAT-04 | Card subtitles separated by visual structure matching artifact layout | Artifact uses small colored dot + label text below hero number (e.g., "In Radarr"). |
| CARD-01 | App cards use colored left border per app type (orange Radarr, blue Sonarr, red unreachable) | Artifact: border-l-4 border-l-triggarr-radarr/sonarr/danger. Current uses green for connected -- change to app-type color. |
| CARD-02 | App card header has title and connection status pill separated by border-bottom | Artifact: p-4 header div with border-b border-triggarr-border/50. Pill uses rounded (not rounded-full) with uppercase tracking-wider text. |
| CARD-03 | Missing/Cutoff stats displayed in recessed sub-cards with bg-triggarr-bg/50 | Artifact: bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5 grid-cols-2 gap-3 sub-cards. |
| CARD-04 | Search Now button in footer section with app-colored hover accent | Artifact: footer div with p-3 bg-triggarr-bg/30 border-t, button with group hover coloring icon to app color. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Stat card visual styling | Frontend (Jinja2 templates) | -- | Pure CSS/HTML class changes |
| App card visual styling | Frontend (Jinja2 templates) | -- | Pure CSS/HTML class changes |
| Mini progress bar layout | Frontend (Jinja2 templates + CSS) | -- | Restructure HTML, possibly update mini-bar CSS |
| App-type color mapping | Frontend (Jinja2 templates) | -- | Conditional Jinja2 logic for border/accent colors based on `app.name` |
| Data wiring | None (preserved) | -- | No backend changes needed |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | v4 | Utility-first CSS framework | Already in project, all styling via utility classes [VERIFIED: input.css @import "tailwindcss"] |
| Phosphor Icons | vendored | Icon library | Already vendored at static/vendor/phosphor/, `<i class="ph ph-*">` markup [VERIFIED: CONTEXT.md code_context] |
| Jinja2 | (via FastAPI) | Template engine | Existing template partials, htmx-compatible [VERIFIED: existing templates] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| htmx | (already loaded) | Partial updates | Existing hx-get/hx-swap on stats_row and app_card -- preserve as-is |

No new libraries needed for this phase.

## Architecture Patterns

### System Architecture Diagram

```
Browser Request
      |
      v
FastAPI Route (partial_stats_row / partial_app_card)
      |
      v
_build_app_context() --> reads app.state.triggarr_state
      |
      v
Jinja2 Template Rendering
  stats_row.html  -- stat cards (Grab Rate, Movies, Episodes, Albums, Time to Grab)
  app_card.html   -- per-instance cards (Radarr/Sonarr/Lidarr)
      |
      v
HTML Fragment Response (htmx outerHTML swap)
```

No changes to this flow. All modifications are within the Jinja2 templates.

### Recommended Project Structure

No new files. Modify in place:
```
triggarr/
├── templates/partials/
│   ├── stats_row.html     # Stat card restyling (STAT-01 through STAT-04)
│   └── app_card.html      # App card restyling (CARD-01 through CARD-04)
├── static/css/
│   └── input.css          # Update mini-bar CSS if needed
tests/
├── test_stats_health.py   # Update assertions for new classes
└── test_app_cards.py      # Update assertions for new classes/structure
```

### Pattern 1: Artifact-to-Template Class Extraction

**What:** Extract exact Tailwind classes from the design artifact HTML and apply them to the Jinja2 template counterpart.
**When to use:** Every visual change in this phase.
**Example:**

Artifact stat card structure:
```html
<!-- Source: design.html line 119-137 -->
<div class="bg-triggarr-card border border-triggarr-border rounded-lg p-5 flex flex-col justify-between">
    <div class="flex justify-between items-start mb-4">
        <span class="text-xs font-bold tracking-widest uppercase text-triggarr-muted">Grab Rate</span>
        <i class="ph ph-chart-line-up text-lg text-triggarr-primary"></i>
    </div>
    <div>
        <div class="text-[32px] md:text-[36px] font-bold text-triggarr-text leading-none mb-4">94%</div>
        <!-- mini bars -->
    </div>
</div>
```

Per D-01, use `text-[32px]` uniformly (not md:text-[36px]).

### Pattern 2: App-Type Conditional Coloring (Jinja2)

**What:** Use Jinja2 conditionals to apply app-type-specific colors to borders and accents.
**When to use:** CARD-01 (left border), CARD-04 (Search Now hover).
**Example:**
```jinja2
{# Left border color based on app type, red override for unreachable #}
{% if app.connected == false %}
  border-l-triggarr-danger
{% elif app.name == 'radarr' %}
  border-l-triggarr-radarr
{% elif app.name == 'sonarr' %}
  border-l-triggarr-sonarr
{% elif app.name == 'lidarr' %}
  border-l-triggarr-green
{% endif %}
```

### Pattern 3: Recessed Sub-Cards for Stats

**What:** Wrap Missing/Cutoff stats in visually recessed containers.
**When to use:** CARD-03.
**Example from artifact (design.html line 183-191):**
```html
<div class="grid grid-cols-2 gap-3 mb-5">
    <div class="bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5">
        <span class="block text-[10px] text-triggarr-muted uppercase tracking-wider">Missing</span>
        <span class="block text-lg font-bold text-triggarr-text mt-1">112</span>
    </div>
    <div class="bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5">
        <span class="block text-[10px] text-triggarr-muted uppercase tracking-wider">Cutoff Unmet</span>
        <span class="block text-lg font-bold text-triggarr-text mt-1">45</span>
    </div>
</div>
```

### Anti-Patterns to Avoid
- **Approximating artifact classes:** Do not use `text-3xl` when artifact says `text-[32px]`. Use exact arbitrary values. [VERIFIED: AIDesigner skill rule - "Do not substitute approximate values"]
- **Changing data wiring:** Do not modify Jinja2 template variables, htmx attributes, or route logic. Only change HTML structure and CSS classes.
- **Breaking existing responsive behavior:** D-10 locks current breakpoints. Do not change grid-cols responsive classes for app cards.

## Artifact Class-by-Class Extraction

### Stat Cards (design.html lines 118-174)

**Grab Rate Card:**
| Element | Artifact Classes | Current Classes | Change |
|---------|-----------------|-----------------|--------|
| Card wrapper | `bg-triggarr-card border border-triggarr-border rounded-lg p-5 flex flex-col justify-between` | `bg-triggarr-card rounded-lg border border-triggarr-border p-5 shadow-sm relative overflow-hidden` | Add flex-col justify-between, keep shadow-sm |
| Label row | `flex justify-between items-start mb-4` | `flex items-center justify-between` | Add mb-4, change items-center to items-start |
| Label text | `text-xs font-bold tracking-widest uppercase text-triggarr-muted` | `text-xs uppercase tracking-wide text-triggarr-muted` | Add font-bold, change tracking-wide to tracking-widest |
| Icon | `ph ph-chart-line-up text-lg text-triggarr-primary` | (none -- badge instead) | Add Phosphor icon, keep health badge separately |
| Hero number | `text-[32px] font-bold text-triggarr-text leading-none mb-4` | `text-4xl font-bold mt-2 leading-none` | Change text-4xl to text-[32px] per D-01, add mb-4 |
| Mini bar layout | Side-by-side `flex items-center justify-between gap-4`, each `flex-1` | Vertical stack `space-y-2` | Restructure to horizontal layout |
| Mini bar height | `h-1 bg-triggarr-bg rounded-full overflow-hidden` | `.mini-bar` (6px) | Change to h-1 (4px) rounded-full |
| Mini bar label | `text-[10px] text-triggarr-muted mb-1`, label+percentage on same row above bar | `text-[11px]` labels inline with bar | Move labels above bar, reduce to text-[10px] |

**Movies Card:**
| Element | Artifact Classes |
|---------|-----------------|
| Icon | `ph ph-film-strip text-lg text-triggarr-radarr` |
| Hero number | `text-[32px] font-bold text-triggarr-text leading-none mb-3` (D-01: use text-[32px]) |
| Subtitle | `flex items-center text-xs text-triggarr-muted gap-1.5` with `w-1.5 h-1.5 rounded-full bg-triggarr-radarr opacity-80` dot + "In Radarr" |

**Series Card:**
| Element | Artifact Classes |
|---------|-----------------|
| Icon | `ph ph-television text-lg text-triggarr-sonarr` |
| Subtitle | Same pattern as Movies but with `bg-triggarr-sonarr` dot + "In Sonarr" |

**Next Scan Card:**
| Element | Artifact Classes |
|---------|-----------------|
| Icon | `ph ph-clock-countdown text-lg text-triggarr-muted` |
| Subtitle | `flex items-center text-xs text-triggarr-muted gap-1.5` with `ph ph-calendar text-sm text-triggarr-primary` icon + "Scheduled automatically" |

### App Cards (design.html lines 176-240)

**Connected App Card:**
| Element | Artifact Classes | Current Classes | Change |
|---------|-----------------|-----------------|--------|
| Card wrapper | `bg-triggarr-card border border-triggarr-border border-l-4 border-l-triggarr-radarr rounded-lg overflow-hidden flex flex-col shadow-sm` | `bg-triggarr-card rounded-lg border border-triggarr-border p-5 shadow-sm card-hover border-l-4 border-l-triggarr-green` | Change border-l color to app-type, add overflow-hidden flex flex-col, remove p-5 (padding moves to sections) |
| Header section | `p-4 border-b border-triggarr-border/50 flex justify-between items-center` | `flex items-center justify-between` (no border-b, no p-4) | Add p-4 and border-b |
| Title | `font-bold text-triggarr-text text-[15px]` | `text-lg font-semibold` | Change to text-[15px] font-bold |
| Connection pill | `px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-triggarr-primary/10 text-triggarr-primary border border-triggarr-primary/20` | `rounded-full bg-triggarr-green/15 text-triggarr-green` (with dot-pulse dot) | Change to rounded (not rounded-full), add border, add uppercase tracking-wider font-bold |
| Body section | `p-4 flex-1` | (was inside single p-5 card) | New section wrapper |
| Schedule row | `text-[11px] font-mono text-triggarr-muted mb-4 flex justify-between` | `text-xs text-triggarr-muted border-b border-triggarr-border/50 pb-3` | Add font-mono, change to mb-4, remove border-b (now on header) |
| Stats grid | `grid grid-cols-2 gap-3 mb-5` with recessed sub-cards | `grid grid-cols-2 gap-4 mt-3` with plain text | Add recessed sub-card wrappers |
| Sub-card | `bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5` | (none) | New wrapper elements |
| Sub-card label | `text-[10px] text-triggarr-muted uppercase tracking-wider` | `text-xs uppercase tracking-wide text-triggarr-muted` | Change to text-[10px], tracking-wider |
| Sub-card value | `text-lg font-bold text-triggarr-text mt-1` | `text-sm font-medium` | Increase to text-lg font-bold |
| Footer section | `p-3 bg-triggarr-bg/30 border-t border-triggarr-border/50` | `flex items-center gap-3 mt-4 pt-3 border-t border-triggarr-border/50` | New wrapper with bg-triggarr-bg/30 |
| Search Now button | `w-full flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-elevated hover:bg-triggarr-border border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-text group` | `bg-triggarr-green/20 text-triggarr-green text-xs font-medium px-3 py-1.5 rounded` | Major restyle: full-width, elevated bg, icon with group-hover app color |
| Search icon | `ph ph-magnifying-glass group-hover:text-triggarr-radarr transition-colors` | (none) | Add Phosphor search icon with app-colored hover |

**Unreachable App Card:**
| Element | Artifact Classes |
|---------|-----------------|
| Card wrapper | `border-l-triggarr-danger` + danger gradient overlay |
| Title | `text-triggarr-muted` (dimmed) |
| Connection pill | `bg-triggarr-danger/10 text-triggarr-danger border border-triggarr-danger/20` |
| Body | Centered error message with `ph ph-warning-circle text-[40px] text-triggarr-danger/40` |
| Retry button | `bg-triggarr-card hover:bg-triggarr-elevated` with `ph ph-arrows-clockwise` icon |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Icon library | Custom SVGs | Phosphor Icons (vendored) | Already vendored, consistent with Phase 60 header [VERIFIED: CONTEXT.md] |
| Color tokens | Hardcoded hex values | Tailwind theme tokens (triggarr-radarr, etc.) | Already defined in input.css @theme [VERIFIED: input.css] |
| Progress bars | JavaScript animated bars | CSS width + Tailwind utilities | Current approach works, just change dimensions |

## Common Pitfalls

### Pitfall 1: Breaking htmx Partial Swap IDs
**What goes wrong:** Changing the outermost `<div>` id or hx-* attributes breaks live polling.
**Why it happens:** When restructuring card HTML, easy to accidentally move or remove the id="stats-row" or id="{{ app.card_id }}-card" attributes.
**How to avoid:** Keep the outermost div with its id, hx-get, hx-trigger, and hx-swap attributes untouched. Only change classes and inner HTML structure.
**Warning signs:** Cards stop auto-refreshing after template change.

### Pitfall 2: Stat Card Grid Column Count Mismatch
**What goes wrong:** The stats row currently uses a 5-column grid (md:grid-cols-5) that adjusts based on enabled apps. The artifact uses a 4-column layout (lg:grid-cols-4). Changing grid columns without considering the conditional logic breaks filtered views.
**Why it happens:** The current template has `{% if instance_app_type %}md:grid-cols-3{% else %}md:grid-cols-5{% endif %}` logic.
**How to avoid:** Match the artifact's `grid-cols-1 md:grid-cols-2 lg:grid-cols-4` for the unfiltered case. Test with different instance filter selections. Note: the current "Time to Grab" card may not exist in the artifact -- need to check if it maps to "Next Scan" or should be treated separately.
**Warning signs:** Cards stack oddly or leave empty grid cells.

### Pitfall 3: Existing Test Assertions on Old Classes
**What goes wrong:** Tests like `test_grab_rate_hero_card_layout` assert `"text-4xl font-bold"` -- this will fail when changed to `text-[32px]`.
**Why it happens:** Tests lock visual structure via class string matching.
**How to avoid:** Update test assertions in the same commit as template changes. Tests in `test_stats_health.py` and `test_app_cards.py` will need updates.
**Warning signs:** Tests fail on class assertions.

### Pitfall 4: App Card Padding Restructure
**What goes wrong:** Current app card uses a single `p-5` on the outer div. Artifact uses sectioned padding (p-4 header, p-4 body, p-3 footer). Moving to sectioned layout without removing outer p-5 causes double padding.
**Why it happens:** The outer div padding must be removed when sections get their own padding.
**How to avoid:** Remove p-5 from outer div, add padding to each section (header, body, footer).

### Pitfall 5: Mini Bar CSS Conflict
**What goes wrong:** The `.mini-bar` class in input.css defines `height: 6px` and `border-radius: 3px`. The artifact uses `h-1` (4px) and `rounded-full`. Using Tailwind classes on elements that also have the `.mini-bar` class creates specificity conflicts.
**Why it happens:** CSS custom class and Tailwind utility compete for the same property.
**How to avoid:** Either update the `.mini-bar` CSS to match the artifact, or replace the custom class entirely with Tailwind utilities. The artifact uses `w-full h-1 bg-triggarr-bg rounded-full overflow-hidden` with an inner `h-full bg-triggarr-radarr rounded-full` span.

### Pitfall 6: Stat Row Grid Change (4 cols vs 5 cols)
**What goes wrong:** Current stats row has 5 cards (Grab Rate spanning 2 + Movies + Episodes + Time to Grab). The artifact has 4 cards (Grab Rate + Movies + Series + Next Scan) in a 4-column grid. The "Time to Grab" card needs to map to "Next Scan" or be reconciled.
**Why it happens:** Artifact has different card count than current implementation.
**How to avoid:** Map current "Time to Grab" to artifact "Next Scan" card. The current template also has an Albums card (Lidarr) that doesn't appear in the artifact -- preserve it with appropriate icon/color per D-07. Adjust grid to lg:grid-cols-4 base but account for Lidarr presence.

## Code Examples

### Stat Card with Phosphor Icon and Hero Number
```jinja2
{# Source: design.html lines 138-149, adapted for Jinja2 #}
<div class="bg-triggarr-card border border-triggarr-border rounded-lg p-5 flex flex-col justify-between shadow-sm">
    <div class="flex justify-between items-start mb-4">
        <span class="text-xs font-bold tracking-widest uppercase text-triggarr-muted">Movies</span>
        <i class="ph ph-film-strip text-lg text-triggarr-radarr"></i>
    </div>
    <div>
        <div class="text-[32px] font-bold text-triggarr-text leading-none mb-3">
            {{ stats.movies_found + stats.movies_updated }}
        </div>
        <div class="flex items-center text-xs text-triggarr-muted gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-triggarr-radarr opacity-80"></span>In Radarr
        </div>
    </div>
</div>
```

### App Card with Colored Left Border and Sectioned Layout
```jinja2
{# Source: design.html lines 176-199, adapted for Jinja2 #}
<div id="{{ app.card_id }}-card"
     hx-get="{{ request.url_for('partial_app_card', app_name=app.name, instance_name=app.instance) }}"
     hx-trigger="every 5s"
     hx-swap="outerHTML"
     class="bg-triggarr-card border border-triggarr-border border-l-4
            {% if app.connected == false %}border-l-triggarr-danger{% elif app.name == 'radarr' %}border-l-triggarr-radarr{% elif app.name == 'sonarr' %}border-l-triggarr-sonarr{% elif app.name == 'lidarr' %}border-l-triggarr-green{% endif %}
            rounded-lg overflow-hidden flex flex-col shadow-sm card-hover
            {% if app.connected == false %}danger-stripes relative{% endif %}">
    <!-- Header with border-b -->
    <div class="p-4 border-b border-triggarr-border/50 flex justify-between items-center">
        <h3 class="font-bold text-triggarr-text text-[15px]">{{ app.name | capitalize }}{% if app.instance != 'Default' %} <span class="text-sm font-normal text-triggarr-muted">/ {{ app.instance }}</span>{% endif %}</h3>
        <!-- connection pill -->
    </div>
    <!-- Body -->
    <div class="p-4 flex-1">
        <!-- schedule row, stats sub-cards -->
    </div>
    <!-- Footer -->
    <div class="p-3 bg-triggarr-bg/30 border-t border-triggarr-border/50">
        <!-- Search Now button with app-colored hover -->
    </div>
</div>
```

### Search Now Button with App-Colored Hover
```jinja2
{# Source: design.html lines 194-198 #}
<button hx-post="{{ request.url_for('search_now', app_name=app.name, instance_name=app.instance) }}"
        hx-target="#{{ app.card_id }}-card"
        hx-swap="outerHTML"
        class="w-full flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-elevated hover:bg-triggarr-border border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-text group">
    <i class="ph ph-magnifying-glass group-hover:text-triggarr-{{ app.name if app.name != 'lidarr' else 'green' }} transition-colors"></i>Search Now
</button>
```

Note: The `group-hover:text-triggarr-{{ app.name }}` dynamic class approach may not work with Tailwind's JIT/AOT scanning. Tailwind needs to see full class strings in source to generate them. Use explicit conditionals instead:
```jinja2
{% if app.name == 'radarr' %}group-hover:text-triggarr-radarr{% elif app.name == 'sonarr' %}group-hover:text-triggarr-sonarr{% elif app.name == 'lidarr' %}group-hover:text-triggarr-green{% endif %}
```

### Recessed Sub-Cards for Missing/Cutoff
```jinja2
{# Source: design.html lines 183-191 #}
<div class="grid grid-cols-2 gap-3 mb-5{% if app.connected == false %} opacity-60{% endif %}">
    <div class="bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5">
        <span class="block text-[10px] text-triggarr-muted uppercase tracking-wider">Missing</span>
        <span class="block text-lg font-bold text-triggarr-text mt-1">
            {{ app.missing_count if app.missing_count is not none else '—' }}
        </span>
    </div>
    <div class="bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5">
        <span class="block text-[10px] text-triggarr-muted uppercase tracking-wider">Cutoff Unmet</span>
        <span class="block text-lg font-bold text-triggarr-text mt-1">
            {{ app.cutoff_count if app.cutoff_count is not none else '—' }}
        </span>
    </div>
</div>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Green/red left border by connection status | App-type colored left border (orange/blue/green/red) | This phase | Border indicates app identity, not just health |
| text-lg/text-4xl hero numbers | text-[32px] uniform hero numbers | This phase (D-01) | Consistent large scale across all stat cards |
| Plain text stats in app cards | Recessed sub-cards with bg/border | This phase | Visual hierarchy improvement |
| Generic green Search Now button | App-colored hover accent button | This phase | Color consistency per app type |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The "Time to Grab" stat card maps to the artifact's "Next Scan" card | Pitfall 6 | Card may be missing from redesign or need different treatment |
| A2 | Albums card (Lidarr) should use `ph ph-music-notes` or `ph ph-vinyl-record` icon since it's not in the artifact | Claude's Discretion | Wrong icon choice, but easily corrected |
| A3 | Tailwind v4 `@source` directive will scan Jinja2 templates for dynamic class strings like `border-l-triggarr-radarr` when written as full strings in conditionals | Code Examples | If not, classes won't be generated and borders will be invisible |

## Open Questions

1. **Time to Grab vs Next Scan mapping**
   - What we know: Current template has a "Time to Grab" card showing avg search-to-grab time. Artifact has a "Next Scan" card showing countdown to next scan.
   - What's unclear: Are these the same card restyled, or should both exist? The current stats_row.html has both the "Time to Grab" card and Next Scan timing may come from the countdown timer elsewhere.
   - Recommendation: Map "Time to Grab" to "Next Scan" since the artifact's 4-card layout doesn't have room for both. The "avg search to grab" stat is less critical than next scan countdown. [ASSUMED]

2. **Albums card Phosphor icon**
   - What we know: Artifact doesn't include a Lidarr/Albums card. D-07 says Lidarr uses green accents.
   - What's unclear: Which Phosphor icon to use for Albums.
   - Recommendation: Use `ph ph-music-notes` (matches media theme) with `text-triggarr-green` coloring. [ASSUMED]

3. **Stat row grid columns with Lidarr**
   - What we know: Artifact has 4-column grid (Grab Rate + Movies + Series + Next Scan). Current has 5 columns (Grab Rate spans 2 + Movies + Episodes + Time to Grab). With Lidarr enabled, current has an additional Albums card.
   - What's unclear: How to handle 5+ stat cards in a 4-column grid when Lidarr is also enabled.
   - Recommendation: Keep the current conditional grid logic that adjusts columns based on enabled apps. With all three apps, use a 5-column or wrapping layout. [ASSUMED]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml (asyncio_mode=auto) |
| Quick run command | `uv run pytest tests/test_stats_health.py tests/test_app_cards.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STAT-01 | p-5 padding + text-[32px] hero numbers on all stat cards | unit | `uv run pytest tests/test_stats_health.py::test_grab_rate_hero_card_layout -x` | Exists -- needs assertion update |
| STAT-02 | Mini progress bars with app colors in Grab Rate card | unit | `uv run pytest tests/test_stats_health.py::test_per_app_bars_with_colors -x` | Exists -- needs assertion update for new layout |
| STAT-03 | Phosphor icons on Movies/Series/Next Scan cards | unit | `uv run pytest tests/test_stats_health.py::test_stat_cards_have_phosphor_icons -x` | New test needed |
| STAT-04 | Card subtitle visual structure | unit | `uv run pytest tests/test_stats_health.py::test_stat_card_subtitles -x` | New test needed |
| CARD-01 | App-type colored left border | unit | `uv run pytest tests/test_app_cards.py::test_app_card_border_color -x` | New test needed |
| CARD-02 | Header with border-b separator | unit | `uv run pytest tests/test_app_cards.py::test_card_header_border_bottom -x` | New test needed |
| CARD-03 | Recessed sub-cards for Missing/Cutoff | unit | `uv run pytest tests/test_app_cards.py::test_recessed_subcards -x` | New test needed |
| CARD-04 | Search Now button with app-colored hover | unit | `uv run pytest tests/test_app_cards.py::test_search_button_app_colored_hover -x` | New test needed |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_stats_health.py tests/test_app_cards.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_stats_health.py` -- update existing assertions for new class names (text-[32px], tracking-widest, Phosphor icons)
- [ ] `tests/test_stats_health.py::test_stat_cards_have_phosphor_icons` -- new test for STAT-03
- [ ] `tests/test_stats_health.py::test_stat_card_subtitles` -- new test for STAT-04
- [ ] `tests/test_app_cards.py::test_app_card_border_color` -- new test for CARD-01 (app-type border)
- [ ] `tests/test_app_cards.py::test_card_header_border_bottom` -- new test for CARD-02
- [ ] `tests/test_app_cards.py::test_recessed_subcards` -- new test for CARD-03
- [ ] `tests/test_app_cards.py::test_search_button_app_colored_hover` -- new test for CARD-04

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- pytest-asyncio with asyncio_mode=auto
- Tailwind CSS v4 with `uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css` for CSS compilation
- Run `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/` before completing

## Sources

### Primary (HIGH confidence)
- design.html artifact (lines 118-240) -- pixel-exact source of truth for all visual specs [VERIFIED: direct file read]
- `triggarr/templates/partials/stats_row.html` -- current stat card template [VERIFIED: direct file read]
- `triggarr/templates/partials/app_card.html` -- current app card template [VERIFIED: direct file read]
- `triggarr/static/css/input.css` -- Tailwind theme tokens and custom CSS [VERIFIED: direct file read]
- `tests/test_stats_health.py` and `tests/test_app_cards.py` -- existing test assertions [VERIFIED: direct file read]
- `triggarr/web/routes.py` -- _build_app_context() data shape [VERIFIED: direct file read]

### Secondary (MEDIUM confidence)
- AIDesigner frontend skill (SKILL.md) -- design-to-code porting methodology [VERIFIED: direct file read]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all verified in codebase
- Architecture: HIGH -- pure template restyling, no structural changes
- Pitfalls: HIGH -- identified from direct comparison of current vs artifact code

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable -- pure CSS/template work)
