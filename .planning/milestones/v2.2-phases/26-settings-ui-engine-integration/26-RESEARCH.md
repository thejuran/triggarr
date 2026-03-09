# Phase 26: Settings UI & Engine Integration - Research

**Researched:** 2026-03-09
**Domain:** FastAPI + htmx settings form, search pipeline integration
**Confidence:** HIGH

## Summary

Phase 26 connects the `skip_unreleased` config field (added in Phase 25) to both the web UI and the search engine pipeline. The config field and filter function already exist -- this phase has two jobs: (1) add a checkbox toggle to the settings page that reads/writes the field, and (2) conditionally call `filter_unreleased_movies()` inside `run_radarr_cycle()` based on the toggle state.

The existing codebase provides a clear, well-established pattern for both changes. Every other settings field follows the same three-location pattern (model field, template input, route handler), and the search engine already has the filter function ready to insert. No new libraries or patterns are needed.

**Primary recommendation:** Follow the existing checkbox pattern (see `{name}_enabled` in settings.html) for the toggle, and insert a 2-line conditional filter call in run_radarr_cycle after `filter_monitored` and before `slice_batch`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-01 | User can enable/disable skip-unreleased-media filtering via web UI toggle | Settings template checkbox + route handler read/write + settings_page context passing |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | existing | Web framework, form handling | Already used |
| Jinja2 | existing | Template rendering | Already used |
| Tailwind CSS v4 | existing | Styling | Already used |
| tomli_w | existing | TOML writing | Already used in save_settings |
| Pydantic | existing | Config validation | Already used |

### No new dependencies needed
This phase requires zero new libraries. Everything needed is already in the project.

## Architecture Patterns

### Three-Location Round-Trip Pattern (ESTABLISHED)

Every settings field in Triggarr follows this exact pattern across three files:

**Location 1: Model** (`triggarr/models/config.py`)
- Already done in Phase 25: `skip_unreleased: bool = True` in `GeneralConfig`

**Location 2: Template** (`triggarr/templates/settings.html`)
- Add checkbox input with `name="skip_unreleased"` in the General section
- Follow the existing `{name}_enabled` checkbox pattern for styling
- Pass current value from route context to set `checked` attribute

**Location 3: Route handler** (`triggarr/web/routes.py`)
- `settings_page()` (GET): Add `skip_unreleased` to template context from `settings.general.skip_unreleased`
- `save_settings()` (POST): Read `form.get("skip_unreleased") == "on"` and include in `new_config["general"]`

### Checkbox Form Pattern (ESTABLISHED)

HTML checkboxes only send a value when checked. The existing pattern:
```python
# In save_settings route (routes.py line 298)
"enabled": form.get(f"{name}_enabled") == "on",
```
```html
<!-- In template (settings.html line 71-73) -->
<input type="checkbox" name="{{ name }}_enabled"
       {% if app.enabled %}checked{% endif %}
       class="accent-triggarr-green w-4 h-4">
```

The `skip_unreleased` toggle must use this same `== "on"` pattern.

### Pipeline Filter Insertion Point (ESTABLISHED)

The success criteria specifies: "filter runs after filter_monitored, before cursor/slice_batch". In `run_radarr_cycle()`:

```python
# Current (engine.py ~line 292-294):
missing = filter_monitored(missing)
cursor = state["radarr"]["missing_cursor"]
batch, new_cursor = slice_batch(missing, cursor, missing_limit)

# After change:
missing = filter_monitored(missing)
if settings.general.skip_unreleased:
    missing = filter_unreleased_movies(missing)
cursor = state["radarr"]["missing_cursor"]
batch, new_cursor = slice_batch(missing, cursor, missing_limit)
```

Key constraints from requirements:
- Only applies to missing queue (cutoff-unmet items already have files, per FILT-04)
- Only applies to Radarr (Sonarr filtering is unconditional, per STATE.md decision)
- When disabled, all monitored movies pass through unfiltered

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Checkbox state handling | Custom JS toggle logic | Native HTML checkbox + form POST | Existing pattern works, no JS needed |
| Config persistence | Custom file format | tomli_w.dumps (existing) | Already handles TOML round-trip |
| Validation | Manual bool parsing | Pydantic model validation (existing) | Already validates all config on save |

## Common Pitfalls

### Pitfall 1: Checkbox sends nothing when unchecked
**What goes wrong:** HTML checkboxes don't send any form data when unchecked. If you check for the key's existence, `form.get("skip_unreleased")` returns `None` when unchecked.
**Why it happens:** HTML spec behavior.
**How to avoid:** Use `form.get("skip_unreleased") == "on"` which correctly evaluates to `False` when the key is absent. This is the existing pattern in the codebase.
**Warning signs:** Toggle always saves as False regardless of checkbox state.

