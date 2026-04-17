# Phase 62: Activity Rail & Log Viewer - Pattern Map

**Mapped:** 2026-04-17
**Files analyzed:** 5 modified files
**Analogs found:** 5 / 5 (all files are modifications of existing code)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/templates/partials/activity_rail.html` | component | request-response | Self (current version) + Phase 61 `stats_row.html` card pattern | exact |
| `triggarr/templates/partials/log_viewer.html` | component | request-response | Self (current version) + Phase 61 Phosphor icon pattern | exact |
| `triggarr/static/css/input.css` | config | N/A | Self (current version) | exact |
| `tests/test_activity_rail.py` | test | N/A | Self (current version) | exact |
| `tests/test_log_viewer.py` | test | N/A | Self (current version) | exact |

## Pattern Assignments

### `triggarr/templates/partials/activity_rail.html` (component, request-response)

**Analog:** Current `activity_rail.html` (110 lines)

**htmx wiring pattern -- PRESERVE AS-IS** (lines 1-5):
```html
<aside id="activity-rail"
       hx-get="{{ request.url_for('partial_activity_rail') }}"
       hx-trigger="every 5s"
       hx-swap="outerHTML"
       class="...">
```
Do NOT change `id`, `hx-get`, `hx-trigger`, or `hx-swap`. Only modify the `class` attribute and inner HTML structure.

**Current aside class** (line 5):
```html
class="hidden xl:flex w-80 shrink-0 flex-col bg-triggarr-card rounded-lg border border-triggarr-border shadow-sm overflow-hidden sticky top-20 max-h-[calc(100vh-6rem)]"
```
Per D-09, the header gets sticky with `bg-triggarr-bg/95 backdrop-blur-md`. Per CONTEXT.md specifics, the aside uses `border-l` separator instead of rounded card. Adjust `top-20` to `top-[73px]` per UI-SPEC if applicable.

**Current header pattern** (lines 8-21):
```html
<div class="px-4 py-3 border-b border-triggarr-border flex items-center justify-between">
  <div class="flex items-center gap-2">
    <h3 class="text-sm font-semibold text-white">Recent Activity</h3>
    <div class="flex items-center gap-1">
      <span class="w-1.5 h-1.5 rounded-full bg-triggarr-green dot-pulse"></span>
      <span class="text-[10px] font-geist-mono uppercase tracking-wider text-triggarr-green">LIVE</span>
    </div>
  </div>
```
Changes needed per D-08/D-09: Title styling to `text-[13px] font-bold uppercase tracking-widest text-triggarr-muted`. LIVE badge color stays green (D-08 override). Header padding to `px-6 py-5`. Remove filter button SVG.

**Current timeline entry pattern** (lines 30-99):
```html
<div class="timeline-item">
  <span class="timeline-dot bg-triggarr-green shadow-[0_0_6px_rgba(34,197,94,0.6)]"></span>
  <!-- app badge row -->
  <!-- title -->
  <!-- outcome pill with inline SVG -->
</div>
```
Replace entirely with card-based layout per D-01 through D-06. The `timeline-item` and `timeline-dot` CSS classes (input.css lines 152-173) will be replaced by inline Tailwind utilities.

**Current outcome pill pattern with SVGs** (lines 71-96):
```html
<span class="inline-flex items-center gap-1 text-green-400 bg-green-500/10 border border-green-500/20 px-1.5 py-0.5 rounded-sm text-xs">
  <svg class="w-3 h-3" viewBox="0 0 24 24" ...><polyline points="20 6 9 17 4 12"/></svg>
  grabbed
</span>
```
Replace with text-only pills per CONTEXT.md specifics: remove inline SVGs, use `text-[10px] font-bold uppercase` pills with outcome-colored backgrounds matching D-02 colors.

**Current app badge pattern** (lines 46-62):
```html
<span class="text-[10px] font-geist-mono font-semibold uppercase text-orange-400 bg-orange-500/10 px-1.5 rounded">
  {{ entry.app }}{% if entry.instance_id and entry.instance_id != 'Default' %} &middot; {{ entry.instance_id }}{% endif %}
