# Phase 60: Foundation & Header - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 5
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/templates/base.html` | template | request-response | itself (current version) | exact |
| `triggarr/static/css/input.css` | config | n/a | itself (current version) | exact |
| `triggarr/static/vendor/phosphor/style.css` | static-asset | n/a | `triggarr/static/fonts/GeistMono-Regular.woff2` (vendoring pattern) | role-match |
| `triggarr/static/vendor/phosphor/Phosphor.woff2` | static-asset | n/a | `triggarr/static/fonts/GeistMono-Regular.woff2` (vendoring pattern) | role-match |
| `tests/test_header_redesign.py` | test | request-response | `tests/test_ui_foundations.py` | exact |

## Pattern Assignments

### `triggarr/templates/base.html` (template, request-response)

**Analog:** itself -- this is a modification of the existing file

**Static asset link pattern** (line 12):
```html
<link rel="stylesheet" href="{{ request.url_for('static', path='css/output.css') }}">
```
New Phosphor CSS link must follow this same pattern:
```html
<link rel="stylesheet" href="{{ request.url_for('static', path='vendor/phosphor/style.css') }}">
```

**Header/nav structure** (lines 16-61) -- current layout to be replaced:
```html
<nav class="sticky top-0 z-30 backdrop-blur-md bg-triggarr-card/80 border-b border-triggarr-border">
  <div class="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-triggarr-green font-bold text-xl tracking-tight">Triggarr</span>
      <button onclick="openChangelog()" type="button"
              class="text-xs text-triggarr-muted hover:text-white transition-colors cursor-pointer"
              title="View changelog">
        {{ triggarr_version }}
      </button>
      {% if update_info and update_info.update_available %}
      ...
      {% endif %}
    </div>
    ...
  </div>
