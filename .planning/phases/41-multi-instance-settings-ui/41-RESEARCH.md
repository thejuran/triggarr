# Phase 41: Multi-Instance Settings UI - Research

**Researched:** 2026-03-11
**Domain:** FastAPI + htmx + Jinja2 settings form, multi-instance CRUD, tag autocomplete
**Confidence:** HIGH

## Summary

Phase 41 overhauls the settings page from showing only the first instance per app type to a full multi-instance management UI. The current `settings.html` iterates `apps.items()` with a flat `{radarr: {...}, sonarr: {...}}` context, rendering one card per app type. This must become a nested loop over instances within each app type, with add/edit/remove/enable-disable controls per instance.

The backend `save_settings` route already handles multi-instance TOML writing (dict-of-dicts structure in `Settings.radarr` / `Settings.sonarr`), including scheduler update, client lifecycle, and state entry creation. The primary gap is: (1) the settings page template only shows the first instance, (2) there is no UI for add/remove instance operations, (3) tag fields (`missing_tag`, `cutoff_tag`) are not exposed in the form, and (4) there is no tag autocomplete endpoint.

**Primary recommendation:** Expand settings.html to loop over all instances per app type with accordion sections, add a new `/api/tags/{app_name}/{instance_name}` JSON endpoint that proxies `get_tags()` for autocomplete, and refactor `save_settings` to accept dynamic instance form fields keyed by instance name.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INST-05 | User can add, edit, and remove instances from the web UI settings page | Template restructure to show all instances; dynamic form fields keyed by instance name; add-instance button creates new section; remove-instance button with confirmation |
| INST-06 | User can enable/disable individual instances from the web UI | Per-instance enable checkbox already exists in the data model; needs per-instance toggle in the template |
| TAG-06 | Tag name autocomplete dropdown populated from the *arr instance when configuring filters in the web UI | New API endpoint `/api/tags/{app_name}/{instance_name}` returning JSON tag list; `<datalist>` HTML element or htmx-powered dropdown bound to tag input fields |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | Web framework, API routes | Already used throughout |
| Jinja2 | current | HTML templating | Already used for all templates |
| htmx | current | Dynamic UI updates without JS frameworks | Already loaded in base.html |
| Tailwind CSS v4 | current | Styling | Already configured |
| tomli_w | current | TOML config writing | Already used for atomic writes |
| pydantic | current | Form validation, model validation | Already used for Settings model |

### Supporting (no new dependencies needed)
| Library | Purpose | When to Use |
|---------|---------|-------------|
| HTML `<datalist>` | Native autocomplete for tag fields | Simplest approach, no JS needed beyond htmx |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `<datalist>` | Custom JS dropdown (Select2, Choices.js) | Overkill; `<datalist>` is native, accessible, zero-dependency |
| Full SPA form | htmx partials | htmx is already the pattern; no reason to add JS framework |

**Installation:** No new packages needed.

## Architecture Patterns

### Current Settings Architecture
```
GET /settings  -->  settings_page()  -->  settings.html
                     reads first instance only (line 207)

POST /settings -->  save_settings()  -->  atomic TOML write
                     processes form for first instance only (line 331-386)
```

### Target Settings Architecture
```
GET /settings  -->  settings_page()  -->  settings.html (all instances)
                     passes ALL instances per app type

POST /settings -->  save_settings()  -->  atomic TOML write
                     processes dynamic instance form fields
                     handles add/remove/edit for all instances

GET /api/tags/{app}/{instance} --> tag_autocomplete() --> JSON [{id, label}]
                     proxies get_tags() from existing client
```

### Pattern 1: Dynamic Instance Form Fields
**What:** Form field names keyed by app type and instance name
**When to use:** Multi-instance forms where instance count is dynamic
**Example:**
```html
<!-- Field naming convention: {app}_{instance}_{field} -->
<input name="radarr__Default__url" value="http://radarr:7878">
<input name="radarr__Default__api_key" type="password">
<input name="radarr__4K Radarr__url" value="http://radarr4k:7878">
```

The double-underscore separator (`__`) avoids collision with instance names that contain single underscores. The `save_settings` route parses form keys to reconstruct the dict-of-dicts structure.