</span>
```
Replace with D-06 pattern: `w-1.5 h-1.5 rounded-full` colored dot + `text-[10px] font-mono text-triggarr-muted uppercase tracking-wider font-bold` label. Note: use `font-geist-mono` (not `font-mono`) to match existing template convention -- see Open Question in RESEARCH.md.

**Current footer pattern** (lines 105-109):
```html
<div class="px-4 py-3 border-t border-triggarr-border">
  <a href="{{ request.url_for('history_page') }}" class="text-xs text-triggarr-muted hover:text-triggarr-green transition-colors font-geist-mono">
    View full history &rarr;
  </a>
</div>
```
Update per D-10: add `ph-arrow-right` Phosphor icon with `group-hover:translate-x-1 transition-transform`. Replace `&rarr;` text with icon element.

**Jinja2 loop index pattern for opacity** (new -- D-07):
```jinja2
{% for entry in entries %}
<div class="flex gap-4 items-start{% if loop.index == 3 %} opacity-75{% elif loop.index > 3 %} opacity-60{% endif %}">
```
This is a new pattern. Use `loop.index` (1-based) in Jinja2 for position-based fading.

---

### `triggarr/templates/partials/log_viewer.html` (component, request-response)

**Analog:** Current `log_viewer.html` (81 lines)

**htmx wiring pattern -- PRESERVE AS-IS** (lines 1-5):
```html
<div id="log-viewer"
     hx-get="{{ request.url_for('partial_log_viewer') }}{% if selected_level %}?level={{ selected_level }}{% endif %}"
     hx-trigger="every 5s"
     hx-swap="outerHTML"
     class="...">