</nav>
```

**Target layout from artifact** (design.html lines 60-93):
```html
<!-- NOTE: Artifact uses triggarr-primary class names. Plans translate to triggarr-green
     (same hex value #22c55e, no alias token added -- see RESEARCH.md Open Questions). -->
<header class="sticky top-0 z-50 w-full border-b border-triggarr-border bg-triggarr-bg/95 backdrop-blur-md">
  <div class="px-6 py-4 flex items-center justify-between">
    <!-- Left zone: fixed width -->
    <div class="flex items-center gap-3 w-64 shrink-0">
      <span class="text-triggarr-green font-bold text-xl tracking-tight">Triggarr</span>
      <button ...>v{{ triggarr_version }}</button>
    </div>
    <!-- Center: absolute-positioned nav -->
    <nav class="hidden md:flex items-center gap-6 absolute left-1/2 -translate-x-1/2">
      <!-- nav links with Phosphor icons -->
    </nav>
    <!-- Right zone: connection pill -->
    <div class="flex items-center justify-end w-64 shrink-0">
      <!-- connection status pill -->
    </div>
  </div>
</header>
```

**Nav link active state pattern** (lines 39-50) -- current:
```html
{% set current_path = request.url.path %}
{% set dashboard_url = request.url_for('dashboard') %}
<a href="{{ dashboard_url }}"
   class="{% if current_path == dashboard_url.path %}text-white border-b-2 border-triggarr-green pb-1 -mb-[7px]{% else %}text-triggarr-muted hover:text-white{% endif %}">
  Dashboard
</a>
```

**Auth-conditional logout pattern** (lines 51-59) -- MUST remain a POST form:
```html
{% if auth_state.active %}
<span class="text-triggarr-border">|</span>
<form method="post" action="{{ request.url_for('logout') }}" class="inline">
  <button type="submit"
          class="text-triggarr-muted hover:text-white text-sm transition-colors cursor-pointer">
    Logout
  </button>
</form>
{% endif %}
```

**Update badge pattern** (lines 25-32) -- preserve but restyle:
```html
{% if update_info and update_info.update_available %}
<a href="{{ update_info.html_url if update_info.html_url.startswith('https://github.com/') else '#' }}" target="_blank" rel="noopener"
   class="inline-flex items-center gap-1.5 text-xs bg-triggarr-green/15 text-triggarr-green px-2 py-0.5 rounded-full hover:bg-triggarr-green/25 transition-colors"
   title="Update available — click to view release">
  <span class="w-1.5 h-1.5 rounded-full bg-triggarr-green dot-pulse"></span>
  v{{ update_info.latest_version }} available
</a>
{% endif %}
```

---

### `triggarr/static/css/input.css` (config, theme tokens)

**Analog:** itself -- adding new color tokens to existing `@theme` block

**Theme token pattern** (lines 4-14):
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
  --font-geist-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

**New tokens to add** (from artifact tailwind.config and RESEARCH.md):
```css
  --color-triggarr-primaryDark: #16a34a;
  --color-triggarr-danger: #ef4444;
  --color-triggarr-radarr: #f59e0b;
  --color-triggarr-sonarr: #3b82f6;
```
NOTE: No `--color-triggarr-primary` token. The artifact's `triggarr-primary` (#22c55e) is identical to the existing `triggarr-green`. Plans use `triggarr-green` directly -- see RESEARCH.md Open Questions (RESOLVED) Q2.

**Existing dot-pulse animation** (lines 48-61) -- reuse for connection pill, no changes needed:
```css
.dot-pulse { position: relative; }
.dot-pulse::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
  animation: dot-ring-pulse 2s infinite;
}
```

---

### `triggarr/static/vendor/phosphor/` (static assets)

**Analog:** `triggarr/static/fonts/` directory (self-hosted font vendoring pattern)

**Vendoring pattern:** Font files placed in a subdirectory under `static/`, referenced by relative URL from their companion CSS file. The Geist Mono fonts demonstrate this:
- `input.css` line 22: `src: url("../fonts/GeistMono-Regular.woff2") format("woff2");`
- For Phosphor: `style.css` internally references `url("./Phosphor.woff2")` -- both files must be in the same directory.

**Loading pattern:** Add a `<link>` tag in `base.html` `<head>`, after the output.css link (line 12), before the htmx script (line 13):
```html
<link rel="stylesheet" href="{{ request.url_for('static', path='vendor/phosphor/style.css') }}">
```

**Icon markup pattern** (from artifact design.html lines 67-83):
```html
<!-- NOTE: Artifact uses text-triggarr-primary; plans translate to text-triggarr-green -->
<i class="ph ph-squares-four text-[18px] text-triggarr-green relative top-px"></i>
<i class="ph ph-clock-counter-clockwise text-[18px] group-hover:text-triggarr-text transition-colors relative top-px"></i>
<i class="ph ph-gear text-[18px] group-hover:text-triggarr-text transition-colors relative top-px"></i>
<i class="ph ph-sign-out text-[18px] group-hover:text-red-400 transition-colors relative top-px"></i>
```

---

### `tests/test_header_redesign.py` (test, request-response)

**Analog:** `tests/test_ui_foundations.py` -- exact match for UI template assertion tests

**Test fixture pattern** (test_ui_foundations.py lines 29-111):
```python
@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for route testing."""
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        await insert_search_entry(db, "Radarr", "missing", "Test Movie")
        app.state.db = db

        app.state.triggarr_state = { ... }
        app.state.settings = make_settings(...)
        # ... mock scheduler, clients, etc.
        yield app

@pytest.fixture
def client(test_app):
    return TestClient(test_app)
```

**Template assertion test pattern** (test_ui_foundations.py lines 125-130):
```python
def test_dashboard_has_widened_container(client):
    """Dashboard uses max-w-7xl and no longer has max-w-5xl."""
    response = client.get("/")
    assert response.status_code == 200
    assert "max-w-7xl" in response.text
    assert "max-w-5xl" not in response.text
```

**CSS file assertion pattern** (test_ui_foundations.py lines 252-260):
```python
def test_output_css_contains_elevation_token_and_dot_pulse():
    """Compiled output.css must contain the elevation hex, dot-pulse, and Geist Mono."""
    css_path = STATIC_DIR / "css" / "output.css"
    css_content = css_path.read_text()
    assert "#233346" in css_content, "Elevation token #233346 missing from output.css"
```

**Static file existence assertion pattern** (for Phosphor vendored files):
```python
def test_phosphor_font_files_vendored():
    """Phosphor CSS and WOFF2 files exist in vendor directory."""
    assert (STATIC_DIR / "vendor" / "phosphor" / "style.css").exists()
    assert (STATIC_DIR / "vendor" / "phosphor" / "Phosphor.woff2").exists()
```

**Imports pattern** (test_ui_foundations.py lines 1-24):
```python
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import log_buffer
from triggarr.models.config import GeneralConfig
from triggarr.web.routes import STATIC_DIR, router
```

---

## Shared Patterns

### Static Asset URL Resolution
**Source:** `triggarr/templates/base.html` line 12
**Apply to:** All new `<link>` or `<script>` tags in base.html
```html
{{ request.url_for('static', path='...') }}
```

### Jinja2 Globals for Template Data
**Source:** `triggarr/web/routes.py` lines 64-74
**Apply to:** Connection pill data availability in base.html
```python
templates.env.globals["triggarr_version"] = get_display_version()
update_info: dict = {}
templates.env.globals["update_info"] = update_info
auth_state: dict = {"active": False}
templates.env.globals["auth_state"] = auth_state
```
This is the established pattern for making data available to all templates via `base.html`. The connection pill needs health data exposed through a similar mechanism, or via htmx partial loading from the existing `/partials/health-summary` endpoint.

### Htmx Partial Loading Pattern
**Source:** `triggarr/templates/partials/health_summary.html` lines 1-4
**Apply to:** Connection status pill (if using htmx approach per RESEARCH.md Option B)
```html
<div id="health-summary"
     hx-get="{{ request.url_for('partial_health_summary') }}"
     hx-trigger="every 30s"
     hx-swap="outerHTML">
```

### Health Data Computation
**Source:** `triggarr/web/routes.py` lines 283-314
**Apply to:** Connection pill logic
```python
def _build_health_summary(request: Request) -> dict:
    settings = request.app.state.settings
    state = request.app.state.triggarr_state
    connected = 0
    disconnected = 0
    pending = 0
    for app_name in APP_TYPES:
        for inst_name in settings.get_enabled_instances(app_name):
            ist = state.get(app_name, {}).get(inst_name, {})
            conn = ist.get("connected")
            if conn is True:
                connected += 1
            elif conn is False:
                disconnected += 1
            else:
                pending += 1
    return {"connected": connected, "disconnected": disconnected, "pending": pending, "total": connected + disconnected + pending}
```
The pill renders "Connection Stable" when `disconnected == 0` and `total > 0`, or "Connection Issue" when `disconnected > 0`.

### POST-Only Logout (Security)
**Source:** `triggarr/templates/base.html` lines 53-58
**Apply to:** Restyled logout in center nav
```html
<form method="post" action="{{ request.url_for('logout') }}" class="inline">
  <button type="submit" class="...">Logout</button>
</form>
```
The artifact uses `<a>` tags for logout, but this MUST remain a `<form method="post">` with `<button type="submit">`. Style the button to look like a link with Tailwind utility classes.

### Test Fixture Reuse
**Source:** `tests/conftest.py` lines 29-76
**Apply to:** `tests/test_header_redesign.py`
```python
from tests.conftest import make_settings
# Use make_settings() for all test Settings instances
app.state.settings = make_settings(
    radarr_url="http://radarr:7878",
    radarr_api_key="test-radarr-key",
    radarr_enabled=True,
    sonarr_url="http://sonarr:8989",
    sonarr_api_key="test-sonarr-key",
    sonarr_enabled=True,
    general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
)
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have analogs in the existing codebase |

## Metadata

**Analog search scope:** `triggarr/templates/`, `triggarr/static/`, `triggarr/web/`, `tests/`
**Files scanned:** 30+
**Pattern extraction date:** 2026-04-15
