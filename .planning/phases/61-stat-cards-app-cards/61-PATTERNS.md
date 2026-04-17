# Phase 61: Stat Cards & App Cards - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 4 modified files + 2 test files
**Analogs found:** 6 / 6 (all files are modifications of existing code)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/templates/partials/stats_row.html` | component | request-response | Self (current version) + design.html lines 118-174 | exact |
| `triggarr/templates/partials/app_card.html` | component | request-response | Self (current version) + design.html lines 176-240 | exact |
| `triggarr/static/css/input.css` | config | N/A | Self (current version) | exact |
| `triggarr/templates/dashboard.html` | component | request-response | Self (current version) | exact |
| `tests/test_stats_health.py` | test | N/A | Self (current version) | exact |
| `tests/test_app_cards.py` | test | N/A | Self (current version) | exact |

## Pattern Assignments

### `triggarr/templates/partials/stats_row.html` (component, request-response)

**Analog:** Current `stats_row.html` + design artifact

**htmx wiring pattern -- PRESERVE AS-IS** (lines 1-6):
```html
<div id="stats-row"
     hx-get="{{ request.url_for('partial_stats_row') }}"
     hx-trigger="every 30s"
     hx-swap="outerHTML"
     hx-include="[name='instance']"
     class="grid grid-cols-2 {% if instance_app_type %}md:grid-cols-3{% else %}md:grid-cols-5{% endif %} gap-3 mb-4">
```
Do NOT change id, hx-get, hx-trigger, hx-swap, or hx-include. Only modify the class attribute and inner HTML structure.

**Stat card wrapper pattern** (artifact design.html line 119):
```html
<div class="bg-triggarr-card border border-triggarr-border rounded-lg p-5 flex flex-col justify-between shadow-sm">
```
Apply to ALL stat cards (Grab Rate, Movies, Episodes, Albums, Time to Grab/Next Scan). Current Movies/Episodes/Albums cards use `p-4` -- upgrade to `p-5`. Add `flex flex-col justify-between`.

**Label row pattern** (artifact design.html lines 120-123):
```html
<div class="flex justify-between items-start mb-4">
    <span class="text-xs font-bold tracking-widest uppercase text-triggarr-muted">Grab Rate</span>
    <i class="ph ph-chart-line-up text-lg text-triggarr-primary"></i>
</div>
```
Current uses `items-center` and `tracking-wide` -- change to `items-start`, `tracking-widest`, add `font-bold` and `mb-4`.

**Hero number pattern** (artifact design.html line 125, per D-01 use text-[32px] only):
```html
<div class="text-[32px] font-bold text-triggarr-text leading-none mb-4">94%</div>
```
Current Grab Rate uses `text-4xl` -- change to `text-[32px]`. Current Movies/Episodes/Albums use `text-lg` -- upgrade to `text-[32px]`. D-01 locks uniform `text-[32px]` across ALL cards (do NOT use `md:text-[36px]` from artifact).

**Phosphor icon assignments** (artifact design.html lines 122, 141, 153, 165):
| Card | Icon class | Color class |
|------|-----------|-------------|
| Grab Rate | `ph ph-chart-line-up` | `text-triggarr-primary` (note: need `--color-triggarr-primary` token or use `text-triggarr-green`) |
| Movies | `ph ph-film-strip` | `text-triggarr-radarr` |
| Series/Episodes | `ph ph-television` | `text-triggarr-sonarr` |
| Albums (Lidarr) | `ph ph-music-notes` | `text-triggarr-green` |
| Next Scan | `ph ph-clock-countdown` | `text-triggarr-muted` |

**Note on `triggarr-primary`:** The artifact uses `text-triggarr-primary` but the current `input.css` @theme does not define `--color-triggarr-primary`. It defines `--color-triggarr-green: #22c55e` and `--color-triggarr-primaryDark: #16a34a`. Either add `--color-triggarr-primary: #22c55e;` to input.css, or substitute `text-triggarr-green` where artifact says `text-triggarr-primary`. Also needed: `--color-triggarr-elevated` for app card buttons (artifact uses `bg-triggarr-elevated`; current CSS has `#233346` in `.card-hover` but not as a Tailwind token). Check if `triggarr-card-elevated` already exists -- yes it does: `--color-triggarr-card-elevated: #233346`.

**Card subtitle pattern** (artifact design.html lines 145-147):
```html
<div class="flex items-center text-xs text-triggarr-muted gap-1.5">
    <span class="w-1.5 h-1.5 rounded-full bg-triggarr-radarr opacity-80"></span>In Radarr
</div>
```
Current Movies/Episodes/Albums cards use plain `<p class="text-xs text-triggarr-muted mt-1">` -- replace with colored dot + label.