```
Do NOT change `id`, `hx-get`, `hx-trigger`, or `hx-swap`. Only modify `class` and inner HTML.

**Current outer class** (line 5):
```html
class="terminal-pane rounded-lg border border-triggarr-border p-5 shadow-sm"
```
Replace `terminal-pane` with `bg-[#0b1120]` per D-16. Keep `rounded-lg border border-triggarr-border shadow-sm`. Restructure to have `bg-triggarr-card` header bar.

**Current header pattern** (lines 8-42):
```html
<div class="flex items-center justify-between mb-4">
  <div class="flex items-center gap-3">
    <h2 class="text-lg font-semibold">Application Log</h2>
    <span class="text-[10px] font-geist-mono text-triggarr-green bg-triggarr-green/10 px-1.5 rounded flex items-center gap-1">
      <span class="w-1.5 h-1.5 bg-triggarr-green rounded-full dot-pulse"></span>
      TAILING
    </span>
  </div>
```
Changes per D-11 through D-15:
- Title: "Application Log" -> "System Logs" with `ph-terminal-window` icon
- TAILING badge: wrap in `px-2 py-0.5 rounded bg-triggarr-bg border border-triggarr-border` container (D-13)
- Level filter: "All" -> "Level: ALL", "ERROR" -> "Level: ERROR", etc. Add `font-mono` styling (D-14)
- Divider: add `w-px h-4 bg-triggarr-border` between filter and buttons (D-15)

**Current pause button with inline SVG** (lines 27-32):
```html
<button type="button" title="Pause stream" data-pause-btn onclick="toggleLogPause(this)"
        class="p-1.5 text-triggarr-muted hover:text-white hover:bg-triggarr-border/40 rounded transition-colors">
  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
  </svg>
</button>
```
Replace SVG with `<i class="ph ph-pause text-[15px]"></i>` per D-12. MUST preserve `onclick="toggleLogPause(this)"` and `data-pause-btn`.

**Current expand button with inline SVG** (lines 34-40):
```html
<button type="button" title="Expand log to terminal" onclick="toggleLogExpand()"
        class="p-1.5 text-triggarr-muted hover:text-white hover:bg-triggarr-border/40 rounded transition-colors">
  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="15 3 21 3 21 9"/>...
  </svg>
</button>
```
Replace SVG with `<i class="ph ph-corners-out text-[15px]"></i>` per D-12. MUST preserve `onclick="toggleLogExpand()"`.

**Current scanline overlay** (line 46):
```html
<div class="scanline-overlay" aria-hidden="true"></div>
```
Remove per Claude's Discretion / RESEARCH.md recommendation. The new design aesthetic does not include CRT scanline effects.

**Current log row pattern** (lines 65-76):
```html
<div class="flex items-start gap-2 py-1 border-b border-triggarr-border/30{% if entry.level == 'ERROR' %} bg-red-500/5 border-l-2 border-l-red-500 pl-2 -ml-[2px]{% endif %}{% if entry.level == 'DEBUG' %} opacity-60{% endif %}">
  <span class="text-triggarr-muted whitespace-nowrap">{{ timestamp }}</span>
  <span class="font-medium whitespace-nowrap w-14 shrink-0 {% if entry.level == 'ERROR' %}text-red-400{% elif ... %}">{{ entry.level }}</span>
  <span class="{{ source_color }} whitespace-nowrap w-20 shrink-0">{% if source %}[{{ source }}]{% endif %}</span>
  <span class="text-triggarr-text break-all">{{ entry.message }}</span>
</div>
```
Add GRAB row detection per D-17: keyword check (`"grab" in msg_lower or "found release" in msg_lower or "sent to client" in msg_lower`) before existing level-based styling. GRAB rows get `bg-triggarr-primary/10 border-l-2 border-triggarr-primary` with `[GRAB]` level label. Non-grab rows get `hover:bg-white/5` with `text-[13px] leading-relaxed` per D-18.

**Current level filter select** (lines 18-25):
```html
<select onchange="var url='{{ request.url_for('partial_log_viewer') }}' + (this.value ? '?level=' + this.value : ''); var v=this.closest('#log-viewer'); v.setAttribute('hx-get', url); htmx.ajax('GET', url, {target:'#log-viewer', swap:'outerHTML'});"
        class="bg-transparent border border-triggarr-border/40 text-triggarr-muted text-xs rounded px-1.5 py-1 font-geist-mono focus:outline-none focus:border-triggarr-green">
  <option value=""{% if not selected_level %} selected{% endif %}>All</option>
  <option value="ERROR"{% if selected_level == 'ERROR' %} selected{% endif %}>ERROR</option>
  <option value="WARNING"{% if selected_level == 'WARNING' %} selected{% endif %}>WARNING</option>
  <option value="INFO"{% if selected_level == 'INFO' %} selected{% endif %}>INFO</option>
  <option value="DEBUG"{% if selected_level == 'DEBUG' %} selected{% endif %}>DEBUG</option>
</select>
```
Per D-14: change display text to "Level: ALL", "Level: ERROR", "Level: WARN", etc. Keep `value` attributes unchanged (backend expects "ERROR", "WARNING", "INFO", "DEBUG"). Note: display says "WARN" but value stays "WARNING". Update class to `font-mono bg-triggarr-bg border border-triggarr-border text-[11px]`. MUST preserve the `onchange` handler exactly.

---

### `triggarr/static/css/input.css` (config)

**Analog:** Self (current version, 174 lines)

**CSS to remove/replace** (lines 93-123):
```css
/* Scanline animation for terminal pane -- LOG-05 D-07 */
@keyframes scanline { ... }

/* Terminal pane background -- LOG-05 D-07 */
.terminal-pane { ... }

/* Scanline overlay -- LOG-05 D-07 */
.scanline-overlay { ... }
```
Remove scanline and terminal-pane CSS. The `bg-[#0b1120]` inline Tailwind class replaces `.terminal-pane`. Keep `#log-viewer.expanded` rules (lines 126-150) -- they target by ID not class.

**CSS to remove/replace** (lines 152-173):
```css
/* Activity timeline rail -- RAIL-02 */
.timeline-item { position: relative; padding-left: 1.25rem; }
.timeline-item::before { ... }
.timeline-item:last-child::before { ... }
.timeline-dot { ... }
```
Remove `.timeline-item` and `.timeline-dot` CSS classes. The new card-based layout uses pure Tailwind utilities (`flex gap-4 items-start`, `w-7 h-7 rounded-full`, etc.).

**Optional addition to @theme block** (line 19):
```css
--font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
```
If planner decides to use `font-mono` class per UI-SPEC instead of `font-geist-mono`. Currently `font-geist-mono` is the project convention. Either approach works -- be consistent.

---

### `tests/test_activity_rail.py` (test)

**Analog:** Self (current version, 211 lines)

**Test fixture pattern** (lines 21-71):
```python
@pytest.fixture
async def rail_app(tmp_path):
    """Build a minimal FastAPI app with seeded search data for rail tests."""
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)
    db_path = tmp_path / "test_rail.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        await insert_search_entry(db, "Radarr", "missing", "Test Movie", outcome="grabbed")
        await insert_search_entry(db, "Sonarr", "cutoff", "Test Show", outcome="failed", detail="Connection refused")
        app.state.db = db
        # ... state setup ...
        yield app
```
Reuse this fixture for all new tests. For opacity fading tests (D-07), need to seed 4+ entries.

**Tests to update:**

`test_rail_has_sticky_classes` (line 126):
```python
assert "top-20" in response.text  # may change to top-[73px] per UI-SPEC
```

`test_timeline_dots_present` (line 141):
```python
# CURRENT:
assert "timeline-item" in response.text
assert "timeline-dot" in response.text
# REPLACE WITH:
assert "w-7 h-7 rounded-full" in response.text  # double-circle outer
assert "w-2.5 h-2.5 rounded-full" in response.text  # double-circle inner
```

`test_entry_has_app_badge` (line 149):
```python
# CURRENT:
assert "bg-orange-500/10" in response.text
# REPLACE WITH:
assert "w-1.5 h-1.5 rounded-full" in response.text  # app badge dot
```

`test_outcome_svg_icons` (line 198):
```python
# CURRENT:
assert "<polyline" in response.text
assert "<circle" in response.text
# REMOVE or replace with text-only pill assertions
```

**New tests to add** (follow existing pattern):
```python
def test_card_based_layout(client):
    response = client.get("/partials/activity-rail")
    assert "bg-triggarr-card" in response.text
    assert "rounded-lg p-3" in response.text

def test_opacity_fading(client_with_4_entries):
    response = client_with_4_entries.get("/partials/activity-rail")
    assert "opacity-75" in response.text
    assert "opacity-60" in response.text
```
Note: opacity fading test needs a fixture with 4+ seeded entries.

---

### `tests/test_log_viewer.py` (test)

**Analog:** Self (current version, 229 lines)

**Test fixture pattern** (lines 26-108):
```python
@pytest.fixture
async def test_app(tmp_path):
    log_buffer.clear()
    app = FastAPI()
    # ... full app setup ...
    yield app

@pytest.fixture
def client(test_app):
    return TestClient(test_app)
```
Reuse for all new tests.

**Tests to update:**

`test_log_viewer_expand_button` (line 184):
```python
# CURRENT:
assert "scanline-overlay" in response.text
assert "terminal-pane" in response.text
# REPLACE WITH:
assert "ph ph-corners-out" in response.text
assert "bg-[#0b1120]" in response.text or check outer class
```

`test_log_viewer_tailing_indicator` (line 129):
```python
# CURRENT assertions still valid, ADD:
assert "bg-triggarr-bg border border-triggarr-border" in response.text  # D-13 border container
```

`test_log_viewer_pause_button` (line 193):
```python
# CURRENT onclick/data-pause-btn assertions still valid, ADD:
assert "ph ph-pause" in response.text
```

**New tests to add:**
```python
def test_system_logs_title(client):
    response = client.get("/partials/log-viewer")
    assert "System Logs" in response.text
    assert "Application Log" not in response.text

def test_terminal_icon(client):
    response = client.get("/partials/log-viewer")
    assert "ph ph-terminal-window" in response.text

def test_grab_row_highlight(client):
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: grabbed 12 items"))
    response = client.get("/partials/log-viewer")
    assert "bg-triggarr-primary/10" in response.text
    assert "[GRAB]" in response.text

def test_level_filter_format(client):
    response = client.get("/partials/log-viewer")
    assert "Level: INFO" in response.text
    assert "Level: WARN" in response.text

def test_vertical_divider(client):
    response = client.get("/partials/log-viewer")
    assert "w-px h-4 bg-triggarr-border" in response.text
```

---

## Shared Patterns

### htmx Wiring Preservation
**Source:** Phase 61 PATTERNS.md (established rule)
**Apply to:** `activity_rail.html`, `log_viewer.html`
Never modify `id`, `hx-get`, `hx-trigger`, or `hx-swap` attributes on root elements. Only change `class` and inner HTML.

### Phosphor Icon Integration
**Source:** Phase 60/61 convention, vendored at `static/vendor/phosphor/`
**Apply to:** `log_viewer.html` (pause, expand, terminal title icons), `activity_rail.html` (footer arrow)
```html
<i class="ph ph-{icon-name} text-[15px]"></i>
```

### Outcome-Based Jinja2 Conditionals (No Dynamic Class Construction)
**Source:** Current `activity_rail.html` lines 32-42, Phase 61 PATTERNS.md anti-pattern rule
**Apply to:** `activity_rail.html` (dot colors, card solid/dashed, pill colors)
```jinja2
{# CORRECT: full class strings in each branch #}
{% if entry.outcome == 'grabbed' %}
<div class="w-2.5 h-2.5 rounded-full bg-triggarr-primary"></div>
{% elif entry.outcome == 'partial' %}
<div class="w-2.5 h-2.5 rounded-full bg-amber-400"></div>
{% endif %}

{# WRONG: dynamic interpolation breaks Tailwind JIT #}
<div class="w-2.5 h-2.5 rounded-full bg-{{ outcome_color }}"></div>
```

### App-Type Color Conditionals
**Source:** Current `activity_rail.html` lines 46-62
**Apply to:** `activity_rail.html` (app badge dots)
```jinja2
{% if entry.app == 'Radarr' %}
<span class="w-1.5 h-1.5 rounded-full bg-triggarr-radarr"></span>
{% elif entry.app == 'Sonarr' %}
<span class="w-1.5 h-1.5 rounded-full bg-triggarr-sonarr"></span>
{% elif entry.app == 'Lidarr' %}
<span class="w-1.5 h-1.5 rounded-full bg-triggarr-green"></span>
{% endif %}
```

### Test Assertion Pattern
**Source:** `tests/test_activity_rail.py` lines 118-122, `tests/test_log_viewer.py` lines 117-126
**Apply to:** All new and updated tests
```python
def test_feature_name(client):
    """Requirement ID: Brief description."""
    response = client.get("/partials/activity-rail")  # or /partials/log-viewer
    assert response.status_code == 200
    assert "expected-class" in response.text, "Descriptive failure message"
```

### Monospace Font Class
**Source:** `triggarr/static/css/input.css` line 19, existing templates
**Apply to:** All badge text, timestamps, log body, filter dropdown
Use `font-geist-mono` to match existing template convention. The `font-mono` class requires adding `--font-mono` to @theme. Pick one approach and be consistent across both templates.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files are modifications of existing code with clear analogs |

## Metadata

**Analog search scope:** `triggarr/templates/partials/`, `triggarr/static/css/`, `tests/`, `.planning/phases/61-stat-cards-app-cards/`
**Files scanned:** 7 (activity_rail.html, log_viewer.html, input.css, test_activity_rail.py, test_log_viewer.py, 61-PATTERNS.md, 62-RESEARCH.md)
**Pattern extraction date:** 2026-04-17
