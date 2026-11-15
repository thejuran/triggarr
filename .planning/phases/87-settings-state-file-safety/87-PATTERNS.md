# Phase 87: Settings & State-File Safety - Pattern Map

**Mapped:** 2026-11-15
**Files analyzed:** 4 modified (no new files — this phase is pure in-place hardening per RESEARCH.md "Recommended Project Structure")
**Analogs found:** 4 / 4 (every file has a same-repo sibling that already does the target behavior correctly)

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|----------------|------|-----------|-----------------|---------------|
| `triggarr/web/routes.py::remove_instance` (938-995) | route/controller | CRUD (settings write) | `triggarr/web/routes.py::add_instance` (883-934) | exact — same file, same mutation shape, only the operation (delete vs. insert) differs |
| `triggarr/web/routes.py::remove_instance` error response | route/controller | request-response (htmx partial vs. plain) | `triggarr/web/routes.py::change_password` (1658-1746) + `triggarr/templates/partials/security_password.html` | role-match — "always-200, template differentiates" htmx precedent; `change_password` swaps into a named `#password-section` div, not `body` |
| `triggarr/state.py::load_state` (210-245) | utility / file-I/O loader | file-I/O (startup JSON load + recovery) | same file, same function — existing `except (JSONDecodeError, OSError)` branch (230-239) | exact — the new non-dict-root guard is an additional branch in the function that already has the target recovery shape |
| new helper `_recover_from_bad_state_file` (or equivalent name) in `triggarr/state.py` | utility | file-I/O (best-effort backup copy) | `triggarr/config.py::detect_and_migrate_v22` (372-412), specifically its `shutil.copy2` backup step (401-402) | role-match — same stdlib call, same "exactly one fixed-name copy" shape; **gap**: the analog has no try/except around the copy (see Shared Patterns note) |
| `triggarr/templates/settings.html` instance row / Remove button (159-172) | template | request-response (htmx target/swap wiring) | `triggarr/templates/partials/security_password.html` (1-4, 10-12) | role-match — per-row/per-section `hx-target` + inline `<p class="text-red-...">` error slot, not a `body` swap |
| `tests/test_web.py` new removal-postcondition test(s) | test | CRUD postcondition assertion | `tests/test_web.py::test_save_settings_propagates_write_failure` (856-883) for *how to force the failure*; `tests/test_web.py::multi_instance_app` fixture (1055-1140) for *what to assert against* | role-match — the force-failure mechanism is exact; the assertion shape must go beyond this analog (see Pitfall D note below) |
| `tests/test_state.py` flipped/new non-dict-root tests | test | file-I/O recovery assertion | `tests/test_state.py::test_state_truncated_json_recovers` (383-392) and `test_state_corrupt_warning_names_reason_without_contents` (440-458) | exact — same assertion shape (default-state contents + log-sink capture, no file contents in the message) |

## Pattern Assignments

### `triggarr/web/routes.py::remove_instance` (938-995) — reorder to build→write→swap

**Analog:** `triggarr/web/routes.py::add_instance` (883-934), same file.

**Imports pattern** (module top, `triggarr/web/routes.py:1-40` — already present, no new imports needed for the reorder itself):
```python
import asyncio
import html
...
import pydantic
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger
```
`shutil` is NOT currently imported in `routes.py` — not needed here (only `state.py` needs it for the set-aside copy).

**Current (outlier) code — mutates live state before the write** (`routes.py:955-987`):
```python
async with request.app.state.search_lock:
    # Remove instance from settings
    del instances[instance_name]                     # <-- live mutation BEFORE write

    config_path = request.app.state.config_path
    config_dict = _settings_to_dict(settings)
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, config_dict
    )                                                   # <-- no try/except at all today

    scheduler = request.app.state.scheduler
    job_id = f"{app_name}_{instance_name}_search"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    clients_dict = getattr(request.app.state, f"{app_name}_clients", {})
    client = clients_dict.pop(instance_name, None)

    triggarr_state = request.app.state.triggarr_state
    if app_name in triggarr_state:
        triggarr_state[app_name].pop(instance_name, None)

    request.app.state.tag_cache.pop((app_name, instance_name), None)

if client:
    await client.close()   # <-- also no try/except (Pitfall C / D-15-D-16)
```

