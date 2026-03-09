# Phase 3: Web UI - Research

**Researched:** 2026-02-23
**Domain:** FastAPI server-rendered UI with Jinja2 templates, htmx polling, Tailwind CSS styling
**Confidence:** HIGH

## Summary

Phase 3 adds a status dashboard and config editor to the existing FastAPI application. The stack is FastAPI + Jinja2 + htmx + Tailwind CSS (via pytailwindcss), all running inside the same single-process architecture established in Phases 1-2. The dashboard polls the server every 5 seconds via htmx `hx-trigger="every 5s"` to display live status without page reloads. The config editor reads the TOML file, masks API keys in the form, and writes changes back via `tomli_w`. Settings hot-reload by re-instantiating pydantic-settings and rescheduling APScheduler jobs.

The existing codebase already has FastAPI, uvicorn, APScheduler, and the state/config infrastructure. The main integration work is: (1) exposing state, settings, and scheduler to route handlers via `app.state`, (2) adding Jinja2 template rendering with htmx partial responses, (3) implementing config save with TOML serialization, and (4) wiring the "search now" button to trigger immediate scheduler jobs.

**Primary recommendation:** Use `app.state` to share the mutable `FetcharrState` dict, `Settings` object, and `AsyncIOScheduler` instance from the lifespan context to route handlers. Return HTML fragments (partials) for htmx polling requests, full pages for initial loads.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Side-by-side app cards: Radarr card on left, Sonarr card on right
- Each card shows: connection status, last run, next run, queue position, wanted/cutoff counts, enable/disable toggle, "Search Now" button
- Shared chronological search log below the cards, with app label per entry
- Separate settings page at /settings (dashboard is read-only status)
- Minimal top bar navigation: "Fetcharr" brand + Dashboard / Settings links
- Dark mode only -- fits the *arr ecosystem
- Visual reference: Radarr/Sonarr style (dark backgrounds, colored accent bars, functional and dense)
- Green accent color for active states, buttons, highlights -- distinct from Radarr (orange) and Sonarr (blue)
- Tailwind CSS via pytailwindcss (Phase 4 Dockerfile already references pytailwindcss builder stage)
- Per-app sections in config editor: Radarr section with all its fields, Sonarr section with all its fields
- Each config section has enable/disable toggle at the top
- Explicit save button -- changes don't apply until user clicks "Save"
- Hot reload on save -- new settings take effect immediately (scheduler interval updates, connections re-validate, no restart needed)
- API keys masked in form (placeholders shown), only accepted on write
- "Search Now" button lives on the dashboard app cards, not the settings page
- Connection errors shown inline on the app card -- red/orange border or badge with "Unreachable since [time]"
- No transient feedback (no toasts) -- dashboard updates via htmx polling, new log entries and timestamps just appear
- htmx polling interval: every 5 seconds
- Green dot/badge on each card when connected -- positive confirmation at a glance