**Mini progress bar pattern** (artifact design.html lines 126-135):
```html
<div class="flex items-center justify-between gap-4 mt-2">
    <div class="flex-1">
        <div class="flex justify-between text-[10px] text-triggarr-muted mb-1"><span>Radarr</span><span>96%</span></div>
        <div class="w-full h-1 bg-triggarr-bg rounded-full overflow-hidden"><div class="h-full bg-triggarr-radarr rounded-full" style="width: 96%;"></div></div>
    </div>
    <div class="flex-1">
        <div class="flex justify-between text-[10px] text-triggarr-muted mb-1"><span>Sonarr</span><span>91%</span></div>
        <div class="w-full h-1 bg-triggarr-bg rounded-full overflow-hidden"><div class="h-full bg-triggarr-sonarr rounded-full" style="width: 91%;"></div></div>
    </div>
</div>
```
Current uses vertical `space-y-2` stack with `.mini-bar` class (6px height). Change to horizontal `flex gap-4` layout with Tailwind utility bars (`h-1 rounded-full`). Either remove `.mini-bar` class from elements or update the CSS. Recommend replacing `.mini-bar` class with pure Tailwind utilities to match artifact exactly.

**Next Scan card subtitle pattern** (artifact design.html lines 169-171):
```html
<div class="flex items-center text-xs text-triggarr-muted gap-1.5">
    <i class="ph ph-calendar text-sm text-triggarr-primary"></i>Scheduled automatically
</div>
```

---

### `triggarr/templates/partials/app_card.html` (component, request-response)

**Analog:** Current `app_card.html` + design artifact

**htmx wiring pattern -- PRESERVE AS-IS** (lines 1-5):
```html
<div id="{{ app.card_id }}-card"
     hx-get="{{ request.url_for('partial_app_card', app_name=app.name, instance_name=app.instance) }}"
     hx-trigger="every 5s"
     hx-swap="outerHTML"
```
Do NOT change id, hx-get, hx-trigger, hx-swap. Only modify the class attribute and inner HTML structure.

**Card wrapper pattern** (artifact design.html line 176):
```html
class="bg-triggarr-card border border-triggarr-border border-l-4 border-l-triggarr-radarr rounded-lg overflow-hidden flex flex-col shadow-sm"
```
Current uses `p-5` on outer div -- REMOVE (padding moves to sections). Add `overflow-hidden flex flex-col`. Change left border from connection-status-based to app-type-based.

**App-type conditional border pattern** (Jinja2 -- new):
```jinja2
{% if app.connected == false %}border-l-triggarr-danger{% elif app.name == 'radarr' %}border-l-triggarr-radarr{% elif app.name == 'sonarr' %}border-l-triggarr-sonarr{% elif app.name == 'lidarr' %}border-l-triggarr-green{% endif %}
```
Current (line 6): `border-l-triggarr-green` for connected, `border-l-red-500` for unreachable. Change to app-type color with red override only for unreachable.

**Header section pattern** (artifact design.html line 177-179):
```html
<div class="p-4 border-b border-triggarr-border/50 flex justify-between items-center">
    <h3 class="font-bold text-triggarr-text text-[15px]">Radarr Main</h3>
    <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-triggarr-primary/10 text-triggarr-primary border border-triggarr-primary/20">Connected</span>
</div>
```
Current header has no `p-4`, no `border-b`, uses `text-lg font-semibold` title and `rounded-full` pills with dot-pulse dots. Change to `text-[15px] font-bold` title, `rounded` pills (not `rounded-full`), add `uppercase tracking-wider font-bold`, add border on pill.

**Connection pill patterns** (artifact design.html lines 179, 228):
```html
<!-- Connected -->
<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-triggarr-primary/10 text-triggarr-primary border border-triggarr-primary/20">Connected</span>

<!-- Unreachable -->
<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-triggarr-danger/10 text-triggarr-danger border border-triggarr-danger/20">Unreachable</span>
```
Current connected pill (app_card.html line 12-14): `inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full bg-triggarr-green/15 text-triggarr-green` with dot-pulse dot inside. Artifact removes the animated dot and uses simpler text-only pill with `rounded` (not `rounded-full`).

**Body section pattern** (artifact design.html line 181):
```html
<div class="p-4 flex-1">
```
New section wrapper -- currently the body content is directly inside the single `p-5` card.