**Target shape — copy from `add_instance`'s already-correct order** (`routes.py:909-934`):
```python
# Build new config dict, add instance, and validate before mutating live state
config_path = request.app.state.config_path
config_dict = _settings_to_dict(settings)
config_dict[app_name][instance_name] = InstanceConfig().model_dump()
config_dict[app_name][instance_name]["api_key"] = ""
config_dict[app_name][instance_name]["id"] = new_instance_id()
try:
    new_settings = SettingsModel(**config_dict)
except pydantic.ValidationError as exc:
    logger.warning("Invalid settings rejected on add_instance: {exc}", exc=exc)
    return HTMLResponse("Validation error: invalid configuration", status_code=400)

async with request.app.state.search_lock:
    # Serialize from validated model to guarantee SecretStr extraction
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    request.app.state.settings = new_settings   # <-- swap only AFTER write succeeds

    triggarr_state = request.app.state.triggarr_state
    triggarr_state.setdefault(app_name, {})
    triggarr_state[app_name][instance_name] = _default_instance_state()
```
Apply the same shape to `remove_instance`: build `updated_instances = dict(instances)` + `del updated_instances[instance_name]` + `settings.model_copy(update={app_name: updated_instances})` **outside** any mutation of the live `instances` dict, write first, and only swap/clean up (scheduler job, client pop, state pop, tag-cache pop) once `_atomic_toml_write` has not raised. On `OSError` from the write, return before touching any live state — settings/scheduler/client/state are provably untouched because nothing above the `try` mutated them (D-02/D-03).