### Claude's Discretion
- Exact Tailwind color palette values (within green accent + dark theme)
- Typography and spacing details
- Loading/skeleton states during initial page load
- Search log entry formatting and max visible entries
- Form validation error presentation
- "Search Now" button disabled state while search is in progress

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WEBU-01 | Dashboard shows last run time and next scheduled run per app | State has `last_run` per app; APScheduler `get_job()` provides `next_run_time`. Exposed via `app.state` to dashboard route. htmx polls every 5s. |
| WEBU-02 | Dashboard shows recent search history with item names and timestamps | State has `search_log` (bounded list of dicts with `name`, `timestamp`, `app`, `queue_type`). Rendered as a Jinja2 partial. |
| WEBU-03 | Dashboard shows current round-robin queue position per app | State has `missing_cursor` and `cutoff_cursor` per app. Displayed alongside counts from API. |
| WEBU-04 | Dashboard shows wanted and cutoff unmet item counts per app | Requires fetching counts from *arr API. Cache in `app.state` with TTL to avoid hammering API on every poll. |
| WEBU-05 | User can edit all settings via web UI config editor without file editing | GET /settings renders form from current Settings; POST /settings writes TOML via `tomli_w.dumps()` and reloads. |
| WEBU-06 | Dashboard shows connection status with "unreachable since" when *arr is down | Track connection health in `app.state` (dict of `{app: {connected: bool, unreachable_since: str\|None}}`). Updated each search cycle. |
| WEBU-07 | User can enable/disable each app via toggle without changing other config | Toggle is a form field in the config editor. POST saves full config including toggle state. |
| WEBU-08 | User can trigger immediate search cycle per app via "search now" button | POST /api/search-now/{app} triggers scheduler job immediately. Route calls `scheduler.modify_job()` or runs the cycle function directly. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.132.0 | Web framework (already installed) | Already the app framework; routes + templates are a natural extension |
| Jinja2 | >=3.1 | HTML template engine | FastAPI's built-in `Jinja2Templates`; standard for server-rendered Python web apps |
| htmx | 2.0.8 | Declarative AJAX via HTML attributes | No JavaScript build step; polling via `hx-trigger="every 5s"`; fragment swaps |
| Tailwind CSS | v4.x | Utility-first CSS framework | Dark theme via CSS-first config; pytailwindcss standalone CLI for no-Node.js builds |
| pytailwindcss | >=0.3.0 | Tailwind standalone CLI via pip | Already referenced in Phase 4 Dockerfile plan; no Node.js dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tomli_w | 1.2.0 (installed) | Write TOML files from dicts | Config editor POST handler: serialize settings back to TOML |
| aiofiles | >=24.1 | Async static file serving | Required by Starlette's `StaticFiles` mount |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tomli_w | tomlkit | tomlkit preserves comments; tomli_w does not. But config editor writes the full settings dict, so comment preservation is not needed -- the saved file is machine-generated. The default template with comments is only used for first-run generation. |
| htmx polling | Server-Sent Events (SSE) | SSE gives real-time push but adds complexity. 5-second polling with htmx is simpler, adequate for a status dashboard, and matches the user decision. |
| Separate partials files | jinja2-fragments library | jinja2-fragments allows rendering named blocks from a single template. But simple `{% include %}` partials are sufficient here and avoid adding a dependency. |

**Installation:**
```bash
pip install jinja2 aiofiles pytailwindcss
```

Add to `pyproject.toml` dependencies:
```toml
"jinja2",
"aiofiles",
```

Add to dev dependencies:
```toml
"pytailwindcss",
```

## Architecture Patterns

### Recommended Project Structure
```
fetcharr/
├── __main__.py             # Entry point (existing)
├── config.py               # TOML config loading (existing)
├── state.py                # State persistence (existing)
├── models/
│   ├── config.py           # Settings models (existing)
│   └── arr.py              # API response models (existing)
├── clients/                # *arr API clients (existing)
├── search/
│   ├── engine.py           # Search cycle logic (existing)
│   └── scheduler.py        # APScheduler lifespan (MODIFIED)
├── web/
│   ├── __init__.py         # Web module init
│   ├── routes.py           # All route handlers (dashboard + settings + API)
│   └── dependencies.py     # FastAPI Depends helpers for accessing app.state
├── templates/
│   ├── base.html           # Base layout (nav, head, body wrapper)
│   ├── dashboard.html      # Dashboard page (extends base)
│   ├── settings.html       # Settings page (extends base)
│   └── partials/
│       ├── app_card.html       # Single app status card (htmx swap target)
│       ├── search_log.html     # Search history table (htmx swap target)
│       └── settings_form.html  # Config form fields
└── static/
    ├── css/
    │   ├── input.css        # Tailwind input (source)
    │   └── output.css       # Tailwind compiled (generated)
    └── img/                 # (if needed for favicon etc.)
```