### Pattern 2: Accordion Instance Sections
**What:** Each instance is a collapsible section within its app type group
**When to use:** Multiple instances per app type, need to minimize visual clutter
**Example:**
```html
{% for inst_name, inst in instances.items() %}
<details class="bg-triggarr-card rounded-lg border border-triggarr-border" open>
    <summary class="p-4 cursor-pointer flex justify-between items-center">
        <span class="font-semibold">{{ inst_name }}</span>
        <span class="text-xs text-triggarr-muted">{{ "Enabled" if inst.enabled else "Disabled" }}</span>
    </summary>
    <div class="p-5 pt-0">
        <!-- instance fields -->
    </div>
</details>
{% endfor %}
```

HTML `<details>/<summary>` is native, accessible, zero-JS. Matches the project's minimal-JS philosophy.

### Pattern 3: Tag Autocomplete via htmx + datalist
**What:** Populate `<datalist>` options by fetching tags from the *arr instance
**When to use:** TAG-06 requirement
**Example:**
```html
<input type="text" name="radarr__Default__missing_tag" value="{{ inst.missing_tag }}"
       list="tags-radarr-Default"
       hx-get="/api/tags/radarr/Default"
       hx-trigger="focus once"
       hx-target="#tags-radarr-Default"
       hx-swap="innerHTML">
<datalist id="tags-radarr-Default"></datalist>
```

The htmx call fetches tag options on first focus, populating the datalist. The endpoint returns `<option>` elements directly (HTML partial), keeping it in the htmx pattern.

### Pattern 4: Add/Remove Instance
**What:** JavaScript-free add via form POST to a dedicated endpoint, or inline htmx
**When to use:** INST-05 add/remove operations
**Example approach:**
- "Add Instance" button at the bottom of each app section
- Creates a new instance with a user-provided name and defaults
- "Remove Instance" button per instance with `confirm()` guard
- Both can be htmx POST endpoints that return the updated instance list partial

### Anti-Patterns to Avoid
- **Parsing instance names from form field names with simple split:** Instance names can contain underscores. Use double-underscore (`__`) as separator, or encode instance names.
- **In-place instance rename:** Renaming creates complexity with state, scheduler, and client references. Don't allow rename; add-new + remove-old is safer.
- **Client-side-only form manipulation:** Adding/removing instance sections purely with JS means the server never validates until save. Keep the server authoritative.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Autocomplete dropdown | Custom JS typeahead | HTML `<datalist>` + htmx | Native, accessible, zero-dep |
| Collapsible sections | Custom JS accordion | HTML `<details>/<summary>` | Native, accessible, zero-dep |
| Form validation | Custom JS validators | Pydantic model validation on POST | Already the pattern (line 388-393) |
| Confirmation dialogs | Custom modal component | Browser `confirm()` via `hx-confirm` attribute | htmx built-in |

**Key insight:** The project uses htmx specifically to avoid custom JavaScript. Every UI interaction should be achievable with htmx attributes + server-rendered HTML partials.

## Common Pitfalls

### Pitfall 1: Instance Name Collision in Form Fields
**What goes wrong:** Instance names containing the separator character break form parsing
**Why it happens:** Names like "My_Instance" conflict with single-underscore separators
**How to avoid:** Use double-underscore (`__`) as app/instance/field separator. Validate instance names on creation to disallow double-underscores.
**Warning signs:** Form data parsing returns wrong instance name or field name

### Pitfall 2: API Key Leakage in Multi-Instance Form
**What goes wrong:** Sending all instance API keys as form values exposes them in browser memory/history
**Why it happens:** Current pattern sends empty password field with masked placeholder
**How to avoid:** Keep the current pattern: password fields always empty, placeholder shows "********" if key exists. On save, preserve existing key when submitted field is empty.
**Warning signs:** API keys visible in form source or network tab

### Pitfall 3: Lost Instance Data on Save
**What goes wrong:** Saving from a form that only shows some instances drops non-displayed instances
**Why it happens:** Form only submits fields that are rendered in the HTML
**How to avoid:** Render ALL instances in the form (even disabled ones). The current `save_settings` preserves non-edited instances (BUG-05 fix in Phase 40), but with full multi-instance editing, all instances are in the form.
**Warning signs:** Instances disappear after settings save

