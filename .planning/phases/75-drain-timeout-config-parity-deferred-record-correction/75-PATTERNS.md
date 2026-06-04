# Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 6 code/template + 4 docs + 4 test surfaces
**Analogs found:** 14 / 14 (all surfaces have an in-repo analog; no greenfield patterns)

This phase is a "config-knob parity" rider: every code change mirrors an existing sibling
field (`request_timeout` / `page_size` / `max_consecutive_failures`) through the standard
config-knob loop. There is no novel architecture. The single substantive design decision
(D-06: config default, env overrides) is wired into one existing function
(`_read_shutdown_drain_timeout`) and one existing shutdown block.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/models/config.py` | model | config/transform | `max_consecutive_failures` field, config.py:134 | exact |
| `triggarr/web/validation.py` | utility | transform (parse+clamp) | `safe_int`, validation.py:179 | exact (sibling helper) |
| `triggarr/web/routes.py` (GET render) | route | request-response | `request_timeout` render line, routes.py:441 | exact |
| `triggarr/web/routes.py` (POST parse) | route | request-response (form parse) | `request_timeout` parse line, routes.py:544 | exact |
| `triggarr/templates/settings.html` | template | request-response (form render) | `request_timeout` input, settings.html:51-57 | exact |
| `triggarr/search/scheduler.py` | service | event-driven (lifespan shutdown) | `_read_shutdown_drain_timeout`, scheduler.py:58 (refactor in place) | self (refactor) |
| `.planning/STATE.md` | docs | n/a | deferred table, STATE.md:101-108 | exact |
| `README.md` | docs | n/a | drain/env docs, README.md:86, 95, 140 | exact |
| `CHANGELOG.md` | docs | n/a | v2.9.0 section, CHANGELOG.md:3 | exact |
| `tests/test_config.py` | test | n/a | `test_general_config_default_max_consecutive_failures`, test_config.py:158 | exact |
| `tests/test_validation.py` | test | n/a | `TestSafeInt`, test_validation.py:196 | exact |
| `tests/test_web.py` | test | n/a | `test_save_settings_with_new_fields`, test_web.py:696 | exact |
| `tests/test_scheduler.py` | test | n/a | drain-timeout tests, test_scheduler.py:628-662 | self (must stay green + extend) |

---

## Pattern Assignments

### `triggarr/models/config.py` (model, config field) — D-01

**Analog:** `GeneralConfig.max_consecutive_failures` (config.py:134), sibling float
`request_timeout` (config.py:129).

**Bounded-field pattern** (config.py:122-136):
```python
class GeneralConfig(BaseModel):
    """Global application settings."""

    log_level: str = "info"
    hard_max_per_cycle: int = 0  # 0 = unlimited; caps total items per app per cycle
    # v2.0 additions
    max_history_rows: int = 1000  # DEBT-03: max resolved rows kept in search_history
    request_timeout: float = 30.0  # DEBT-07: outbound HTTP timeout in seconds
    page_size: int = 50  # DEBT-08: *arr API pagination size
    tracking_window_minutes: int = 60  # TRACK-07: how long to wait for grabs after search
    tracking_delay_seconds: int = 90  # Delay before tracking check (unused)
    # SAFETY-03: bounded 1..100 to defend against typos at config edit time
    max_consecutive_failures: int = Field(default=5, ge=1, le=100)
    # v2.2: skip Radarr movies without past digital/physical release date
    skip_unreleased: bool = True
```

**Action:** Add one line to `GeneralConfig`, mirroring the `Field(...)`-with-bound idiom of
`max_consecutive_failures` but as a `float` (like `request_timeout`):
```python
    # DEBT-06: graceful-shutdown drain timeout (seconds). ge=1.0 defends against a
    # typo (e.g. 0) disabling the drain. Config is the default; TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT
    # env var overrides at shutdown time. No upper bound on the model; the form clamp (3600.0)
    # is the practical UI ceiling.
    shutdown_drain_timeout: float = Field(default=60.0, ge=1.0)