**Schedule row pattern** (artifact design.html line 182):
```html
<div class="text-[11px] font-mono text-triggarr-muted mb-4 flex justify-between">
    <span>Last run: 45m ago</span><span>Next: 2h 14m</span>
</div>
```
Current (line 44): `mt-3 flex items-center justify-between text-xs text-triggarr-muted border-b border-triggarr-border/50 pb-3`. Change: add `font-mono`, change to `mb-4`, remove `border-b pb-3` (border-b now on header section).

**Recessed sub-cards pattern** (artifact design.html lines 183-192):
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
Current (line 50): `grid grid-cols-2 gap-4 mt-3` with plain text labels (`text-xs uppercase tracking-wide`) and values (`text-sm font-medium`). Wrap in recessed sub-card divs, change `gap-4` to `gap-3`, change `mt-3` to remove (schedule row provides spacing via `mb-4`), add `mb-5`. Upgrade label to `text-[10px] tracking-wider`, value to `text-lg font-bold`.

**Footer section pattern** (artifact design.html lines 194-198):
```html
<div class="p-3 bg-triggarr-bg/30 border-t border-triggarr-border/50">
    <button class="w-full flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-elevated hover:bg-triggarr-border border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-text group">
        <i class="ph ph-magnifying-glass group-hover:text-triggarr-radarr transition-colors"></i>Search Now
    </button>
</div>
```
Current (line 93): `flex items-center gap-3 mt-4 pt-3 border-t border-triggarr-border/50`. Change to new footer wrapper with `p-3 bg-triggarr-bg/30`. Button changes from `bg-triggarr-green/20 text-triggarr-green text-xs font-medium px-3 py-1.5 rounded` to full-width elevated style with Phosphor search icon.

**Search Now button app-colored hover** (Jinja2 conditionals for Tailwind JIT):
```jinja2
<i class="ph ph-magnifying-glass {% if app.name == 'radarr' %}group-hover:text-triggarr-radarr{% elif app.name == 'sonarr' %}group-hover:text-triggarr-sonarr{% elif app.name == 'lidarr' %}group-hover:text-triggarr-green{% endif %} transition-colors"></i>
```
Must use explicit full class strings for Tailwind scanning -- dynamic string interpolation like `group-hover:text-triggarr-{{ app.name }}` will NOT work.

**Unreachable card body pattern** (artifact design.html lines 230-234):
```html
<div class="p-4 flex-1 relative z-10 flex flex-col justify-center items-center text-center">
    <i class="ph ph-warning-circle text-[40px] text-triggarr-danger/40 mb-3 block"></i>
    <span class="text-sm text-triggarr-muted block mb-1">API connection failed.</span>
    <span class="text-[10px] text-triggarr-muted/60 block">Check API key or network setup.</span>
</div>
```
Current unreachable cards show the stats grid with `opacity-60`. Artifact replaces the body entirely with a centered error message. This is a structural change for unreachable cards.

**Unreachable card retry button pattern** (artifact design.html lines 236-238):
```html
<button class="w-full flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-card hover:bg-triggarr-elevated border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-muted">
    <i class="ph ph-arrows-clockwise"></i>Retry Connection
</button>
```
Current (line 95-101): Uses SVG icon with `bg-red-500/15 text-red-400` styling. Change to Phosphor icon and neutral card-colored button matching artifact.

---

### `triggarr/static/css/input.css` (config)

**Analog:** Self (current version)

**Changes needed:**
1. Add `--color-triggarr-primary: #22c55e;` to @theme (artifact references `triggarr-primary` extensively)
2. Add `--color-triggarr-elevated: #233346;` to @theme (artifact uses `bg-triggarr-elevated`; currently exists as `--color-triggarr-card-elevated` which maps to a different Tailwind class name)
3. Update `.mini-bar` CSS if keeping the class, or leave it for backward compat and use Tailwind utilities in templates instead

**Current @theme block** (lines 4-18):
```css
@theme {
  --color-triggarr-green: #22c55e;
  --color-triggarr-green-dark: #16a34a;
  --color-triggarr-bg: #0f172a;
  --color-triggarr-card: #1e293b;
  --color-triggarr-card-elevated: #233346;
  --color-triggarr-border: #334155;
  --color-triggarr-text: #e2e8f0;
  --color-triggarr-muted: #94a3b8;
  --color-triggarr-radarr: #f59e0b;
  --color-triggarr-sonarr: #3b82f6;
  --color-triggarr-danger: #ef4444;
  --color-triggarr-primaryDark: #16a34a;
  --font-geist-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

---

### `tests/test_stats_health.py` (test)

**Analog:** Self (current version)

**Test fixture pattern** (lines 28-123) -- reuse exact same `test_app` fixture structure for any new tests.

**Class assertion pattern** (line 171):
```python
def test_grab_rate_hero_card_layout(client):
    """Grab Rate card spans 2 columns with text-4xl headline and gradient."""
    response = client.get("/")
    assert response.status_code == 200
    assert "md:col-span-2" in response.text
    assert "text-4xl font-bold" in response.text