### Pitfall 4: Tag Endpoint Without Active Client
**What goes wrong:** Tag autocomplete fails when instance has no active client (disabled or not yet saved)
**Why it happens:** Client dict only contains clients for enabled instances
**How to avoid:** Create a temporary client for the tag fetch if no active client exists, or return empty list with appropriate message. Best: require instance to be saved and enabled before tag autocomplete works.
**Warning signs:** 500 error on tag fetch for new/disabled instances

### Pitfall 5: Scheduler Orphan Jobs After Instance Removal
**What goes wrong:** Removing an instance leaves its scheduler job running
**Why it happens:** `save_settings` only handles disabled instances, not deleted ones
**How to avoid:** When processing instance removal, explicitly stop scheduler job, close client, and clean up state entry. The existing `save_settings` loop already handles missing instances (line 412-418).
**Warning signs:** Log messages for removed instance, ghost entries in state

### Pitfall 6: Max 5 Instance Limit Not Enforced in UI
**What goes wrong:** User adds 6th instance, gets confusing Pydantic validation error on redirect
**Why it happens:** `validate_instances` raises ValueError but save_settings returns redirect with no error message
**How to avoid:** Check instance count before adding in the add-instance endpoint. Display count in UI.
**Warning signs:** Settings redirect with no visible change after adding instance

## Code Examples

### Current settings_page Context Building (to be replaced)
```python
# Source: triggarr/web/routes.py lines 194-235
# Shows ONLY the first instance per app type
for name in ("radarr", "sonarr"):
    instances = getattr(settings, name)
    if instances:
        first_name = next(iter(instances))
        cfg = instances[first_name]
    # ... builds single-instance context
```

### Target: All Instances in Context
```python
# Pass all instances with their names to the template
for name in ("radarr", "sonarr"):
    instances = getattr(settings, name)
    app_instances = {}
    for inst_name, cfg in instances.items():
        app_instances[inst_name] = {
            "url": cfg.url,
            "has_api_key": bool(cfg.api_key.get_secret_value()),
            "enabled": cfg.enabled,
            "search_interval": cfg.search_interval,
            "search_missing_count": cfg.search_missing_count,
            "search_cutoff_count": cfg.search_cutoff_count,
            "missing_tag": cfg.missing_tag,
            "cutoff_tag": cfg.cutoff_tag,
        }
    apps[name] = app_instances
```

### Tag Autocomplete Endpoint
```python
@router.get("/api/tags/{app_name}/{instance_name}", response_class=HTMLResponse)
async def tag_autocomplete(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Return <option> elements for tag autocomplete datalist."""
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("")
    clients = getattr(request.app.state, f"{app_name}_clients", {})
    client = clients.get(instance_name)
    if not client:
        return HTMLResponse("")
    try:
        tags = await client.get_tags()
        options = "".join(f'<option value="{tag.label}">' for tag in tags)
        return HTMLResponse(options)
    except Exception:
        return HTMLResponse("")
```

### Form Field Parsing for Dynamic Instances
```python
# Parse form keys like "radarr__Default__url" into nested dict
import re
INSTANCE_FIELD_RE = re.compile(r"^(radarr|sonarr)__(.+)__(\w+)$")

for key in form.keys():
    match = INSTANCE_FIELD_RE.match(key)
    if match:
        app, inst_name, field = match.groups()
        # Build nested config dict
```