### Pitfall 2: Forgetting to pass value to template context
**What goes wrong:** The checkbox renders but doesn't reflect the saved state on page reload.
**Why it happens:** `settings_page()` doesn't include `skip_unreleased` in context dict.
**How to avoid:** Add `"skip_unreleased": settings.general.skip_unreleased` to the context dict in the GET handler.
**Warning signs:** Toggle resets to unchecked on every page load.

### Pitfall 3: Applying filter to cutoff queue
**What goes wrong:** Cutoff-unmet items (already downloaded, need quality upgrade) get filtered out.
**Why it happens:** Copy-pasting the filter call to both queues.
**How to avoid:** Only insert the filter in the missing queue section, never cutoff. This is explicitly documented in FILT-04 and the filter function docstring.
**Warning signs:** Cutoff searches stop happening for unreleased movies that already have files.

### Pitfall 4: Mock settings missing skip_unreleased in tests
**What goes wrong:** Test fixture's MagicMock auto-creates attributes, masking missing context.
**Why it happens:** MagicMock returns a MagicMock for any attribute access, which is truthy.
**How to avoid:** Explicitly set `mock_settings.general.skip_unreleased = True` in the test_app fixture.
**Warning signs:** Tests pass but don't actually verify the toggle behavior.

## Code Examples

### Template Checkbox (based on existing pattern)
```html
<!-- In General section of settings.html, after the existing fields -->
<div class="flex items-center gap-3">
    <input type="checkbox" name="skip_unreleased"
           {% if skip_unreleased %}checked{% endif %}
           class="accent-triggarr-green w-4 h-4"
           id="skip_unreleased">
    <label for="skip_unreleased" class="text-sm">Skip Unreleased Movies</label>
</div>
<p class="text-xs text-triggarr-muted mt-1">
    Skip Radarr movies without a past digital or physical release date.
</p>
```

### Route GET Context Addition
```python
# In settings_page(), add to context dict:
"skip_unreleased": settings.general.skip_unreleased,
```

### Route POST Reading
```python
# In save_settings(), add to new_config["general"] dict:
"skip_unreleased": form.get("skip_unreleased") == "on",
```

### Engine Pipeline Insertion
```python
# In run_radarr_cycle(), after filter_monitored(missing):
if settings.general.skip_unreleased:
    missing = filter_unreleased_movies(missing)
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_web.py tests/test_search.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01a | Settings page shows skip_unreleased checkbox | unit | `uv run pytest tests/test_web.py -k "skip_unreleased" -x` | Needs new tests |
| CFG-01b | Toggle state saves and round-trips | unit | `uv run pytest tests/test_web.py -k "skip_unreleased" -x` | Needs new tests |
| CFG-01c | Engine calls filter when enabled | unit | `uv run pytest tests/test_search.py -k "skip_unreleased" -x` | Needs new tests |
| CFG-01d | Engine skips filter when disabled | unit | `uv run pytest tests/test_search.py -k "skip_unreleased" -x` | Needs new tests |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_web.py tests/test_search.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_web.py` -- new tests for skip_unreleased checkbox rendering + save round-trip
- [ ] `tests/test_search.py` or `tests/test_web.py` -- new tests for engine conditional filter call
- [ ] `tests/test_web.py` -- mock_settings fixture needs `skip_unreleased = True` added

## Open Questions

None -- all requirements and integration points are clear from the existing codebase.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of all files involved:
  - `triggarr/models/config.py` -- GeneralConfig.skip_unreleased already exists
  - `triggarr/config.py` -- DEFAULT_CONFIG already includes skip_unreleased comment
  - `triggarr/search/engine.py` -- filter_unreleased_movies() exists but not yet called
  - `triggarr/web/routes.py` -- settings_page() and save_settings() patterns
  - `triggarr/templates/settings.html` -- checkbox pattern from enabled toggles
  - `tests/test_web.py` -- existing test patterns for settings round-trip
  - `tests/test_search.py` -- existing filter_unreleased_movies tests

### Secondary (HIGH confidence)
- `.planning/REQUIREMENTS.md` -- CFG-01 requirement definition
- `.planning/phases/25-filter-foundation/25-01-SUMMARY.md` -- Phase 25 completion details
- `.planning/STATE.md` -- locked decisions about filter placement and scope

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- zero new dependencies, all existing
- Architecture: HIGH -- three-location pattern is well-established with 6+ existing fields
- Pitfalls: HIGH -- all derived from direct codebase analysis of existing patterns

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable -- no external dependencies involved)