**Error handling pattern to add** (there is currently no `try/except` around `_atomic_toml_write` in this function at all — the closest in-file precedent for *catching* this exact write failure and turning it into a non-crashing response is the general shape already used for `pydantic.ValidationError` in `add_instance` (`routes.py:916-918`); the research's own illustrative diff shows the concrete shape):
```python
try:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
except OSError as exc:
    logger.error(
        "Could not save settings after removing {app}/{inst}: {exc_type}: {exc}",
        app=app_name, inst=instance_name, exc_type=type(exc).__name__, exc=exc,
    )
    return _removal_failed_response(request, app_name, instance_name)
```

**Validation note (Pitfall F):** `add_instance` re-validates through `SettingsModel(**config_dict)`; `remove_instance` today has no such step and deleting a key cannot itself violate any field/count constraint. Re-validating is optional here — if added, it needs its own `pydantic.ValidationError` test (currently-unreachable branch).

---

### `remove_instance` failure response (CONSIST-02, D-04 to D-06) — row-scoped, always-200-for-htmx pattern

**Analog:** `triggarr/web/routes.py::change_password` (1658-1746) + `triggarr/templates/partials/security_password.html`.

**Why this is the right analog, not the HTTP-status approach:** htmx 2.0.8's vendored default (`triggarr/static/js/htmx.min.js`, confirmed string `responseHandling:[{code:"204",swap:false},{code:"[23]..",swap:true},{code:"[45]..",swap:false,error:true}]`) never swaps a 4xx/5xx response body anywhere, regardless of `hx-target`. `change_password` already solves the "show an inline error without a full reload" problem by returning an **implicit 200** whose template content differs on error vs. success:

**Core pattern** (`routes.py:1667-1673`):
```python
if errors:
    return templates.TemplateResponse(
        request=request,
        name="partials/security_password.html",
        context={"errors": errors},
    )   # <-- implicit 200; htmx swaps it into #password-section normally
```

**Template pattern** (`triggarr/templates/partials/security_password.html:1-4, 10-12`):
```html
<form hx-post="{{ request.url_for('change_password') }}"
      hx-target="#password-section"
      hx-swap="innerHTML">
  ...
  {% if errors and errors.current_password %}
  <p class="text-red-500 text-sm mt-1" aria-live="polite">{{ errors.current_password }}</p>
  {% endif %}
```

**Apply to `remove_instance` / `settings.html`:** the Remove button currently has `hx-target="body" hx-swap="outerHTML"` (`settings.html:167`), which only works today because the success path returns `HX-Redirect` (a header that bypasses `hx-target`/`hx-swap` entirely, per the `SEC-01` comment at `routes.py:991-994`). Give the Remove button (or its row) a per-instance target, e.g. an empty `<div id="remove-error-{{ app_name }}-{{ sanitized }}">` inside the row (mirroring the `tags-{{ app_name }}-{{ sanitized }}-missing` id-naming convention already used two lines below at `settings.html:218`), and change `hx-target`/`hx-swap` to point at it with `innerHTML`. On the htmx path, return 200 with a small fragment containing the D-05 wording in the same red-text convention (`text-red-500`/`text-red-400`, matching `security_password.html`'s `text-red-500` and the Remove button's own `text-red-400` class already on `settings.html:166`). On the direct/non-htmx path, the discretion note allows a non-2xx plain-text response (follow the existing not-found convention below).

**Existing escape + plain-error convention to reuse for the instance name** (`routes.py:952-953`, the not-found branch — same function, few lines above the removal logic):
```python
if instance_name not in instances:
    return HTMLResponse(f"Instance '{html.escape(instance_name)}' not found", status_code=400)
```
Reuse `html.escape(instance_name)` exactly like this for the D-05 message's `'<name>'`.

**D-15/D-16 close-failure guard to add (Pitfall C)** — there is no existing in-repo analog that wraps `client.close()` in a try/except (the shutdown-path precedent cited by RESEARCH.md as Pitfall 7 lives in a different function, `create_lifespan`, out of scope here); write it following the same `logger.error(... exc_type=..., exc=...)` shape used above and elsewhere in this file:
```python
if client:
    try:
        await client.close()
    except Exception as exc:
        logger.error(
            "Removed {app}/{inst} but closing its connection failed: {exc_type}: {exc}",
            app=app_name, inst=instance_name, exc_type=type(exc).__name__, exc=exc,
        )
```

**Guard test that MUST be updated alongside the template change (Pitfall E):** `tests/test_web.py::test_no_new_body_swap_html_targets` (1548-1570) currently asserts **exactly one** `hx-target="body"`/`hx-target="html"` exists in all templates and names it as the settings.html Remove button. Once the Remove button's `hx-target` changes away from `body`, this test's count assertion must be updated in the same change (likely to `0`), not merely deleted — its docstring explains the invariant it guards (any future `body`-swap must pair with `HX-Redirect`).

---

### `triggarr/state.py::load_state` (210-245) — non-dict-root guard (CONSIST-03)

**Analog:** same function, existing `except (json.JSONDecodeError, OSError)` branch (`state.py:230-239`) — the guard is a sibling branch, not a new mechanism.

**Current code:**
```python
try:
    with open(resolved_state_path, encoding="utf-8") as f:
        data = json.load(f)
except (json.JSONDecodeError, OSError) as exc:
    logger.warning(
        "Corrupt state file at {path} -- resetting to defaults: {exc}",
        path=resolved_state_path,
        exc=f"{type(exc).__name__}: {exc}",
    )
    return _default_state()

if _is_v22_state_format(data):
    logger.info("Migrating v2.2 state to v2.3 per-instance format")
    data = _migrate_v22_state(data)

return _merge_defaults(data)
```

**Target shape:** add `if not isinstance(data, dict): return _recover_from_bad_state_file(...)` immediately after the `except` block and before `_is_v22_state_format(data)` is called (that function's first line is `data.get(section, {})`, which raises `AttributeError` on a list/int/str/bool/`None` root — this is the exact crash CONSIST-03 targets). D-09 wants **one shared helper** called by both this new branch and the existing `except` block, so both paths get the same set-aside + warning behavior — do not duplicate the logic inline in each branch.

**D-12 already satisfied, no change needed:** `_merge_defaults` (`state.py:171-207`) already guards `isinstance(loaded_section, dict)` at `state.py:181` and `isinstance(instance_data, dict)` at `state.py:184`; `_is_v22_state_format` (`state.py:148-151`) already guards `isinstance(section_data, dict)`. The existing passing test `test_state_wrong_nested_type_recovers` (`tests/test_state.py:423-437`) already proves this — confirmed by reading both, no code change or new test required here.

---

### New set-aside helper in `triggarr/state.py` (D-08, D-09, D-11)

**Analog:** `triggarr/config.py::detect_and_migrate_v22` (372-412), specifically the backup step at 400-402:
```python
# Backup original config
backup_path = config_path.with_suffix(".toml.bak")
shutil.copy2(config_path, backup_path)
```
Tested by `tests/test_config.py::test_detect_and_migrate_v22_creates_backup` (687-696):
```python
def test_detect_and_migrate_v22_creates_backup(tmp_path: Path) -> None:
    """detect_and_migrate_v22 creates backup file triggarr.toml.bak."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)
    detect_and_migrate_v22(config_file)
    backup = config_file.with_suffix(".toml.bak")
    assert backup.exists()
    assert backup.read_text() == V22_RADARR_SONARR_TOML
```

**Gap vs. this phase's needs — do not copy this part verbatim:**
1. **No try/except around the copy today.** `detect_and_migrate_v22`'s `shutil.copy2` call has no error handling at all — if it raises, migration aborts. D-11 explicitly requires the opposite here: "If setting the bad file aside fails ... startup still continues with default state ... Recovery must never be blocked by the copy step." Wrap the new call in its own `try/except OSError` that only logs (`logger.warning`) and falls through to return `_default_state()` regardless.
2. **`.with_suffix(".toml.bak")` is a trap for `state.json` (Pitfall A).** `Path.with_suffix` *replaces* the final suffix rather than appending — `config_path.with_suffix(".toml.bak")` happens to work for `triggarr.toml` only because `.toml.bak`'s leading dot plus the rest reads as a new single suffix replacing `.toml`; applying the same call to `state_path` (`state.json`) would produce `state.bad`-style names that silently drop `.json`. Use `state_path.with_name(state_path.name + ".bad")` (or similar string-append) instead — exact name is Claude's Discretion (87-CONTEXT.md), this is a mechanical gotcha, not a locked requirement.
3. **"Exactly one copy, never accumulating" (D-08) is satisfied by reusing the *same* fixed destination path every time** — `shutil.copy2` naturally overwrites on each call since the destination name never changes; do not borrow `triggarr/db.py::run_migrations`'s timestamped-backup naming (that function solves a different, deliberately-accumulating problem — Pitfall B / this milestone's own Pitfall 9).

**Illustrative call-site shape (from RESEARCH.md, not locked, naming/wording are Claude's Discretion):**
```python
import shutil

def _recover_from_bad_state_file(state_path: Path, reason: str, kind_found: str) -> TriggarrState:
    set_aside_path = state_path.with_name(state_path.name + ".bad")
    try:
        shutil.copy2(state_path, set_aside_path)
    except OSError as exc:
        logger.warning(
            "Could not set aside corrupt state file {path}: {exc}",
            path=state_path, exc=f"{type(exc).__name__}: {exc}",
        )
    logger.warning(
        "State file at {path} held {kind} instead of the expected object -- {reason}. "
        "Queue progress and last-run times were reset to defaults; search history is "
        "unaffected. A copy was set aside at {set_aside} for diagnosis.",
        path=state_path, kind=kind_found, reason=reason, set_aside=set_aside_path,
    )
    return _default_state()
```

**Permissions note (discretion item "at least as restrictive as the state file's"):** `shutil.copy2` preserves the source file's mode bits automatically — no extra `os.chmod` call needed, unlike `_atomic_text_write`'s deliberate pre-chmod pattern (`config.py:200-236`), which exists for a different reason (a brand-new file with no prior permissions to inherit).

---

### Test patterns

**Force-the-write-failure mechanism (reuse exactly):** `tests/test_web.py::test_save_settings_propagates_write_failure` (856-883):
```python
with TestClient(test_app, raise_server_exceptions=False) as tc, \
     patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError("disk full")):
    response = tc.post("/settings", data={...}, follow_redirects=False)
assert response.status_code == 500
```
**Pitfall D — do not stop at this assertion shape.** This existing test only checks `status_code`; it proves nothing about postcondition consistency. The new `remove_instance` regression test(s) must additionally assert, using the `multi_instance_app` fixture's already-exposed mocks (`tests/test_web.py:1055-1140`):
```python
# After patching _atomic_toml_write to raise OSError and POSTing a removal:
assert "4K" in multi_instance_app.state.settings.radarr          # instance still in live settings
mock_scheduler.remove_job.assert_not_called()                     # scheduler job untouched
assert "4K" in multi_instance_app.state.radarr_clients             # client still registered
assert "4K" in multi_instance_app.state.triggarr_state["radarr"]   # state entry untouched
```

**Postcondition fixture already has everything needed** — `multi_instance_app` (`tests/test_web.py:1055-1140`) exposes `mock_scheduler` (`MagicMock`), `radarr_clients`/`sonarr_clients`/`lidarr_clients` (plain dicts with `AsyncMock().close`), `triggarr_state` (plain dict), and `settings` (a real `Settings` instance) — no new fixture machinery required.

**Existing removal tests to extend, not replace:** `test_remove_instance_happy_path` (1478), `test_remove_instance_keeps_other_ids` (1489), `test_remove_instance_nonexistent` (1507), `test_remove_instance_uses_hx_redirect_when_htmx` (1517), `test_remove_instance_uses_303_for_non_htmx` (1535), `test_remove_instance_invalidates_tag_cache` (2834) — all must keep passing unmodified by the reorder (same success-path behavior, only the failure path and the Remove button's `hx-target` change).

**State-recovery test pattern to flip (per its own docstring):** `tests/test_state.py::test_state_wrong_structure_list_crashes` (407-420):
```python
# Before (current):
def test_state_wrong_structure_list_crashes(tmp_path: Path) -> None:
    """...When load_state is hardened to handle non-dict roots, convert this
    test to assert recovery to defaults instead."""
    state_file = tmp_path / "state.json"
    state_file.write_text("[1, 2, 3]")
    with pytest.raises(AttributeError):
        load_state(state_file)
```
Flip to the shape already proven by the sibling recovery test `test_state_truncated_json_recovers` (383-392):
```python
def test_state_wrong_structure_list_recovers(tmp_path: Path) -> None:
    """Valid JSON list (not dict) recovers to defaults instead of crashing (CONSIST-03)."""
    state_file = tmp_path / "state.json"
    state_file.write_text("[1, 2, 3]")
    state = load_state(state_file)
    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []
```
Add parallel `42`/`null` siblings (locked by CONSIST-03's wording); a string/boolean root sibling is Claude's Discretion.

**No-contents warning-assertion pattern to reuse for the new non-dict-root warning:** `tests/test_state.py::test_state_corrupt_warning_names_reason_without_contents` (440-458) — captures a `logger.add(sink, ...)` handler, asserts the exception type and a "line N" detail appear, and asserts a content sentinel string does **not** appear. Apply the identical `io.StringIO()` + `logger.add`/`logger.remove` pattern to assert the new warning names the file path and "a non-object JSON root"/kind-found without ever echoing a value from the bad JSON.

**Set-aside-copy backup-overwrite test to write new (no direct existing analog — nearest precedent is the TOML-side creates-backup test above):** simulate two separate corrupt-state-file loads and assert exactly one `.bad`-named file exists afterward with the *second* occurrence's contents (D-08/Pitfall B), mirroring `test_detect_and_migrate_v22_creates_backup`'s `assert backup.exists(); assert backup.read_text() == ...` shape but called twice.

## Shared Patterns

### Validate-before-mutate settings write (applies to the `remove_instance` reorder)
**Source:** `triggarr/web/routes.py::add_instance` (909-934), confirmed as the dominant convention across every other settings-writing route in the file (`save_settings:717-731`, `setup_post:1450-1454`, `change_password:1715-1719`, `save_security:1764-1768`, `regenerate_api_key_endpoint:1788-1792`, password-reset confirm `~2117-2121`).
**Apply to:** `remove_instance` only — it is the sole confirmed outlier (D-13 audit, performed in RESEARCH.md, found nothing else unsafe).
```python
# build replacement via model_copy/fresh dict (no live mutation yet)
# -> write to disk inside try/except OSError
# -> only on success: swap request.app.state.settings and run cleanup
```

### Atomic file write (already correct, reused unchanged)
**Source:** `triggarr/config.py::_atomic_toml_write` (129-170+) and `_settings_to_dict` (63-87).
**Apply to:** no change needed — `remove_instance` already calls `_atomic_toml_write`; the fix is purely about *when* live state is mutated relative to this call, not the write mechanism itself.

### Set-aside/backup-before-overwrite (new usage of an existing idiom)
**Source:** `triggarr/config.py::detect_and_migrate_v22` (400-402), `shutil.copy2` to one fixed-name sibling path.
**Apply to:** the new `state.py` recovery helper — reuse the stdlib call, but add the try/except the TOML-side precedent lacks (D-11) and avoid `with_suffix` (Pitfall A).

### Never log/echo raw file contents or internal error detail
**Source:** `triggarr/state.py::load_state`'s existing comment and practice (`state.py:230-238`: "never touching `exc.doc`, which holds the raw file contents") and `tests/test_state.py::test_state_corrupt_warning_names_reason_without_contents` (440-458).
**Apply to:** both the D-07 removal-failure log line and the D-10 state-file warning — name `type(exc).__name__`/`str(exc)` (sanitized reason), never a raw file's parsed content, matching the project CLAUDE.md rule ("generic message out, details logged server-side").

### `html.escape` on any user-supplied name in response HTML
**Source:** `triggarr/web/routes.py:953` (not-found branch, same function) and `:883` region (`add_instance`'s duplicate-name branch, `routes.py:908`: `f"Instance '{html.escape(instance_name)}' already exists"`).
**Apply to:** the new D-05 failed-removal message's `'<name>'` substitution — same call, same quoting convention.

### Always-200-for-htmx, differentiate by content (row/section-scoped errors)
**Source:** `triggarr/web/routes.py::change_password` (1667-1673) + `triggarr/templates/partials/security_password.html`.
**Apply to:** the new `remove_instance` failure response on the htmx path; `settings.html`'s Remove button `hx-target`/`hx-swap` must move off `body` to a per-row scope first (paired template change — see Pitfall E test above).

### Redacting log sink — no per-call-site work needed
**Source:** `triggarr/logging.py::create_redacting_sink` — redacts every configured secret value from the complete formatted output automatically.
**Apply to:** both new log lines (D-07 removal-failure error, D-16 close-failure error, D-10 state-file warning) — use `logger.error`/`logger.warning` normally; no secret value is named in any of the three new log lines in the first place, so this is satisfied by default.

## No Analog Found

None. RESEARCH.md's own "Key insight" (confirmed by this mapping) holds: every file this phase touches already has a correct, shipped sibling pattern somewhere in `triggarr/` — the work is bringing one outlier (`remove_instance`) and one narrow gap (`load_state`'s non-dict-root case) in line with conventions that already exist, not introducing a new pattern.

## Conventions

Derived via the shared deterministic tool (`gsd-tools.cjs verify conventions --derive --scope triggarr`), run this session:

| Axis | Dominant | Share | Entropy | Status |
|------|----------|-------|---------|--------|
| File-name casing | `camel`-bucketed* | 77.4% (24/31) | 0.609 | named contract |
| Identifier casing | none (split camel/Pascal/CONSTANT) | 43.2% (95/220) | 0.784 | contested hotspot |
| Export style | — | — (0 samples) | — | insufficient-data |
| Import style | — | — (0 samples) | — | insufficient-data |

\* The tool's generic "camel" bucket has no snake_case category; single-token Python module names (e.g. `routes.py`, `config.py`) land there by elimination. Read directly against the source: this project is 100% `snake_case.py` filenames in practice — the project's own two Python-specific axes the tool also reported confirm the codebase's real discipline: `py-wildcard-import` is 100% `explicit` (28/28, no `from x import *`) and `py-import-relativity` is 100% `absolute` (28/28, no relative `from .x import y`), both "named contract" at full consensus.

Export-style/import-style are JS/TS-oriented axes with zero applicable samples in a pure-Python repo (`insufficient-data`, not contested) — ignore them here; the two Python-specific axes above are the ones that matter for this phase's files.

**Contested hotspots (author's choice):** The tool's "identifier-casing" axis reports a 3-way split (camelCase/PascalCase/CONSTANT) with no single dominant style, mirroring the canonical example of a legitimate contested-but-not-inconsistent split: this project's bm tooling repo's own `bin/lib/**` (CJS `module.exports`/`require`) vs. `sdk/src/**` (ESM `export`/`import`) dual resolver — each half is internally consistent per-directory, contested only when aggregated repo-wide. The same shape applies here: Python's own per-role convention (snake_case for functions/variables, PascalCase for classes, UPPER_CASE for module-level constants) is each individually 100% consistent; the aggregate tool only sees "contested" because it counts across roles rather than within one. For this phase's actual edits (route functions, a module-level helper function, test functions), the correct local style is plain `snake_case` — confirmed directly by every analog read above (`remove_instance`, `add_instance`, `load_state`, `_atomic_toml_write`, `_merge_defaults`, every test function name). No new class is introduced by this phase, so PascalCase does not apply to any new identifier here.

## Metadata

**Analog search scope:** `triggarr/web/routes.py`, `triggarr/state.py`, `triggarr/config.py`, `triggarr/templates/settings.html`, `triggarr/templates/partials/security_password.html`, `triggarr/search/scheduler.py`, `tests/test_web.py`, `tests/test_state.py`, `tests/test_config.py`
**Files scanned:** 9 read directly this session (plus the convention-derivation tool's repo-wide scan of `triggarr/`)
**Pattern extraction date:** 2026-11-15
