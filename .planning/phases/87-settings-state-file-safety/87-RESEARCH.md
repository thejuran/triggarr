# Phase 87: Settings & State-File Safety - Research

**Researched:** 2026-11-15
**Domain:** Reorder-and-guard hardening of two existing code paths in a shipped FastAPI/Pydantic/loguru daemon (Triggarr v2.12.1) — no new library, no new architecture
**Confidence:** HIGH

## Summary

Both fixes in this phase are narrow, already-precedented corrections to code that exists today, confirmed by reading `triggarr/web/routes.py` and `triggarr/state.py` directly (not inferred from the phase description). `remove_instance` is the one settings-mutating route in `routes.py` that deletes from the live in-memory `settings.<app>` dict **before** attempting the disk write; every other settings-writing route (`save_settings`, `add_instance`, `setup_post`, `change_password`, `save_security`, `regenerate_api_key_endpoint`, the password-reset confirm handler) already builds the replacement config via `model_copy`/a fresh dict, writes it to disk, and only swaps `request.app.state.settings` (plus runs scheduler/client/state cleanup) after the write succeeds. The fix is to make `remove_instance` match that existing convention — no new mechanism. Separately, `load_state` catches `(json.JSONDecodeError, OSError)` but calls `.get()` on the parsed JSON before checking its type, so a syntactically valid but non-object root (`[]`, `42`, `null`) raises an uncaught `AttributeError` and crashes startup; this is already self-documented as a known, intentionally-deferred gap in `tests/test_state.py` (`test_state_wrong_structure_list_crashes`'s own docstring says to flip the assertion once fixed). The fix is one `isinstance(data, dict)` guard before that `.get()` call, reusing the existing corrupt-JSON recovery path's shape (log a warning, return `_default_state()`).

The user's locked decisions (87-CONTEXT.md) add two requirements beyond the milestone research's own framing: (1) a user-visible, row-scoped error message on a failed removal, which the current htmx wiring cannot deliver without a template/target change — the Remove button's `hx-target="body"` and htmx 2.0.8's own default config (verified directly from the vendored `htmx.min.js`) mean a non-2xx response is silently discarded, not swapped; and (2) a "set aside the bad file, exactly one copy, never blocks recovery" treatment for both the new wrong-shape crash and the existing truncated/unparseable crash, which has no existing analog in `state.py` but a directly reusable sibling pattern in `config.py` (`detect_and_migrate_v22`'s single fixed-name `.toml.bak` copy via `shutil.copy2`) — explicitly **not** the timestamped, ever-accumulating backup style used by `db.py::run_migrations` for a different purpose (that one is this milestone's Pitfall 9, a problem the owner's "exactly one copy" wording for this phase specifically avoids repeating).

**Primary recommendation:** Reorder `remove_instance` to validate/write/swap exactly like `add_instance`; add one `isinstance(data, dict)` guard in `load_state` before the first `.get()` call, routed through a shared "reset to defaults, log, set the bad file aside" helper that both the existing `except (JSONDecodeError, OSError)` block and the new non-dict-root branch call; and change the Remove button's htmx wiring from `hx-target="body"` to a per-row target so a failure response can render inline without disturbing unsaved edits elsewhere on the page (this also requires updating the one existing guard test, `test_no_new_body_swap_html_targets`, that currently asserts exactly one `hx-target="body"` usage exists and names the Remove button as that usage).

## Architectural Responsibility Map

Triggarr is a single-process app; there is no client/server tier split for this phase. Both fixes live entirely in the backend/API tier.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Instance-removal settings write ordering | API / Backend (`triggarr/web/routes.py`) | — | Route handler owns validate→write→swap→cleanup; no browser or DB tier involvement |
| Row-scoped failure message rendering | Frontend Server (SSR via Jinja2 + htmx) | Browser (htmx swap target) | Server renders the error fragment; the browser's htmx runtime decides whether/where to swap it based on response status and `hx-target` |
| State-file corruption recovery (non-dict root) | API / Backend (`triggarr/state.py`) | — | Pure file-load logic invoked once at startup (`search/scheduler.py::create_lifespan`); no UI surface |
| Set-aside copy of the bad state file | Database / Storage (local filesystem) | API / Backend | The copy is a storage-layer side effect of the backend's load path; no network or browser involvement |

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONSIST-01 | When removing an instance fails to save, the user still sees the instance, and its settings, schedule and connection keep working as before the attempt | Pitfall 4 / Architecture §1a below: exact current code, exact reorder shown in Code Examples; test fixture (`multi_instance_app`) already exposes `scheduler`/`*_clients`/`triggarr_state` for postcondition assertions |
| CONSIST-02 | When removing an instance fails to save, the user sees an error that says the instance was not removed, with no internal details | Architecture Patterns §"Row-scoped failure message" below: htmx 2.0.8's verified default `responseHandling`, the existing `change_password`/`save_security` "always 200, template differentiates" precedent, and the `test_no_new_body_swap_html_targets` guard test that must be updated alongside the template change |
| CONSIST-03 | When the saved state file holds valid JSON that is not an object, Triggarr starts with default state and logs a warning instead of crashing | Pitfall 5 / Architecture §1b below: exact current code, exact guard shown in Code Examples; `test_state_wrong_structure_list_crashes`'s own docstring already specifies the required post-fix assertion |

## Project Constraints (from CLAUDE.md)

Both the user's global `~/.claude/CLAUDE.md` and the project's `./CLAUDE.md` apply. Directives relevant to this phase:

- **SecretStr discipline:** not touched by either fix — no API key or credential handling is involved in `remove_instance` or `load_state`.
- **Loguru with the custom redacting sink, never print/logging module:** both new log lines (the removal-failure error log and the state-file warning) must use `logger.error`/`logger.warning`. No special redaction code is needed at the call site — `create_redacting_sink` (`triggarr/logging.py`) redacts any configured secret value from the complete formatted output, including tracebacks, automatically. Neither new log line names a secret, so this is satisfied by using `logger.*` normally.
- **Atomic file writes (write-then-rename) for config and state:** `_atomic_toml_write` (unchanged by this phase) already provides this for the removal fix. The new "set aside the bad state file" step should use `shutil.copy2` (matching `config.py::detect_and_migrate_v22`'s precedent for an adjacent backup copy) — this is a copy of an already-on-disk file, not a write of new data, so the write-then-rename discipline does not apply to it directly, but the copy must not corrupt or block the already-atomic `_default_state()` recovery path (D-11).
- **Never log sensitive data; never expose stack traces or internal error details to end users:** directly governs CONSIST-02 (D-05's fixed wording has no file paths, no system error text, no exception names) and the state-file warning (D-10: never echoes file contents, matching the existing `test_state_corrupt_warning_names_reason_without_contents` convention).
- **Guard nullable returns before property access; ensure resources are released on every path:** relevant to the `await client.close()` call in `remove_instance`, which currently has no `try/except` — see Pitfall C below (D-15/D-16).
- **Don't swallow exceptions silently — log at minimum; try/except around external calls only where this code is the intended error boundary:** `remove_instance`'s disk write is exactly this kind of boundary (the route is where "settings write failed" must turn into a user-facing message, not propagate as a bare 500) — currently it has no try/except around `_atomic_toml_write` at all; the fix must add one.
- **Precedence: Security rules absolute; everything else defers to existing codebase conventions.** This phase has no security-rule implications (no SQL, no subprocess, no `innerHTML`/`dangerouslySetInnerHTML` of user content, no hardcoded secrets) — the only user-supplied value touched is the instance name, which must stay `html.escape`d exactly as the existing not-found branch already does.
- **Review workflow (project CLAUDE.md):** one PR per phase; BM code-review + paired Codex pass after all of this phase's plans finish, not per-plan; offer `/deep-review` before any push to main or release tag (not expected to trigger mid-phase, but applies at phase-PR time per the project's documented workflow).
- **Planning file format:** `.planning/STATE.md`/`ROADMAP.md`/`REQUIREMENTS.md` edits must follow `docs/PLANNING-FORMAT.md` (already loaded; applies to the planner, not to this research file).

No project-skill files were found under `.claude/skills/` or `.agents/skills/` beyond the unrelated `aidesigner-frontend` skill, which does not apply to this phase.

## Standard Stack

No new dependency — runtime or dev. Both fixes reorder/guard existing code using only the Python standard library and libraries already pinned in `uv.lock`.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`shutil`, `pathlib`, `json`, `os`) | 3.13 (project target) | `shutil.copy2` for the set-aside copy; `isinstance`/`json.load` for the non-dict-root guard | Already used identically elsewhere in this codebase (`config.py::detect_and_migrate_v22`'s `shutil.copy2`, `state.py`'s existing `json.load`/`isinstance` checks in `_merge_defaults`) `[VERIFIED: read directly from triggarr/config.py and triggarr/state.py]` |
| pydantic | pinned in `uv.lock` (already installed; not re-verified this session — no behavior change needed) | `Settings.model_copy(update=...)` for the validate-before-mutate reorder | `Settings`/`InstanceConfig` have no `validate_assignment=True` in `model_config` (confirmed: `triggarr/models/config.py:194-196`), so `model_copy(update=...)` does not re-run validation — matches the exact mechanism `change_password`/`setup_post`/`save_security` already use `[VERIFIED: read directly from triggarr/models/config.py]` |
| loguru | pinned in `uv.lock` | `logger.warning`/`logger.error` for both new log lines, through the existing redacting sink | Already the project's sole logging mechanism (CLAUDE.md mandate) `[VERIFIED: read directly from triggarr/logging.py]` |
| htmx (vendored, `triggarr/static/js/htmx.min.js`) | **2.0.8** | Client-side swap behavior for the row-scoped failure message | Version string read directly from the vendored minified file (`version:"2.0.8"`); this is the exact version shipping in production, not a training-data guess `[VERIFIED: read directly from triggarr/static/js/htmx.min.js]` |

### Supporting
No supporting libraries are introduced. `html.escape` (stdlib) continues to be the only sanitization needed for the instance name in any new response text, matching the existing not-found-instance branch.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| One shared "reset state to defaults + log + set aside" helper in `state.py` | Separate inline handling in each of the two call sites (`except (JSONDecodeError, OSError)` and the new `isinstance` branch) | Research recommends the shared helper (D-09 explicitly wants "one recovery behavior to understand and test"); duplicating it risks the two paths drifting (e.g. one gets the set-aside copy, the other doesn't) |
| `shutil.copy2` for the set-aside file | `Path.replace`/move instead of copy | D-10's warning implies the original corrupt file's existence/shape still needs to be inspectable for diagnosis while `_default_state()` is written fresh to the *original* path — a copy (leaving the original in place to be overwritten by the next `save_state`) matches `config.py`'s `.toml.bak` precedent; a move would leave no file at the original path until the next save, which is unnecessary extra behavior change not asked for |
| Global htmx `responseHandling` override to make 4xx responses swap by default | Returning 200 for the htmx failure path (matching `change_password`/`save_security`) | See Architecture Patterns below — the 200-with-differentiated-content approach has a direct, already-shipped precedent in this exact codebase; a global config override would change behavior for every other htmx call on the page, a much larger blast radius for no added benefit |

**Installation:** None — no new packages.

**Version verification:** Not applicable (no new packages). The one version claim made above (htmx 2.0.8) was confirmed by reading the vendored file directly, not via a registry lookup.

## Package Legitimacy Audit

Not applicable — this phase installs no external packages (project-wide standing rule: "No new runtime dependency," confirmed unviolated by both fixes). The Package Legitimacy Gate protocol was not run because there is nothing for it to check.

## Architecture Patterns

### System Architecture Diagram

```
Browser (settings.html)
   │  POST /api/instance/remove/{app}/{instance}   (htmx: hx-post, HX-Request header)
   ▼
FastAPI route: remove_instance()  [triggarr/web/routes.py]
   │
   ├─ 1. Build replacement config WITHOUT touching live settings
   │      (copy settings.<app> dict, del the key, settings.model_copy(update=...))
   │
   ├─ 2. Serialize + write to disk  ──────────────► _atomic_toml_write()  [triggarr/config.py]
   │        │                                            │
   │        │                                     success│        │failure (OSError)
   │        ▼                                            ▼        ▼
   │   write succeeded                          swap live settings   RAISE caught here:
   │        │                                   + scheduler.remove_job   log (D-07),
   │        │                                   + pop client/state/      return row-scoped
   │        │                                     tag_cache              error (D-05/D-06),
   │        │                                                            settings/job/client
   │        ▼                                                            /state UNCHANGED
   │   close removed client (outside lock) ── try/except (D-15/D-16):
   │        on close() failure: log, still return normal success
   │
   ▼
Response:
  - success + htmx  → HX-Redirect (full nav; existing SEC-01 CSP-nonce mechanism, unchanged)
  - success + plain → 303 (unchanged)
  - failure + htmx  → 200 + row-scoped HTML fragment (new hx-target, per D-04)
  - failure + plain → non-2xx + plain wording (per discretion note)


Startup path (separate, no HTTP involved):
FastAPI lifespan → create_lifespan()  [triggarr/search/scheduler.py:481]
   │
   ▼
load_state(state_path)  [triggarr/state.py]
   │
   ├─ file missing            → _default_state()
   ├─ JSONDecodeError/OSError → set bad file aside (D-08/D-09/D-11) → warn (D-10) → _default_state()
   ├─ valid JSON, NOT a dict  → same shared path as above (NEW guard)
   ├─ valid JSON, IS a dict   → _is_v22_state_format / _merge_defaults (unchanged;
   │                             already recovers from wrong-shaped-but-dict content, D-12)
   ▼
TriggarrState returned to create_lifespan, used as today
```

### Recommended Project Structure

No new files or directories. Both fixes stay inside their existing modules:
```
triggarr/
├── web/routes.py     # remove_instance() reordered; response building changed
├── state.py           # load_state() gains isinstance(data, dict) guard + shared
│                       #   "reset to defaults" helper used by both corrupt-input paths
└── templates/
    └── settings.html  # Remove button's hx-target changed from "body" to a per-row scope;
                        #   a new empty error-slot element added inside each instance row
tests/
├── test_web.py        # extend remove_instance coverage (postcondition asserts, not just status)
└── test_state.py       # flip test_state_wrong_structure_list_crashes; add 42/null/string-root
                        #   siblings; add set-aside-copy and warning-content tests
```

### Pattern 1: Validate → write → swap → cleanup (the convention `remove_instance` must adopt)

**What:** Build the replacement state from a copy, persist it, and only mutate live in-memory state once the persist step has provably succeeded.
**When to use:** Any route that changes `request.app.state.settings`.
**Example (read directly from the current codebase — this is `add_instance`'s existing, already-correct shape, `triggarr/web/routes.py:909-927`):**
```python
# Source: triggarr/web/routes.py (add_instance, current shipped code)
config_dict = _settings_to_dict(settings)
config_dict[app_name][instance_name] = InstanceConfig().model_dump()
...
try:
    new_settings = SettingsModel(**config_dict)
except pydantic.ValidationError as exc:
    ...
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    request.app.state.settings = new_settings   # only reached if the write didn't raise
    ...
```
**The fix applies this same shape to `remove_instance` (see Code Examples below for the exact diff-shape).**

### Pattern 2: Error partial rendered at 200, swapped into a scoped target (the convention for the row-scoped message)

**What:** Return the normal 200 status with a small HTML fragment whose *content* differentiates success from failure, rather than relying on the HTTP status code to signal state — because htmx's default config does not swap non-2xx/3xx responses.
**When to use:** Any htmx-driven form/button that must show an inline error without a full page reload.
**Already-shipped example in this exact codebase (`triggarr/web/routes.py:1657-1680`, `change_password`):**
```python
# Source: triggarr/web/routes.py (change_password, current shipped code)
if errors:
    return templates.TemplateResponse(
        request=request,
        name="partials/security_password.html",
        context={"errors": errors},
    )   # <-- implicit 200; htmx swaps it into #password-section normally
```
```html
<!-- Source: triggarr/templates/partials/security_password.html -->
<form hx-post="{{ request.url_for('change_password') }}"
      hx-target="#password-section"
      hx-swap="innerHTML">
  ...
  {% if errors and errors.current_password %}
  <p class="text-red-500 text-sm mt-1" aria-live="polite">{{ errors.current_password }}</p>
  {% endif %}
```
**Why this matters here:** `remove_instance`'s Remove button currently has `hx-target="body" hx-swap="outerHTML"` (`settings.html:167`), which only works today because the success path uses `HX-Redirect` (a header that makes htmx skip `hx-target`/`hx-swap` entirely and force a full browser navigation — see SEC-01's own comment at `routes.py:991-994`). A failure response cannot reuse `hx-target="body"`: swapping the whole `<body>` on an error would satisfy neither D-04 ("Unsaved edits elsewhere on the Settings page must survive a failed removal") nor correctness (the response for a failure is a short message, not a full settings page). The Remove button's `hx-target`/`hx-swap` need a per-row scope (e.g. a dedicated empty `<div id="remove-error-{{ app_name }}-{{ sanitized }}">` placed inside each instance row, targeted with `hx-swap="innerHTML"`) so a failure only ever touches that one small element.

**Verified fact that makes this non-optional:** htmx 2.0.8's default `responseHandling` config, read directly from the vendored `triggarr/static/js/htmx.min.js`:
```
responseHandling:[{code:"204",swap:false},{code:"[23]..",swap:true},{code:"[45]..",swap:false,error:true}]
```
Any 4xx/5xx response is explicitly `swap:false` — htmx will fire an `htmx:responseError` event (which nothing in this codebase currently listens for) and **will not** insert the response body anywhere, regardless of `hx-target`. A naive "just return 400 with the D-05 text" implementation will work correctly for a direct/non-htmx POST (discretion note already anticipates this: "a non-2xx response carrying the same plain wording" for that path) but will show **nothing** to a normal browser user clicking the Remove button, silently failing D-04. The two response shapes (htmx vs. non-htmx) need to differ in status code for exactly this reason — this is not a stylistic choice, it is required by htmx's own shipped default behavior.

### Pattern 3: Shared "reset to defaults" recovery path with set-aside, used by both corrupt-input branches in `load_state`

**What:** One helper that both the existing `except (JSONDecodeError, OSError)` block and the new "valid JSON but not a dict" branch call, so the behavior (log, set the bad file aside, return defaults) is defined once (D-09: "One recovery behavior to understand and test").
**Example shape (new code, following the existing `config.py::detect_and_migrate_v22` precedent for the set-aside copy and the existing `load_state` warning-logging convention):**
```python
# Illustrative shape, following existing conventions in this codebase -- not a locked
# implementation; naming and exact warning wording are Claude's Discretion per 87-CONTEXT.md.
import shutil

def _recover_from_bad_state_file(
    state_path: Path, reason: str, kind_found: str
) -> TriggarrState:
    """Set the bad state file aside (best-effort), warn, and return defaults.

    Mirrors config.py::detect_and_migrate_v22's shutil.copy2 set-aside pattern --
    ONE fixed destination name, overwritten on each occurrence (D-08), NOT the
    timestamped-accumulating style db.py::run_migrations uses for a different
    purpose (never apply that pattern here -- see Pitfall B below).
    """
    set_aside_path = state_path.with_name(state_path.name + ".bad")  # see Pitfall A
    try:
        shutil.copy2(state_path, set_aside_path)
    except OSError as exc:
        # D-11: the copy step must never block recovery.
        logger.warning(
            "Could not set aside corrupt state file {path}: {exc}",
            path=state_path, exc=f"{type(exc).__name__}: {exc}",
        )
    logger.warning(
        "State file at {path} held {kind} instead of the expected object -- "
        "{reason}. Queue progress and last-run times were reset to defaults; "
        "search history is unaffected. A copy was set aside at {set_aside} for diagnosis.",
        path=state_path, kind=kind_found, reason=reason, set_aside=set_aside_path,
    )
    return _default_state()
```
```python
# load_state's two call sites both route through the helper:
try:
    with open(resolved_state_path, encoding="utf-8") as f:
        data = json.load(f)
except (json.JSONDecodeError, OSError) as exc:
    return _recover_from_bad_state_file(
        resolved_state_path, f"{type(exc).__name__}: {exc}", "unparseable content"
    )

if not isinstance(data, dict):
    return _recover_from_bad_state_file(
        resolved_state_path, "a non-object JSON root", type(data).__name__
    )
```

### Anti-Patterns to Avoid
- **Guarding `isinstance` deep inside `_is_v22_state_format`/`_merge_defaults` instead of once at `load_state`'s entry point.** `_merge_defaults` already has its own (necessary, unrelated) `isinstance(loaded_section, dict)` guard per app-key — that guard exists *because* its caller already guarantees the top-level `loaded` is a dict. Adding a second, redundant guard deeper in the call stack instead of fixing the actual contract at the entry point is explicitly called out as a warning sign in the milestone's PITFALLS.md (Pitfall 5).
- **Reusing `db.py::run_migrations`'s timestamped, never-deleted backup naming for the state-file set-aside.** That pattern exists to solve a different problem (preserve every attempt's backup across a crash loop) and is itself the subject of this milestone's Pitfall 9 (unbounded accumulation) — the opposite of what D-08 asks for here ("exactly one set-aside copy... so it can never accumulate").
- **Checking `error:true`/status-code branching instead of content for the htmx failure path.** Don't try to make htmx swap a 4xx response by overriding `htmx.config.responseHandling` globally — it is unused anywhere else in this codebase today and a global override changes behavior for every other htmx-driven element on every page, including ones that correctly rely on 4xx-not-swapping today (e.g. `tag_autocomplete`'s malformed-tag-list responses, `search_now`'s 429 rate-limit response).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Validating a settings mutation before committing it live | A custom "try the mutation, roll back on failure" wrapper | `Settings.model_copy(update={...})` on a freshly-built dict, exactly as `add_instance`/`change_password`/`save_security` already do | `model_copy` already gives an immutable-looking swap with zero risk of partially-mutated shared state; four other routes already prove this works for this exact `Settings` model |
| Detecting/recovering from a malformed state file | A new validation/schema library (e.g. `jsonschema`) | One `isinstance(data, dict)` check, reusing the existing `_default_state()`/warning-log convention | The only failure mode in scope is "root is not an object" — a full schema validator would be solving a problem this phase doesn't have, and the existing `_merge_defaults` already handles deeper malformed shapes gracefully (D-12) |
| Preserving a corrupted file for diagnosis | A custom backup-rotation mechanism | `shutil.copy2` to one fixed path, matching `config.py::detect_and_migrate_v22`'s `.toml.bak` precedent | stdlib `shutil.copy2` already preserves mode bits (so the set-aside file naturally inherits the original's permissions, satisfying the "at least as restrictive" discretion note) and is already a proven pattern in this codebase for exactly this purpose |

**Key insight:** every piece of this phase already has a correct, shipped sibling implementation somewhere else in `triggarr/`. The work is "make the one outlier match," not "design something new."

## Common Pitfalls

### Pitfall A: `Path.with_suffix()` replaces the extension; it does not append one
**What goes wrong:** `Path("state.json").with_suffix(".bad")` produces `Path("state.bad")`, not `state.json.bad` — the suffix is *replaced*, not appended. `db.py::run_migrations` deliberately relies on this behavior for its own (different) naming scheme (`db_path.with_suffix(f".v{current}-backup")`, replacing `.db`), which can make it look like the "normal" way to derive a sibling path in this codebase.
**Why it happens:** `with_suffix` reads as "add a suffix" in plain English but means "set the (single, final) suffix" in `pathlib`.
**How to avoid:** Use `state_path.with_name(state_path.name + ".bad")` (or similar string-append) if the set-aside file should still be recognizably related to `state.json` by name. Exact naming is Claude's Discretion per 87-CONTEXT.md — this is a mechanical gotcha to watch for, not a locked requirement.
**Warning signs:** A diff that copies `db_path.with_suffix(...)`'s shape verbatim for `state_path` and produces a set-aside filename that silently drops `.json` from the name.

### Pitfall B: Borrowing `db.py`'s accumulating-backup shape for a "keep exactly one" requirement
**What goes wrong:** `db.py::run_migrations` writes a new, uniquely-timestamped backup file on every failed-migration retry and never deletes any of them (this is itself Pitfall 9 in the milestone-level research, addressed in Phase 88, not here). If the set-aside logic for `state.json` is modeled after that function instead of `config.py::detect_and_migrate_v22`'s single fixed-name copy, D-08's "exactly one set-aside copy... so it can never accumulate" is violated on the very first repeat occurrence.
**How to avoid:** Always write to the *same* set-aside path; let the second `shutil.copy2` call overwrite the first. No timestamp in the filename.
**Test that catches it:** Simulate two separate corrupt-state-file occurrences (e.g. reload after a second corruption) and assert exactly one set-aside file exists on disk afterward, with contents matching the *second* corruption, not the first.

### Pitfall C: The final `await client.close()` in `remove_instance` has no `try/except` today — and D-15/D-16 require one
**What goes wrong:** After the reorder fix, every in-memory cleanup step (scheduler job removal, client-dict pop, state-dict pop, tag-cache pop) happens *before* the single remaining call that can still fail: `await client.close()` outside the lock (`routes.py:985-987`, unchanged by the reorder). Today this call has **no** `try/except`. The milestone's own resource-lifecycle research (Pitfall 7, cited for Phase 89's shutdown loop, not this phase) already proves `ArrClient.close()`/`httpx.AsyncClient.aclose()` can raise something other than a quiet no-op when a request is in flight at close time (`tests/test_clients.py`'s TEST-04). In `remove_instance`'s *current* code, since all the dict/scheduler cleanup already ran before this line, a raised exception here would propagate out of the route as an unhandled error **after** the removal already fully succeeded in memory and on disk — directly contradicting D-15 ("the user still sees the normal successful removal and nothing extra is shown").
**Why it happens:** The function was written assuming `close()` "can't really fail" in the graceful case — the same assumption Pitfall 7 already disproves for the shutdown path elsewhere in this codebase.
**How to avoid:** Wrap the final `await client.close()` in `try/except Exception: logger.error(...); ` (do not re-raise) so a close failure is logged (D-16, redacted automatically by the existing sink) but never changes the response the user sees. This is in scope for *this* phase per D-15/D-16 in 87-CONTEXT.md — it is not the same thing as Phase 89's startup/shutdown lifespan cleanup, which is a different function (`create_lifespan`) entirely.
**Test that catches it:** Make the removed instance's client's `.close()` raise (e.g. `AsyncMock(side_effect=RuntimeError("boom"))` on the fixture's existing client mocks) and assert the response is still the normal success response (`HX-Redirect`/303, unchanged), with the exception only visible via a captured log line.

### Pitfall D: Testing only the HTTP status code, not the postcondition (already the existing weaker precedent)
**What goes wrong:** `test_save_settings_propagates_write_failure` (the one existing negative test for any settings-writing route, `tests/test_web.py:856-883`) asserts only `response.status_code == 500` — it never checks whether settings/scheduler/client state stayed consistent after the failure. Copying that test's shape for `remove_instance` would prove the route doesn't crash the test harness, but not prove CONSIST-01 (the actual postcondition: instance still in settings, scheduler job still present, client still registered).
**How to avoid:** The new regression test(s) must assert, after patching `_atomic_toml_write` to raise `OSError`: the instance is still present in `multi_instance_app.state.settings.<app>`; `mock_scheduler.remove_job` was **not** called; the instance's entry is still present in `multi_instance_app.state.<app>_clients`; the instance's entry is still present in `multi_instance_app.state.triggarr_state[<app>]`. The existing `multi_instance_app` fixture (`tests/test_web.py:1054-1140`) already exposes every one of these as a `MagicMock`/plain dict, so no new fixture machinery is needed.
**Test that catches it:** The new test itself — this is the thing to write, not a pre-existing gap to merely document.

### Pitfall E: Forgetting to update `test_no_new_body_swap_html_targets` when the Remove button's `hx-target` changes
**What goes wrong:** This existing guard test (`tests/test_web.py:1548-1570`) asserts **exactly one** `hx-target="body"`/`hx-target="html"` occurrence exists in all of `triggarr/templates/`, and that it is the settings.html Remove button — explicitly justified by that button's paired `HX-Redirect` response. If the Remove button's `hx-target` is changed (required by Pattern 2 above, to satisfy D-04), this test will either start failing (if the count check still requires exactly one and finds zero) or — worse — silently stop testing anything meaningful if its assertion is loosened without replacing what it was actually guarding (the "any future body-swap must be paired with `HX-Redirect`" invariant named in its own docstring).
**How to avoid:** Update this test's assertion (and docstring) in the same change that updates the template, to reflect the new expected count (likely zero, if nothing else in the codebase uses `hx-target="body"`) — do not just delete or skip it.
**Test that catches it:** Running the existing test suite after the template change — this test will fail immediately and loudly if missed, which is the intended behavior; it's a pitfall only if the failure is "fixed" by weakening the assertion rather than understanding why it existed.

### Pitfall F: `remove_instance` currently skips `add_instance`'s re-validation step
**What goes wrong:** `add_instance` re-validates the whole config through `SettingsModel(**config_dict)` before writing; `remove_instance`'s current code builds `config_dict = _settings_to_dict(settings)` directly with no `SettingsModel(...)` re-validation step at all (confirmed: `routes.py:962`, no `try/except pydantic.ValidationError` anywhere in the function). Removing an instance cannot itself produce invalid data (deleting a dict key can't violate `Settings.validate_instances`'s "max 5 instances" rule or any per-instance field constraint), so skipping re-validation is not a correctness bug — but a fix that *adds* re-validation "to match the pattern" needs to handle the (currently unreachable, now newly-reachable) `pydantic.ValidationError` branch, or it introduces a new, untested failure path.
**How to avoid:** Either skip re-validation deliberately (removal cannot create invalid config, unlike addition) and note why in the implementation, or add it with its own explicit test. Either choice is reasonable; just don't add the `try/except` incompletely.

## Code Examples

### The core reorder for `remove_instance` (CONSIST-01)
```python
# Illustrative diff-shape against triggarr/web/routes.py's current remove_instance
# (lines 937-995). Exact variable names/validation choice (Pitfall F) are left to
# implementation; the ORDER shown here is the locked decision (D-02).

settings = request.app.state.settings
instances = getattr(settings, app_name)

if instance_name not in instances:
    return HTMLResponse(f"Instance '{html.escape(instance_name)}' not found", status_code=400)

async with request.app.state.search_lock:
    # 1. Build the replacement WITHOUT touching live settings (mirrors add_instance).
    updated_instances = dict(instances)
    del updated_instances[instance_name]
    new_settings = settings.model_copy(update={app_name: updated_instances})

    # 2. Write to disk FIRST.
    config_path = request.app.state.config_path
    try:
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
        )
    except OSError as exc:
        # D-07: one error-level log line naming app + instance + sanitized system reason.
        logger.error(
            "Could not save settings after removing {app}/{inst}: {exc_type}: {exc}",
            app=app_name, inst=instance_name, exc_type=type(exc).__name__, exc=exc,
        )
        # D-05 wording, D-02 postcondition: settings/instances untouched above this point.
        return _removal_failed_response(request, app_name, instance_name)  # see Pattern 2

    # 3. Write succeeded -- now safe to swap live settings and clean up.
    request.app.state.settings = new_settings
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

# 4. Close outside the lock, per D-15/D-16 never letting a close failure
#    override an already-successful removal (Pitfall C).
if client:
    try:
        await client.close()
    except Exception as exc:
        logger.error(
            "Removed {app}/{inst} but closing its connection failed: {exc_type}: {exc}",
            app=app_name, inst=instance_name, exc_type=type(exc).__name__, exc=exc,
        )

# 5. Normal success response, unchanged from today.
settings_url = str(request.url_for("settings_page"))
if request.headers.get("HX-Request") == "true":
    return HTMLResponse("", headers={"HX-Redirect": settings_url})
return RedirectResponse(url=settings_url, status_code=303)
```

### The non-dict-root guard for `load_state` (CONSIST-03)
See Pattern 3 above for the full shared-helper shape. The minimal addition to `load_state` itself:
```python
# triggarr/state.py::load_state, after the existing try/except JSONDecodeError/OSError block
if not isinstance(data, dict):
    return _recover_from_bad_state_file(resolved_state_path, "a non-object JSON root", type(data).__name__)

if _is_v22_state_format(data):
    ...
return _merge_defaults(data)
```

### The test to flip (per its own docstring instruction)
```python
# tests/test_state.py -- currently:
def test_state_wrong_structure_list_crashes(tmp_path: Path) -> None:
    """...This is a known gap... When load_state is hardened to handle non-dict
    roots, convert this test to assert recovery to defaults instead."""
    state_file = tmp_path / "state.json"
    state_file.write_text("[1, 2, 3]")
    with pytest.raises(AttributeError):
        load_state(state_file)

# After the fix, per the docstring's own instruction:
def test_state_wrong_structure_list_recovers(tmp_path: Path) -> None:
    """Valid JSON list (not dict) recovers to defaults instead of crashing (CONSIST-03)."""
    state_file = tmp_path / "state.json"
    state_file.write_text("[1, 2, 3]")
    state = load_state(state_file)
    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []
# Add parallel tests for "42" and "null" roots (locked by CONSIST-03's own wording);
# a string/boolean root sibling is Claude's Discretion (87-CONTEXT.md).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `remove_instance` deletes from live settings before writing | Build-write-swap, matching `add_instance`/`save_settings`/`change_password`/etc. | This phase | Removes the one outlier; no architectural shift — the other six routes already prove this pattern works |
| `load_state` assumes the parsed JSON root is always a dict | `isinstance(data, dict)` guard before any `.get()` call | This phase | Closes a documented, intentionally-deferred gap; `test_state_wrong_structure_list_crashes`'s docstring has specified this exact fix since before this milestone existed |

**Deprecated/outdated:** None — nothing in this phase retires an existing capability; both changes are pure hardening of existing behavior.

## Neighbouring Save Paths (D-13 check, performed this session)

Every other settings-mutating route in `triggarr/web/routes.py` was read directly and confirmed to already follow validate→write→swap, with no code change needed:

| Route | Location | Pattern confirmed |
|-------|----------|--------------------|
| `save_settings` | `routes.py:636-851` | `SettingsModel(**new_config)` validated at line 717 **before** the write (727-729); swap at 731 |
| `add_instance` | `routes.py:883-934` | `SettingsModel(**config_dict)` validated at 916 before the write (924-926); swap at 927 |
| `setup_post` | `routes.py:1396-1479` | `current_settings.model_copy(update={"auth": new_auth})` before the write (1450-1452); swap (via `load_settings` re-read) at 1454 |
| `change_password` | `routes.py:1658-1746` (write at ~1715-1719) | `model_copy` before write; swap via `load_settings` after |
| `save_security` | `routes.py:1749-1774` | `model_copy` before write (1764-1766); swap at 1768 |
| `regenerate_api_key_endpoint` | `routes.py:1778-1802` | `model_copy` before write (1788-1790); swap at 1792 |
| Password-reset confirm | `routes.py:~2093-2121` | `model_copy` before write (2117-2119); swap at 2121 |

**Finding to record (D-13): no other route is unsafe.** `remove_instance` is confirmed as the single outlier in the entire file. Nothing needs to be added to `.planning/backlog/MAINTENANCE.md` under D-13 beyond a one-line note that the audit was performed and found no other unsafe route — there is no "evidence of an unsafe route" to hand off, because none exists.

**D-14 (recorded, not fixed here):** confirmed directly in code — `save_settings`'s only failure signal on a write error is an uncaught `OSError` propagating to a raw 500 (proven by the existing `test_save_settings_propagates_write_failure`, which asserts `status_code == 500` with no custom error page). `add_instance`'s "Add" form (`settings.html:267`, `<form method="post" action="...">`, **not** htmx-wired — no `hx-post`) submits as a plain full-page POST, so its existing `HTMLResponse(err, status_code=400)` responses (e.g. "Maximum 5 instances per app type") render as a bare, unstyled error page replacing the whole document, not as an inline message — confirmed by reading the template, not assumed. Both are real, visible gaps and match D-14's description exactly; they are out of scope for this phase per 87-CONTEXT.md and should be written into `.planning/backlog/MAINTENANCE.md` pointing at the UI Redesign milestone's "Settings sections and one save" item, as D-14 already specifies.

## D-12 check (performed this session): object-root-but-wrong-inside already recovers

Confirmed by reading `_merge_defaults` (`state.py:171-207`) and the existing passing test `test_state_wrong_nested_type_recovers` (`tests/test_state.py:423-437`, `{"radarr": "not_a_dict", "sonarr": {}}`): the `isinstance(loaded_section, dict)` guard at `state.py:181` already causes a wrong-typed-but-present app key to fall back to an empty dict (and `isinstance(instance_data, dict)` at `state.py:184` does the same one level deeper for a wrong-typed individual instance entry). `_is_v22_state_format` (`state.py:148-151`) is likewise already guarded (`isinstance(section_data, dict)`) against a non-dict `radarr`/`sonarr` value. **No code change needed for this case** — D-12's "leaves this as is" is already true today, confirmed rather than assumed. No new test is strictly required, but the planner may choose to keep `test_state_wrong_nested_type_recovers` as the documented proof (already exists, already passing, needs no modification).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The best htmx mechanism for the row-scoped error is "return 200 with differentiated content, change `hx-target` away from `body`" rather than a global `responseHandling` override | Architecture Patterns, Pattern 2 | If wrong, the planner would instead need to customize htmx's global config, which changes behavior for every other htmx element on the Settings page (and every other page) — a materially larger blast radius. This is a recommendation under Claude's Discretion (87-CONTEXT.md), not a verified requirement; flagged here so the planner evaluates it deliberately rather than assuming it's locked. |
| A2 | Set-aside filename should use `with_name(...+".bad")` rather than some other extension/scheme | Pitfall A, Code Examples | Low risk — explicitly Claude's Discretion per 87-CONTEXT.md ("The set-aside file's name and permissions"); any reasonable fixed, non-accumulating name satisfies D-08 |

**All other claims in this research were verified by reading the current codebase directly** (file paths and line numbers cited throughout) or confirmed against the vendored `htmx.min.js`'s actual shipped source — no training-data-only claims beyond the two flagged above.

## Open Questions

1. **Exact wording of the D-10 state-file warning and the D-07/D-16 log lines.**
   - What we know: the required content (file name, kind-found-vs-expected, "queue progress and last-run times were reset," "search history is unaffected," never file contents) is fully specified by D-10; D-07/D-16 require naming app, instance, and system reason, redacted by the existing sink.
   - What's unclear: the precise phrasing is explicitly Claude's Discretion.
   - Recommendation: the planner/executor can finalize wording at implementation time; the illustrative strings in Code Examples above are not locked.

2. **Whether to add `SettingsModel(**config_dict)` re-validation to the fixed `remove_instance` (Pitfall F).**
   - What we know: removal cannot produce invalid config, so it's not required for correctness.
   - What's unclear: whether matching `add_instance`'s shape exactly (for consistency/future-proofing) is worth the extra code.
   - Recommendation: optional; if added, it needs its own explicit test for the (now-reachable) `ValidationError` branch, or that branch is untested dead code.

## Environment Availability

Skipped — this phase has no external dependencies beyond the project's own already-installed stack (Python stdlib, pydantic, loguru, vendored htmx). `uv run pytest`, `uv run ruff check` are already confirmed working project tooling per `./CLAUDE.md`'s Development Commands section; no new tool/service/runtime is introduced.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`, `pyproject.toml:42-43`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_web.py tests/test_state.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONSIST-01 | Failed save during removal leaves settings/scheduler/client/state unchanged | unit (integration-style via `TestClient`) | `uv run pytest tests/test_web.py -k remove_instance -x -q` | ✅ existing tests to extend (`test_remove_instance_happy_path` et al., `tests/test_web.py:1478-1546`); new postcondition-asserting test needed (Pitfall D) |
| CONSIST-02 | User sees fixed-wording error, no internal detail, instance name escaped | unit | `uv run pytest tests/test_web.py -k remove_instance -x -q` | ✅ same file; new test needed for response content/escaping; `test_no_new_body_swap_html_targets` (`tests/test_web.py:1548-1570`) must be updated in the same change (Pitfall E) |
| CONSIST-03 | Non-dict state root recovers to defaults with a warning, not a crash | unit | `uv run pytest tests/test_state.py -k "wrong_structure or state_corrupt" -x -q` | ✅ `test_state_wrong_structure_list_crashes` exists and must be flipped per its own docstring (`tests/test_state.py:407-420`); new `42`/`null`-root siblings and set-aside-copy tests needed |

### Sampling Rate
- **Per task commit:** the quick run command above (scoped to the two touched test files).
- **Per wave merge:** `uv run pytest tests/ -x -q` (full suite) plus `uv run ruff check triggarr/ tests/`.
- **Phase gate:** full suite green before `/bm:verify-work`; this project's own CLAUDE.md additionally requires offering `/deep-review` before the phase's PR reaches `main`.

### Wave 0 Gaps
None — existing test infrastructure (pytest, `multi_instance_app` fixture, `tmp_path`-based state tests, the loguru `sink`-capture pattern already used by `test_state_corrupt_warning_names_reason_without_contents`) already covers everything this phase's new tests need. No new fixtures, no new framework install.

## Security Domain

`security_enforcement` is absent from `.planning/config.json`, so it is treated as enabled. This phase touches no authentication, session, or cryptographic code; the only user-controllable value involved is the instance name (already-validated, already length-capped at 64 chars by the existing `len(instance_name) > 64` check, `routes.py:946`).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not touched by either fix |
| V3 Session Management | no | Not touched by either fix |
| V4 Access Control | no | Removal already requires an authenticated session via existing middleware (unchanged) |
| V5 Input Validation | yes (narrow) | `html.escape(instance_name)` in any new response text, exactly matching the existing not-found branch's convention; no new input surface is introduced |
| V6 Cryptography | no | Not touched |
| V7 Error Handling & Logging | yes | Directly governs CONSIST-02 (no internal detail to the user) and D-10 (no file contents in the warning) — both already specified by the locked decisions and the project's own CLAUDE.md rule against exposing stack traces/internal errors |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected content in an HTML error fragment (if a future change ever echoes more than the instance name) | Tampering/Information Disclosure | `html.escape` on any user-supplied value in response HTML — already the established convention in this file; no `| safe`/`innerHTML` of user content anywhere in scope |
| Internal error detail (file paths, exception text) reaching the browser | Information Disclosure | D-05's fixed wording has none of this; the project's own CLAUDE.md rule ("generic message out, details logged server-side") already forbids it project-wide |

## Sources

### Primary (HIGH confidence — read directly from the installed codebase this session)
- `triggarr/web/routes.py` — full read of `save_settings` (636-851), `add_instance` (883-934), `remove_instance` (937-995), `setup_post` (1396-1479), `change_password` (1658-1746), `save_security` (1749-1774), `regenerate_api_key_endpoint` (1778-1802), password-reset confirm (~2080-2130)
- `triggarr/state.py` — full read (`load_state`, `_merge_defaults`, `_is_v22_state_format`, `_migrate_v22_state`, `_default_state`, `save_state`)
- `triggarr/config.py` — full read (`_atomic_toml_write`, `_settings_to_dict`, `detect_and_migrate_v22`, `_atomic_text_write`, `backfill_instance_ids`)
- `triggarr/models/config.py:186-212` — `Settings` model_config (confirms no `validate_assignment`)
- `triggarr/clients/base.py:295-314` — `ArrClient.close()` (confirms no internal guard)
- `triggarr/logging.py` — `create_redacting_sink`/`_redact` (confirms automatic secret redaction, no per-call-site work needed)
- `triggarr/templates/settings.html` — full read of the instance-row markup, Remove button's current `hx-target`/`hx-swap`, the Add-instance form's plain (non-htmx) submission
- `triggarr/templates/partials/security_password.html` — the "always 200, template differentiates" precedent
- `triggarr/static/js/htmx.min.js` — version string (`"2.0.8"`) and the exact default `responseHandling` array, read directly from the vendored/shipped file
- `tests/test_web.py` — `multi_instance_app` fixture (1054-1140), all existing `test_remove_instance_*` tests (1478-1546, 2834-2845), `test_save_settings_propagates_write_failure` (856-883), `test_no_new_body_swap_html_targets` (1548-1570)
- `tests/test_state.py` — all existing corrupt/wrong-structure/wrong-nested-type tests (383-458)
- `triggarr/search/scheduler.py:460-500` — `create_lifespan`'s single `load_state` call site
- `.planning/config.json` — confirms `nyquist_validation`/`security_enforcement` absent (both treated as enabled)
- `.planning/backlog/MAINTENANCE.md` — confirms the existing bugs-005 entry and the established entry-writing convention for D-13/D-14 notes
- `pyproject.toml:42-43` — pytest/asyncio config

### Secondary (HIGH confidence — milestone-level research already completed this session, read and cross-checked against the live code above)
- `.planning/research/SUMMARY.md` — confirmed defect status table (items 1 and 2), Phase 1 rationale
- `.planning/research/PITFALLS.md` — Pitfall 4 (write-before-mutate), Pitfall 5 (non-dict state root), Pitfall 7 (client-close failure precedent, used here for Pitfall C), "Looks Done But Isn't" checklist item for state/config consistency
- `.planning/research/ARCHITECTURE.md` — §1a/§1b exact current-code traces, confirming the same line numbers independently re-verified this session

### Tertiary
None used — every claim in this document was either read directly from the shipped codebase this session or carried from the already-completed, already-code-verified milestone research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; every library claim verified by reading the installed/vendored source directly.
- Architecture: HIGH — both fixes traced to exact current file:line, cross-checked against the milestone's independently-produced ARCHITECTURE.md/PITFALLS.md, which agree.
- Pitfalls: HIGH — every pitfall grounded in current code (Pitfalls A, B, C, F) or an existing test whose own docstring/behavior proves the point (Pitfalls D, E).

**Research date:** 2026-11-15
**Valid until:** 30 days (stable internal refactor; no fast-moving external dependency involved) — but re-check `triggarr/static/js/htmx.min.js`'s version if it is ever upgraded before this phase executes, since the `responseHandling` default could change between htmx major versions.