```
`Field` is already imported (used by `max_consecutive_failures`). No upper bound on the model
per D-01 — the `safe_float(..., 3600.0)` form clamp supplies the UI ceiling.

---

### `triggarr/web/validation.py` (utility, parse+clamp) — D-03

**Analog:** `safe_int` (validation.py:179-199) — copy signature shape and clamp idiom exactly.

**Pattern to copy** (validation.py:179-199):
```python
def safe_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Parse a form value as an integer, clamped to ``[minimum, maximum]``.

    Returns *default* when the value is None, empty, or unparseable.
    ...
    """
    if value is None or value == "":
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, n))
```

**Action:** Add a sibling `safe_float` immediately after `safe_int` (validation.py:~200),
identical structure with `float()` in place of `int()`:
```python
def safe_float(value: str | None, default: float, minimum: float, maximum: float) -> float:
    """Parse a form value as a float, clamped to ``[minimum, maximum]``.

    Returns *default* when the value is None, empty, or unparseable. Unlike
    :func:`safe_int`, this preserves fractional input (e.g. accepts "1.5") and
    coerces int-like strings via ``float()``.

    Args:
        value: Raw form string (may be None).
        default: Fallback when *value* is missing or invalid.
        minimum: Lower bound (inclusive).
        maximum: Upper bound (inclusive).

    Returns:
        A float guaranteed to be within ``[minimum, maximum]``.
    """
    if value is None or value == "":
        return default
    try:
        n = float(value)
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, n))
```
Note: the `except (ValueError, TypeError)` tuple matches the project convention (no bare
`except:`, per CLAUDE.md). `float("abc")` raises `ValueError`; `float(None)` raises `TypeError`.

---

### `triggarr/web/routes.py` (route — GET render + POST parse) — D-02, D-03

**Analog:** the `request_timeout` lines in both blocks.

**Import update** (routes.py:63): add `safe_float` to the existing validation import:
```python
from triggarr.web.validation import safe_int, safe_log_level, validate_arr_url, validate_instance_name
```
becomes
```python
from triggarr.web.validation import safe_float, safe_int, safe_log_level, validate_arr_url, validate_instance_name
```
(ruff `I` will sort; `safe_float` sorts before `safe_int`.)

**GET render dict pattern** (routes.py:436-451) — add one key alongside the sibling
`general.*` fields:
```python
        context={
            "apps": apps,
            "log_level": settings.general.log_level,
            "hard_max_per_cycle": settings.general.hard_max_per_cycle,
            "max_history_rows": settings.general.max_history_rows,
            "request_timeout": settings.general.request_timeout,
            "page_size": settings.general.page_size,
            "tracking_window_minutes": settings.general.tracking_window_minutes,
            "tracking_delay_seconds": settings.general.tracking_delay_seconds,
            "max_consecutive_failures": settings.general.max_consecutive_failures,
            "skip_unreleased": settings.general.skip_unreleased,
            ...
```
**Action:** Insert `"shutdown_drain_timeout": settings.general.shutdown_drain_timeout,`
adjacent to `max_consecutive_failures` (routes.py:445).

**POST parse pattern** (routes.py:540-551):
```python
    new_config: dict = {
        "general": {
            "log_level": safe_log_level(form.get("log_level")),
            "hard_max_per_cycle": safe_int(form.get("hard_max_per_cycle"), 0, 0, 1000),
            "max_history_rows": safe_int(form.get("max_history_rows"), 1000, 0, 100_000),
            "request_timeout": safe_int(form.get("request_timeout"), 30, 5, 300),
            "page_size": safe_int(form.get("page_size"), 50, 10, 500),
            "tracking_window_minutes": safe_int(form.get("tracking_window_minutes"), 60, 5, 1440),
            "tracking_delay_seconds": current_settings.general.tracking_delay_seconds,
            "max_consecutive_failures": safe_int(form.get("max_consecutive_failures"), 5, 1, 100),
            "skip_unreleased": form.get("skip_unreleased") == "on",
        },
    }
```
**Action:** Insert the new key in this dict, using `safe_float` (not `safe_int`):
```python
            "shutdown_drain_timeout": safe_float(form.get("shutdown_drain_timeout"), 60.0, 1.0, 3600.0),
```
Per D-03: `request_timeout` is a float field parsed via `safe_int` (a known wrinkle) — do NOT
propagate that to the new knob; use `safe_float` so `1.5` survives. Defaults `60.0, 1.0, 3600.0`
match the model default, the `ge=1.0` floor, and the agreed UI ceiling.

---

### `triggarr/templates/settings.html` (template, form input) — D-02, D-10

**Analog:** the `request_timeout` input (settings.html:51-57); also `page_size` (60-64) and
`max_consecutive_failures` (72-78).

**Markup pattern to mirror** (settings.html:51-57):
```html
            <div>
                <label class="block text-sm text-triggarr-muted mb-1">Request Timeout (seconds)</label>
                <input form="settings-form" type="number" name="request_timeout" value="{{ request_timeout }}"
                       min="5" max="300" step="1"
                       class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
                <p class="text-xs text-triggarr-muted mt-1">Timeout for outbound HTTP requests to *arr apps.</p>
            </div>
```

**Action:** Add an analogous `<div>` among the General fields (placement is Claude's discretion
per D-disc; natural slot is after `max_consecutive_failures`, settings.html:78). Use
`step="0.5"` to signal the float nature, `min="1"`, `max="3600"`, and help text documenting the
env-override precedence per D-10:
```html
            <div>
                <label class="block text-sm text-triggarr-muted mb-1">Shutdown Drain Timeout (seconds)</label>
                <input form="settings-form" type="number" name="shutdown_drain_timeout" value="{{ shutdown_drain_timeout }}"
                       min="1" max="3600" step="0.5"
                       class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
                <p class="text-xs text-triggarr-muted mt-1">
                    How long a graceful shutdown waits for an in-flight search cycle to finish
                    before forcing close. The <code>TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT</code>
                    environment variable overrides this value when set. Minimum 1s.
                </p>
            </div>
```
The `value="{{ shutdown_drain_timeout }}"` context var is supplied by the GET render dict above.

---

### `triggarr/search/scheduler.py` (service, shutdown event handler) — D-04, D-05, D-06

This is the one real wiring change. Two edits: (1) refactor the helper to take a `configured`
default; (2) resolve `drain` once at the top of the shutdown block and replace the ~6
constant references with the local.

**Helper refactor analog/target** (scheduler.py:58-75) — current:
```python
def _read_shutdown_drain_timeout() -> float:
    """RES-01 (Codex finding 3): read TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT env var.
    ...
    """
    raw = os.environ.get("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "60.0")
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = 60.0
    return max(value, 1.0)
```
**Action (D-04/D-06):** accept `configured: float = 60.0`; env overrides when set; on malformed
env, fall back to `configured`; clamp `>=1.0` applies to both sources:
```python
def _read_shutdown_drain_timeout(configured: float = 60.0) -> float:
    """RES-01 / DEBT-06: resolve the graceful-shutdown drain timeout.

    Precedence (D-06, 12-factor): the *configured* value (from
    GeneralConfig.shutdown_drain_timeout) is the default; the
    TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT env var overrides it when set. A malformed
    env value falls back to *configured* rather than crashing. The result is
    clamped to >= 1.0 so neither source can disable the drain (e.g. "0").
    ...
    """
    raw = os.environ.get("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT")
    if raw is None:
        value = configured
    else:
        try:
            value = float(raw)
        except (ValueError, TypeError):
            value = configured
    return max(value, 1.0)
```
Keep the existing deployment-guidance docstring tail (`stop_grace_period >` note).

**Module constant** (scheduler.py:81) — `_SHUTDOWN_DRAIN_TIMEOUT = _read_shutdown_drain_timeout()`.
Per D-05 (and Claude's discretion): the shutdown path must no longer read this import-time
constant. Either delete it, or retain it as an unreferenced legacy default. NOTE: the
existing test `test_shutdown_timeout_default_is_60s` (test_scheduler.py:628) imports and asserts
`_SHUTDOWN_DRAIN_TIMEOUT == 60.0`; if the constant is removed, that test must be updated/removed
(see test mapping below). If retained as a no-default-config call (`_read_shutdown_drain_timeout()`
with no env set → 60.0) it stays green for free. Planner picks; recommend keeping it (cheaper).

**Shutdown-drain block** (scheduler.py:600-657) — current references `_SHUTDOWN_DRAIN_TIMEOUT`
at lines 611, 618, 634, 648, 656:
```python
            holder = getattr(app.state, "search_lock_holder", None)
            if holder:
                ...
                logger.info(
                    "Shutdown: draining search lock (timeout={t}s); holder={job} elapsed={e:.1f}s",
                    t=_SHUTDOWN_DRAIN_TIMEOUT,         # 611
                    ...
                )
            else:
                logger.info(
                    "Shutdown: draining search lock (timeout={t}s); no current holder",
                    t=_SHUTDOWN_DRAIN_TIMEOUT,         # 618
                )
            ...
            try:
                try:
                    async with asyncio.timeout(_SHUTDOWN_DRAIN_TIMEOUT):   # 634
                        await app.state.search_lock.acquire()
                        acquired = True
                except TimeoutError:
                    ...
                    logger.warning(
                        "... did not finish in {timeout}s ...",
                        timeout=_SHUTDOWN_DRAIN_TIMEOUT,   # 648
                        ...
                    )
                    ...
                        logger.warning(
                            "... did not drain in {timeout}s ...",
                            timeout=_SHUTDOWN_DRAIN_TIMEOUT,   # 656
                        )
```
**Action (D-05):** Compute one local at the top of the block (right after `scheduler.shutdown(wait=False)`,
before the `holder = getattr(...)` line at scheduler.py:605), then replace all five `_SHUTDOWN_DRAIN_TIMEOUT`
references with `drain`:
```python
            # DEBT-06 (D-05): resolve drain timeout from config at shutdown time
            # (env overrides). settings is already in scope here, like search_lock /
            # search_lock_holder below — no new state-access pattern.
            drain = _read_shutdown_drain_timeout(app.state.settings.general.shutdown_drain_timeout)
```
Then `t=drain` (×2), `asyncio.timeout(drain)`, `timeout=drain` (×2). The `asyncio.timeout()`
mechanism (WR-01) is unchanged — only the value source changes.

**Verify `app.state.settings` is set in lifespan before shutdown.** The block already reads
`app.state.search_lock` and `app.state.search_lock_holder`; confirm `app.state.settings` is
assigned during lifespan startup (it is referenced by the settings routes, so it is on app
state, but the planner should confirm the lifespan sets `app.state.settings = settings` so the
shutdown read does not `AttributeError`). If lifespan binds the local `settings` closure var but
not `app.state.settings`, prefer reading the closure `settings.general.shutdown_drain_timeout`
directly (it is in scope in `create_lifespan`).

---

### `.planning/STATE.md` (docs) — D-07

**Analog/target:** Deferred Items table, STATE.md:101-108.

Current rows (STATE.md:107-108):
```markdown
| record correction | DEBT-07/08/03 (request timeout / page size / search-history cap) | v2.9 (mis-recorded as parked) | already shipped — DOCS-01 corrects record in Phase 75 |
| shipping in v2.10 | DEBT-06: Surface graceful-shutdown drain timeout in settings UI | v2.9 (spec D-5) | in scope — Phase 75 (CFG-03/CFG-04) |
```
**Action:** Per the in-table note (STATE.md:103: "DEBT-07/08/03/06 leave this table at v2.10
close"), update these two rows to reflect shipped reality (DEBT-07/08/03 shipped; DEBT-06 shipped
in Phase 75) — mark them resolved/removed. This is in-flight bookkeeping; GSD's
complete-milestone may rewrite STATE.md at archive (the durable record is roadmap/milestone
audit), so keep the edit minimal and factual.

---

### `README.md` (docs) — D-08

**Analog/target:** existing drain/env docs at README.md:86, 95, 140.

Existing surfaces (do NOT remove the `stop_grace_period > drain` guidance):
- README.md:86 — `stop_grace_period: 90s  # > TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT (default 60s)`
- README.md:95 — prose: "in-process search-cycle drain (default 60s, configurable via the
  `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` environment variable)"
- README.md:140 — systemd comment: "set via TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT"

**Action:** Add a sentence (near README.md:95) noting the new settings-UI path and the
precedence: the drain timeout is now a persisted config field
(`general.shutdown_drain_timeout`, settable in Settings, default 60s) and the
`TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env var **overrides** the configured value when set. Keep the
`>= 1.0` clamp and `stop_grace_period > drain` deployment guidance intact.

---

### `CHANGELOG.md` (docs, in-app changelog source) — D-09

**Analog/target:** the v2.9.0 section header + bulleted categories (CHANGELOG.md:3-22).

Section structure to mirror:
```markdown
## v2.9.0 (2026-06-02)

Security hardening, a search-reliability fix, and a documentation overhaul.

* Security:
  * ...
* Fixes:
  * ...
* Documentation:
  * ...
```
**Action:** Add a new top section (above v2.9.0) for the v2.10 release. Per spec §5 / D-09 the
v2.10 entry covers all three tracks shipped this milestone: password recovery (Track A),
Refresh-counts (Track B), and the drain-timeout settings knob (Track C). Exact wording/ordering
is Claude's discretion. This is rendered into the in-app changelog modal via
`triggarr/changelog.py::read_changelog()` (no code change needed). Use the date format
`## vX.Y.Z (YYYY-MM-DD)` to match the parser.

---

## Shared Patterns

### The config-knob round-trip (applies to config.py + routes.py + settings.html + tests)
**Sources:** `request_timeout` / `page_size` / `max_consecutive_failures`.
The established loop is: `GeneralConfig` field → GET render dict (`routes.py:436-451`) →
settings.html `{{ var }}` input → POST `safe_*` parse (`routes.py:540-551`) → atomic TOML
persist → reload on next view. The drain timeout joins this loop identically; the ONLY deviation
from the siblings is using `safe_float` instead of `safe_int` (D-03).

### Bounded-field defensive validation
**Source:** `max_consecutive_failures: int = Field(default=5, ge=1, le=100)` (config.py:134).
**Apply to:** the new `shutdown_drain_timeout` field. Same `Field(..., ge=...)` idiom; pydantic
raises `ValidationError` at construction for out-of-bound values. Defense in depth: the route
`safe_float(..., 1.0, 3600.0)` clamp also bounds the form value before it reaches the model.

### Parse-and-clamp helper
**Source:** `safe_int` (validation.py:179). Returns default on `None`/empty/unparseable,
catches `(ValueError, TypeError)` (no bare except — CLAUDE.md), clamps with
`max(minimum, min(maximum, n))`. `safe_float` is a structural clone.

### Shutdown reads app/lifespan state (no new pattern)
**Source:** the drain block already reads `app.state.search_lock` and
`app.state.search_lock_holder` (scheduler.py:605, 635). Reading
`app.state.settings.general.shutdown_drain_timeout` (or the lifespan-closure `settings`) at
shutdown time is consistent with this — no new state-access pattern introduced (D-05).

---

## Test Pattern Assignments

TDD mode is on. The scheduler refactor is behavior-preserving: existing drain tests must stay
green (or be minimally updated where they assert the now-removed import-time constant).

### Config field test → `tests/test_config.py`
**Analog:** `test_general_config_default_max_consecutive_failures` (test_config.py:158-172):
```python
def test_general_config_default_max_consecutive_failures() -> None:
    ...
    assert GeneralConfig().max_consecutive_failures == 5
    with pytest.raises(ValidationError):
        GeneralConfig(max_consecutive_failures=0)
    with pytest.raises(ValidationError):
        GeneralConfig(max_consecutive_failures=101)
```
**New test (per spec §4.4):** `test_general_config_default_shutdown_drain_timeout` — assert
default `== 60.0`; `pytest.raises(ValidationError)` for a value `< 1.0` (e.g. `0.0`); accept a
valid float (e.g. `GeneralConfig(shutdown_drain_timeout=120.5).shutdown_drain_timeout == 120.5`).
No upper-bound assertion (model has no `le=`). `ValidationError` is already imported in this file.

### `safe_float` helper test → `tests/test_validation.py`
**Analog:** `TestSafeInt` (test_validation.py:196-221) — copy each case for floats:
```python
class TestSafeInt:
    def test_valid_value(self) -> None:
        assert safe_int("30", default=5, minimum=1, maximum=1440) == 30
    def test_none_returns_default(self) -> None:
        assert safe_int(None, default=5, minimum=1, maximum=1440) == 5
    def test_empty_string_returns_default(self) -> None: ...
    def test_non_numeric_returns_default(self) -> None: ...
    def test_below_minimum_clamped(self) -> None: ...
    def test_above_maximum_clamped(self) -> None: ...
```
**New test:** `class TestSafeFloat` mirroring each case, PLUS a float-specific case proving the
fractional-preservation rationale for the helper:
`safe_float("1.5", default=60.0, minimum=1.0, maximum=3600.0) == 1.5` (this is the line that
would FAIL with `safe_int`, justifying the new helper). Add `safe_float` to the
`from triggarr.web.validation import ...` line at the top of the test file.

### Settings POST round-trip test → `tests/test_web.py`
**Analog:** `test_save_settings_with_new_fields` (test_web.py:696-733) and the render assertion
`test_settings_page_renders_new_config_fields` (test_web.py:685-693).
```python
def test_save_settings_with_new_fields(client, test_app):
    response = client.post("/settings", data={
        "log_level": "info",
        "request_timeout": "60",
        "page_size": "100",
        ... (full radarr/sonarr instance fields) ...
    }, follow_redirects=False)
    assert response.status_code == 303
    new_settings = test_app.state.settings
    assert new_settings.general.request_timeout == 60
    assert new_settings.general.page_size == 100
```
**New test (per spec §4.4):** extend or add a sibling that POSTs
`"shutdown_drain_timeout": "120.5"` in the form data and asserts
`new_settings.general.shutdown_drain_timeout == 120.5` (proves the round-trip AND the float
parse). Also add `"shutdown_drain_timeout" in response.text` to the render-assertion test. Reuse
the full instance-field payload shape from the analog (the POST handler rejects incomplete
instance data).

### Scheduler precedence tests → `tests/test_scheduler.py`
**Analog (must update):** `test_shutdown_timeout_default_is_60s` (test_scheduler.py:628-633) and
`test_shutdown_timeout_env_var_override` (test_scheduler.py:636-662). These currently assert the
import-time module constant `_SHUTDOWN_DRAIN_TIMEOUT` via `importlib.reload`. After the refactor:
- If the module constant is **kept** as `_read_shutdown_drain_timeout()` (no configured arg, no
  env) → both stay green unchanged.
- If **removed** → rewrite them to call `_read_shutdown_drain_timeout(configured=...)` directly.

**New tests (per spec §4.4 — the precedence matrix):** test `_read_shutdown_drain_timeout`
directly (pure function, no lifespan needed):
- env unset → returns `configured` (e.g. `_read_shutdown_drain_timeout(45.0) == 45.0`).
- env set → env wins over configured (`monkeypatch.setenv(..., "15.0")`;
  `_read_shutdown_drain_timeout(45.0) == 15.0`).
- clamp on both sources: `configured=0.5` → `>= 1.0`; env `"0"` → `1.0`.
- malformed env → falls back to `configured` (`monkeypatch.setenv(..., "abc")`;
  `_read_shutdown_drain_timeout(45.0) == 45.0`).

**Must stay green (behavior-preserving):** `test_shutdown_drains_search_lock`
(test_scheduler.py:564) and `test_shutdown_timeout_logs_holder_identity`
(test_scheduler.py:665). The latter sets `monkeypatch.setattr(sched, "_SHUTDOWN_DRAIN_TIMEOUT", 0.1)`
to force a fast drain — after the refactor the shutdown path reads `drain` from settings, NOT the
constant, so this test must be updated to set the drain via the configured value, e.g. construct
`make_settings(general=GeneralConfig(shutdown_drain_timeout=1.0))`. NOTE: the forced value MUST be
`1.0` (the field minimum), NOT `0.1` — Plan 75-01 adds `Field(ge=1.0, allow_inf_nan=False)`, so
`GeneralConfig(shutdown_drain_timeout=0.1)` raises `ValidationError` at construction. The
holder-identity test holds the lock and never releases it, so the drain times out regardless of
value; `1.0` proves the config-read path just as well as `0.1` did. The planner MUST flag this:
the existing holder-identity test's force-fast-drain target moves from the module constant to a
valid (`>= 1.0`) configured settings value.

---

## No Analog Found

None. Every surface in this phase has a direct in-repo analog — this is the defining property of
the "config-knob parity" rider (spec §1, Track C risk: Low — "mirrors existing knobs").

---

## Metadata

**Analog search scope:** `triggarr/models/`, `triggarr/web/`, `triggarr/templates/`,
`triggarr/search/`, `tests/`, repo-root docs (`README.md`, `CHANGELOG.md`), `.planning/STATE.md`.
**Files scanned:** config.py, validation.py, routes.py, settings.html, scheduler.py,
test_config.py, test_validation.py, test_web.py, test_scheduler.py, README.md, CHANGELOG.md,
STATE.md.
**Project conventions honored:** Python 3.11+, ruff E/F/I/UP/B/SIM, line length 120, no bare
`except:` (use `(ValueError, TypeError)`), loguru logging, atomic TOML writes (existing
settings-POST persist path), pytest-asyncio `asyncio_mode=auto`.
**Pattern extraction date:** 2026-06-03
```