```
Tests that need updating:
- `test_grab_rate_hero_card_layout` (line 166): `"text-4xl font-bold"` -> `"text-[32px] font-bold"`, add `"tracking-widest"` assertion, add Phosphor icon assertion
- `test_per_app_bars_with_colors` (line 196): `"mini-bar"` assertion may need updating if switching to Tailwind utilities; add `"h-1"` or `"rounded-full"` assertions
- `test_stat_cards_have_shadow` (line 211): shadow-sm count may change if card count changes

New tests needed (follow same pattern as existing):
- `test_stat_cards_have_phosphor_icons`: assert `"ph ph-chart-line-up"`, `"ph ph-film-strip"`, `"ph ph-television"`, `"ph ph-clock-countdown"` in response
- `test_stat_card_subtitles`: assert colored dot + label pattern (`"w-1.5 h-1.5 rounded-full"`)

---

### `tests/test_app_cards.py` (test)

**Analog:** Self (current version)

**Tests that need updating:**
- `test_connected_pill_unified_shape` (line 127): `"rounded-full bg-triggarr-green/15 text-triggarr-green"` -> new pill classes with `rounded` (not `rounded-full`), `bg-triggarr-primary/10`, `tracking-wider`, `font-bold`
- `test_unreachable_pill_unified_shape` (line 137): `"rounded-full bg-red-500/15 text-red-400"` -> `"rounded"` + `bg-triggarr-danger/10 text-triggarr-danger`
- `test_waiting_pill_unified_shape` (line 149): update pill classes
- `test_schedule_row_present` (line 161): `"border-b border-triggarr-border/50 pb-3"` -> schedule row loses border-b (moves to header)
- `test_connected_card_search_now_button` (line 271): update button class assertions

New tests needed:
- `test_app_card_border_color`: assert `"border-l-triggarr-radarr"` for radarr, `"border-l-triggarr-sonarr"` for sonarr
- `test_card_header_border_bottom`: assert `"p-4 border-b border-triggarr-border/50"` in header
- `test_recessed_subcards`: assert `"bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5"` in response
- `test_search_button_app_colored_hover`: assert `"group-hover:text-triggarr-radarr"` for radarr cards

---

## Shared Patterns

### Phosphor Icon Integration
**Source:** design.html artifact (lines 122, 141, 153, 165, 196, 231, 237)
**Apply to:** `stats_row.html`, `app_card.html`
```html
<i class="ph ph-{icon-name} text-lg text-{color-token}"></i>
```
Use `<i>` tags with `ph ph-*` classes. Icons are vendored at `static/vendor/phosphor/`.

### App-Type Color Conditional (Jinja2)
**Source:** New pattern derived from artifact design
**Apply to:** `app_card.html` (border, button hover, pill colors)
```jinja2
{% if app.name == 'radarr' %}triggarr-radarr{% elif app.name == 'sonarr' %}triggarr-sonarr{% elif app.name == 'lidarr' %}triggarr-green{% endif %}
```
Always write full Tailwind class strings in the template for JIT scanning. Never concatenate token names dynamically.

### Card Label Typography
**Source:** design.html artifact (consistent across all cards)
**Apply to:** All stat card labels, all app card sub-card labels
```html
<!-- Stat card label -->
<span class="text-xs font-bold tracking-widest uppercase text-triggarr-muted">Label</span>

<!-- Sub-card label -->
<span class="block text-[10px] text-triggarr-muted uppercase tracking-wider">Label</span>
```

### Recessed Container
**Source:** design.html lines 184-191
**Apply to:** `app_card.html` Missing/Cutoff stat sub-cards
```html
<div class="bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5">
```

### Test Fixture
**Source:** `tests/test_stats_health.py` lines 28-123, `tests/test_app_cards.py` lines 27-112
**Apply to:** All new test functions in both files
Both files use identical fixture patterns with `test_app(tmp_path)` async fixture + `client(test_app)` sync fixture. New tests should follow the same `def test_*(client, test_app)` or `def test_*(client)` signature pattern.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files are modifications of existing code with clear analogs |

## Metadata

**Analog search scope:** `triggarr/templates/partials/`, `triggarr/static/css/`, `tests/`, `.aidesigner/runs/`
**Files scanned:** 7 (stats_row.html, app_card.html, dashboard.html, input.css, design.html, test_stats_health.py, test_app_cards.py)
**Pattern extraction date:** 2026-04-15