### Pattern 1: app.state for Shared Mutable State
**What:** Store mutable references (state dict, settings, scheduler, connection health) on `app.state` during lifespan, access from routes via `request.app.state`.
**When to use:** When lifespan-created resources need to be accessed by route handlers.
**Example:**
```python
# In scheduler.py lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = load_state(state_path)
    scheduler = AsyncIOScheduler()
    # ... setup ...
    app.state.fetcharr_state = state
    app.state.settings = settings
    app.state.scheduler = scheduler
    app.state.connection_health = {"radarr": None, "sonarr": None}
    # ... yield ...

# In routes.py:
@router.get("/")
async def dashboard(request: Request):
    state = request.app.state.fetcharr_state
    settings = request.app.state.settings
    scheduler = request.app.state.scheduler
    # ... render template ...
```
**Source:** [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

### Pattern 2: htmx Polling with Partial Templates
**What:** Use `hx-trigger="every 5s"` on container elements to poll endpoints that return HTML fragments (partials). The fragment replaces just the target element, not the full page.
**When to use:** Dashboard status panels that need live updates without page reload.
**Example:**
```html
<!-- In dashboard.html -->
<div id="radarr-card"
     hx-get="/partials/app-card/radarr"
     hx-trigger="every 5s"
     hx-swap="outerHTML">
  {% include "partials/app_card.html" %}
</div>
```
```python
# In routes.py:
@router.get("/partials/app-card/{app_name}")
async def app_card_partial(request: Request, app_name: str):
    # ... build context for just this card ...
    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={...},
    )
```
**Source:** [htmx hx-trigger docs](https://htmx.org/attributes/hx-trigger/)

### Pattern 3: Config Editor with Masked Secrets
**What:** GET renders the form with API key fields showing placeholder text. POST accepts new values -- empty means "keep existing", non-empty means "replace". Never serialize the actual key value into the HTML response.
**When to use:** Any form that edits config containing `SecretStr` fields.
**Example:**
```python
# GET /settings -- build form context with masked keys
form_data = {
    "radarr": {
        "url": settings.radarr.url,
        "api_key_placeholder": "********" if settings.radarr.api_key.get_secret_value() else "",
        "enabled": settings.radarr.enabled,
        ...
    }
}

# POST /settings -- merge submitted values
submitted_api_key = form.get("radarr_api_key", "").strip()
if submitted_api_key:
    new_config["radarr"]["api_key"] = submitted_api_key
else:
    # Keep existing key from current settings
    new_config["radarr"]["api_key"] = settings.radarr.api_key.get_secret_value()
```

### Pattern 4: Hot Reload via Settings Re-instantiation
**What:** After saving new TOML config, reload `Settings` from the file, update `app.state.settings`, and reschedule APScheduler jobs with new intervals.
**When to use:** POST /settings handler after successful config save.
**Example:**
```python
# After writing new config to TOML file:
new_settings = load_settings(config_path)
app.state.settings = new_settings

# Reschedule jobs if intervals changed:
scheduler = app.state.scheduler
if new_settings.radarr.enabled:
    scheduler.reschedule_job(
        "radarr_search",
        trigger="interval",
        minutes=new_settings.radarr.search_interval,
    )
```
**Source:** [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)

### Pattern 5: Search Now via Direct Job Execution
**What:** POST /api/search-now/{app} runs the search cycle function immediately without waiting for the scheduler interval. The cycle runs in the same event loop.
**When to use:** Dashboard "Search Now" button.
**Example:**
```python
@router.post("/api/search-now/{app_name}")
async def search_now(request: Request, app_name: str):
    # Run cycle function directly (same event loop, safe)
    if app_name == "radarr" and request.app.state.radarr_client:
        state = await run_radarr_cycle(
            request.app.state.radarr_client,
            request.app.state.fetcharr_state,
            request.app.state.settings,
        )
        save_state(state, STATE_PATH)
    # Return updated card partial
    return templates.TemplateResponse(...)
```

### Anti-Patterns to Avoid
- **Global module-level state:** Do NOT use module-level dicts/variables for shared state. The lifespan context manager is the correct place to create and share mutable state. Use `app.state` exclusively.
- **Polling the *arr API on every dashboard poll:** Dashboard polls every 5 seconds. Fetching item counts from Radarr/Sonarr on every poll would hammer the API. Cache counts in `app.state` and refresh them only during search cycles.
- **Rendering full pages for htmx requests:** htmx expects HTML fragments for swap targets. Return partials (not full pages with `<html>` wrapper) from polling endpoints. The initial page load gets the full page; subsequent polls get fragments.
- **Writing API keys to HTML:** Never put `SecretStr.get_secret_value()` into template context. Always use a masked placeholder string.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS utility framework | Custom CSS | Tailwind CSS via pytailwindcss | Thousands of edge cases in responsive design, dark mode, spacing |
| AJAX polling | Custom JavaScript fetch loops | htmx `hx-trigger="every 5s"` | htmx handles DOM diffing, request deduplication, error recovery |
| Template rendering | String concatenation or f-strings | Jinja2Templates (FastAPI built-in) | Auto-escaping, template inheritance, `url_for()` helpers |
| TOML serialization | Manual string building | `tomli_w.dumps()` | TOML quoting rules, table nesting, array formatting |
| Form parsing | Manual `request.body()` parsing | `request.form()` (Starlette built-in) | Handles multipart, URL-encoded, validation |
| Static file serving | Custom file-read routes | `StaticFiles` mount (Starlette built-in) | Correct MIME types, caching headers, async IO |

**Key insight:** The entire UI layer is glue code between existing systems (state, settings, scheduler) and HTML rendering. Every component has a battle-tested library. The only custom logic is the routing and template context assembly.

## Common Pitfalls

### Pitfall 1: State Reference Staleness After Config Reload
**What goes wrong:** After hot-reloading settings, the scheduler job closures still capture the old `settings` object via `nonlocal`. The jobs continue using stale config.
**Why it happens:** Python closures capture the variable binding, but if you replace `app.state.settings` without updating what the job closure references, the job keeps the old object.
**How to avoid:** The job closures must read `app.state.settings` at execution time (via the app reference) rather than capturing a settings variable at lifespan creation time. Alternatively, pass a mutable container (like a dict or list) that the closure reads from.
**Warning signs:** Changing interval in settings page has no effect until restart.

### Pitfall 2: Race Between htmx Poll and Search Cycle
**What goes wrong:** htmx polls `/partials/app-card/radarr` while `run_radarr_cycle` is mutating the state dict. Partial render sees inconsistent data.
**Why it happens:** Both run on the same event loop, but the cycle is an async function with multiple `await` points. If a poll request arrives between awaits, it reads partially-updated state.
**How to avoid:** This is acceptable for a status dashboard -- "eventually consistent" display is fine. The state dict is updated atomically at the field level (cursor, last_run). Worst case: dashboard shows old cursor with new timestamp for one poll cycle (5s).
**Warning signs:** None -- this is a cosmetic issue, not a correctness issue.

### Pitfall 3: Tailwind CSS Not Compiling New Classes
**What goes wrong:** Adding new Tailwind utility classes in templates but the compiled CSS doesn't include them.
**Why it happens:** Tailwind CSS v4 uses automatic content detection, scanning template files. If the templates directory isn't in the scan path, new classes are missed.
**How to avoid:** Ensure the Tailwind CSS input file has `@import "tailwindcss"` and the CLI is run with the correct source paths. For development: `tailwindcss -i fetcharr/static/css/input.css -o fetcharr/static/css/output.css --watch`. The `--watch` flag recompiles on template changes.
**Warning signs:** Elements missing expected styling despite correct class names.

### Pitfall 4: API Key Leaking via Form Value Attribute
**What goes wrong:** Rendering `<input value="{{ api_key }}">` puts the actual key into HTML source.
**Why it happens:** Developer convenience -- wanting to show the current value in an edit form.
**How to avoid:** Always use a placeholder string (`"********"` or empty) for the `value` attribute. The HTML `placeholder` attribute shows hint text without being a form value. On POST, empty value means "keep existing key."
**Warning signs:** View page source shows actual API key in input element.

### Pitfall 5: tomli_w Losing Config Comments
**What goes wrong:** User's manually-added comments in `fetcharr.toml` are stripped after saving via the config editor.
**Why it happens:** `tomli_w.dumps()` serializes a Python dict to TOML. Comments are not part of the data model.
**How to avoid:** Accept this limitation. The config editor saves a clean, machine-generated TOML file. Document in the UI that saving via the editor replaces the file content. The default template with comments is only used for first-run generation (before the user ever opens the editor).
**Warning signs:** User complains about lost comments after using config editor.

### Pitfall 6: Jinja2 Not Installed
**What goes wrong:** `ImportError: jinja2 must be installed to use Jinja2Templates` at runtime.
**Why it happens:** Jinja2 is not a hard dependency of FastAPI -- it's only required when using templates. Currently NOT installed in the project venv.
**How to avoid:** Add `"jinja2"` to pyproject.toml dependencies before implementing template routes.
**Warning signs:** Import error on first template route hit.

## Code Examples

Verified patterns from official sources:

### Jinja2Templates Setup with StaticFiles
```python
# Source: https://fastapi.tiangolo.com/advanced/templates/
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="fetcharr/static"), name="static")
templates = Jinja2Templates(directory="fetcharr/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "Fetcharr"},
    )
```

### htmx Polling for Dashboard Panels
```html
<!-- Source: https://htmx.org/attributes/hx-trigger/ -->
<!-- Initial load includes the full card; htmx replaces it every 5s -->
<div id="radarr-card"
     hx-get="/partials/app-card/radarr"
     hx-trigger="every 5s"
     hx-swap="outerHTML">
  <!-- Server-rendered initial content -->
  {% include "partials/app_card.html" %}
</div>
```

### TOML Config Write with tomli_w
```python
# Source: https://pypi.org/project/tomli-w/
import tomli_w

config_dict = {
    "general": {"log_level": "info"},
    "radarr": {
        "url": "http://radarr:7878",
        "api_key": "actual-key-here",
        "enabled": True,
        "search_interval": 30,
        "search_missing_count": 5,
        "search_cutoff_count": 5,
    },
    "sonarr": {
        "url": "http://sonarr:8989",
        "api_key": "actual-key-here",
        "enabled": False,
        "search_interval": 30,
        "search_missing_count": 5,
        "search_cutoff_count": 5,
    },
}

toml_bytes = tomli_w.dumps(config_dict)
config_path.write_text(toml_bytes)
```

### APScheduler 3.x Job Rescheduling
```python
# Source: https://apscheduler.readthedocs.io/en/3.x/userguide.html
scheduler.reschedule_job(
    "radarr_search",
    trigger="interval",
    minutes=new_interval,
)
# next_run_time is recalculated from now
```

### APScheduler Get Next Run Time
```python
# Source: https://apscheduler.readthedocs.io/en/3.x/modules/job.html
job = scheduler.get_job("radarr_search")
if job:
    next_run = job.next_run_time  # datetime or None
```

### Tailwind CSS v4 Input File
```css
/* fetcharr/static/css/input.css */
@import "tailwindcss";

/* Custom theme overrides for Fetcharr dark mode */
@theme {
  --color-fetcharr-green: #22c55e;
  --color-fetcharr-bg: #0f172a;
  --color-fetcharr-card: #1e293b;
  --color-fetcharr-border: #334155;
}
```

### Tailwind CSS Build Command
```bash
# Development (watch mode):
tailwindcss -i fetcharr/static/css/input.css -o fetcharr/static/css/output.css --watch

# Production (minified):
tailwindcss -i fetcharr/static/css/input.css -o fetcharr/static/css/output.css --minify
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind v3 `tailwind.config.js` | Tailwind v4 CSS-first config (`@theme` directive) | Jan 2025 | No JavaScript config file needed; configuration lives in CSS |
| htmx 1.x | htmx 2.0.8 | Jun 2024 | Dropped IE support; cleaner attribute naming; otherwise backward-compatible |
| APScheduler 4.x | APScheduler 3.x (stable) | Ongoing | 4.x is still alpha; 3.11.2 is the stable release. Project correctly uses 3.x. |

**Deprecated/outdated:**
- `tailwind.config.js`: Replaced by CSS-first `@theme` directive in Tailwind v4. The standalone CLI with `@import "tailwindcss"` handles everything.
- FastAPI `startup`/`shutdown` events: Replaced by `lifespan` context manager (already used in this project).

## Open Questions

1. **Item counts from *arr API: where to fetch?**
   - What we know: WEBU-04 requires showing wanted and cutoff-unmet counts per app. The state file stores cursors but not counts.
   - What's unclear: Whether to add a lightweight API call in the search cycle to fetch total counts, or to make a separate periodic job.
   - Recommendation: Add count tracking to the search cycle functions. They already call `get_wanted_missing()` and `get_wanted_cutoff()` which return the full list. Store `len(missing)` and `len(cutoff)` in `app.state.item_counts` after each cycle. This avoids extra API calls.

2. **Connection health tracking granularity**
   - What we know: WEBU-06 requires "unreachable since [time]". The search cycle already catches `httpx.HTTPError` for abort scenarios.
   - What's unclear: Should connection health be checked independently of search cycles, or only updated when a cycle runs?
   - Recommendation: Update connection health during each search cycle. If the cycle aborts due to connection failure, record `unreachable_since`. If it succeeds, clear it. For apps with long intervals (e.g., 60 minutes), the dashboard might show stale "connected" status. This is acceptable -- the user decided no toasts, just polling updates.

3. **Scheduler job management during enable/disable toggle**
   - What we know: Config editor can toggle `enabled` per app. APScheduler has `add_job`, `remove_job`, `reschedule_job`.
   - What's unclear: Should disabling an app remove the job entirely or pause it?
   - Recommendation: Remove the job with `scheduler.remove_job("radarr_search")` on disable. Re-add with `scheduler.add_job(...)` on enable. Also close/create the corresponding httpx client. This is cleaner than pausing.

## Sources

### Primary (HIGH confidence)
- [FastAPI Templates docs](https://fastapi.tiangolo.com/advanced/templates/) - Jinja2Templates setup, StaticFiles mount, TemplateResponse pattern
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - Lifespan context manager, app.state sharing
- [htmx hx-trigger docs](https://htmx.org/attributes/hx-trigger/) - Polling syntax `every Ns`, filters, stop code 286
- [htmx hx-swap docs](https://htmx.org/attributes/hx-swap/) - innerHTML, outerHTML swap strategies
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) - reschedule_job, modify_job, get_job, AsyncIOScheduler
- [tomli_w PyPI](https://pypi.org/project/tomli-w/) - TOML write API, dumps() function
- [Pydantic SecretStr docs](https://docs.pydantic.dev/2.0/usage/types/secrets/) - get_secret_value(), serialization masking

### Secondary (MEDIUM confidence)
- [pytailwindcss PyPI](https://pypi.org/project/pytailwindcss/) - Standalone Tailwind CLI via pip, version pinning via TAILWINDCSS_VERSION env var
- [Tailwind CSS v4 blog](https://tailwindcss.com/blog/tailwindcss-v4) - CSS-first configuration, @theme directive, automatic content detection
- [TestDriven.io FastAPI + htmx guide](https://testdriven.io/blog/fastapi-htmx/) - HX-Request header detection, partial rendering patterns

### Tertiary (LOW confidence)
- None -- all critical claims verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed or well-documented; FastAPI + Jinja2 + htmx is a proven combination
- Architecture: HIGH - app.state sharing, htmx polling, and partial template patterns are documented in official sources
- Pitfalls: HIGH - State reference staleness and API key masking are well-understood problems with clear solutions

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (30 days -- stable ecosystem, no breaking changes expected)