### Instance Name Validation
```python
def validate_instance_name(name: str) -> tuple[bool, str]:
    """Validate a user-supplied instance name."""
    name = name.strip()
    if not name:
        return (False, "Instance name cannot be empty")
    if len(name) > 32:
        return (False, "Instance name too long (max 32 characters)")
    if "__" in name:
        return (False, "Instance name cannot contain double underscores")
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9 _.-]*$", name):
        return (False, "Instance name must start with alphanumeric and contain only letters, numbers, spaces, underscores, dots, hyphens")
    return (True, "")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single instance per app | Multi-instance dict config | v2.3 Phase 33 | Settings UI still shows first-only |
| No tag fields in UI | Tag fields in model only | v2.3 Phase 36 | Settings form never renders tag fields |
| Full page form submit | PRG pattern with redirect | v2.0 | Keep this pattern for save_settings |

**Current gaps:**
- `settings_page()` line 207: "Show first instance for settings form (Phase 39: multi-instance editing)" -- this is the TODO we are closing
- `save_settings()` line 331: Only processes first instance from form data
- Tag fields `missing_tag`/`cutoff_tag` exist in `InstanceConfig` but are never rendered or accepted from the form

## Open Questions

1. **Add Instance UX: inline or separate endpoint?**
   - What we know: htmx can POST to an add endpoint and swap in a new instance section
   - What's unclear: Whether to use a modal, inline form, or separate page
   - Recommendation: Inline "Add Instance" button at the bottom of each app section that POST-creates with a name prompt via `hx-prompt` (htmx built-in), then returns the full updated section

2. **Instance deletion: soft or hard?**
   - What we know: Removing from TOML and cleaning up state/scheduler/client is needed
   - What's unclear: Whether to support "undo" or require confirmation only
   - Recommendation: Hard delete with `hx-confirm` browser confirmation. State cleanup follows existing patterns in `save_settings`.

3. **Form submission approach: single POST or per-instance?**
   - What we know: Current pattern is a single form POST for everything
   - What's unclear: Whether keeping one big form or splitting per-instance is cleaner
   - Recommendation: Keep single form POST. All instances are in one `<form>`. Add/remove are separate htmx POST endpoints that modify config and return updated page sections.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_web.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-05 | Settings page lists all instances | unit | `uv run pytest tests/test_web.py -x -q -k "test_settings_all_instances"` | No - Wave 0 |
| INST-05 | Add instance creates new entry in config | unit | `uv run pytest tests/test_web.py -x -q -k "test_add_instance"` | No - Wave 0 |
| INST-05 | Remove instance deletes entry and cleans up | unit | `uv run pytest tests/test_web.py -x -q -k "test_remove_instance"` | No - Wave 0 |
| INST-05 | Edit instance saves all field changes | unit | `uv run pytest tests/test_web.py -x -q -k "test_save_multi_instance"` | No - Wave 0 |
| INST-06 | Enable/disable toggle per instance | unit | `uv run pytest tests/test_web.py -x -q -k "test_instance_enable_disable"` | No - Wave 0 |
| TAG-06 | Tag autocomplete endpoint returns options | unit | `uv run pytest tests/test_web.py -x -q -k "test_tag_autocomplete"` | No - Wave 0 |
| TAG-06 | Tag fields rendered in settings form | unit | `uv run pytest tests/test_web.py -x -q -k "test_tag_fields_in_form"` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_web.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Test cases for multi-instance settings CRUD in `tests/test_web.py`
- [ ] Test for tag autocomplete endpoint in `tests/test_web.py`
- [ ] Test for instance name validation in `tests/test_validation.py`

*(Existing test infrastructure -- `test_web.py` fixture `test_app` with mocked state -- covers the foundation. New tests extend existing patterns.)*

## Sources

### Primary (HIGH confidence)
- `triggarr/web/routes.py` - Current settings_page and save_settings implementation, line-by-line analysis
- `triggarr/templates/settings.html` - Current single-instance template structure
- `triggarr/models/config.py` - Settings model with `dict[str, InstanceConfig]` structure, max 5 instances validator
- `triggarr/clients/base.py` - `get_tags()` method returning `list[Tag]` from `/api/v3/tag`
- `triggarr/web/validation.py` - Existing URL and integer validation helpers
- `tests/test_web.py` - Existing test patterns for settings routes

### Secondary (MEDIUM confidence)
- htmx `hx-prompt` attribute for inline name prompts (from htmx docs, well-established feature)
- HTML `<datalist>` for autocomplete (web standard, widely supported)
- HTML `<details>/<summary>` for accordion (web standard)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all existing tools
- Architecture: HIGH - extending existing patterns, clear path from current to target
- Pitfalls: HIGH - identified from direct code analysis of existing save_settings bugs and fixes

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable, no external dependency changes)
