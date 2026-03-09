# Phase 6: Bug Fixes & Resilience - Research

**Researched:** 2026-02-24
**Domain:** Concurrency safety, error handling, state recovery, log redaction
**Confidence:** HIGH

## Summary

Phase 6 addresses six specific bugs and resilience gaps identified during code review (QUAL-01 through QUAL-06). All issues are in existing Python code using libraries already in the project (asyncio, httpx 0.28.1, Pydantic 2.12.5, loguru 0.7.3). No new dependencies are needed.

The bugs fall into three categories: (1) concurrency — scheduler and manual search-now can corrupt shared state, (2) data integrity — settings written before validation, state files crash on corruption or schema drift, temp files leak on failure, and (3) error handling — httpx exception hierarchy is incomplete, Pydantic ValidationError is uncaught in API response parsing, `deduplicate_to_seasons` crashes on missing fields, and log redaction misses exception tracebacks.

**Primary recommendation:** Fix all six issues as targeted surgical changes to existing files. No architectural changes needed — each fix is a focused edit to one or two modules.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QUAL-01 | Concurrent search cycles serialized via asyncio.Lock — no state race condition | Pattern: single `asyncio.Lock` on `app.state`, acquired in both `make_search_job` and `search_now` route. See Architecture Pattern 1. |
| QUAL-02 | Settings validated before writing to disk — invalid config never corrupts TOML file | Pattern: construct `Settings(**new_config)` before `config_path.write_text()`. See Architecture Pattern 2. |
| QUAL-03 | Atomic state writes clean up temp files on failure; corrupt state recovers to defaults | Pattern: try/except around `os.replace`, unlink temp in except. `load_state` catches `json.JSONDecodeError`. See Architecture Patterns 3 & 4. |
| QUAL-04 | State file load fills missing keys from defaults for forward-compatible schema migration | Pattern: merge loaded JSON over `_default_state()` structure. See Architecture Pattern 4. |
| QUAL-05 | Log redaction covers exception tracebacks; settings hot-reload refreshes redaction filter | Pattern: replace `filter=` with custom `sink` wrapper that redacts the full formatted output. See Architecture Pattern 5. |
| QUAL-06 | All API response parsing handles ValidationError gracefully; httpx retry covers RemoteProtocolError | Pattern: add `RemoteProtocolError` to retry catch, catch `ValidationError` in `get_paginated` and `validate_connection`, use `.get()` in `deduplicate_to_seasons`. See Architecture Pattern 6. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncio (stdlib) | 3.11+ | `asyncio.Lock` for concurrency serialization | Built-in, zero overhead, correct for single-event-loop apps |
| httpx | 0.28.1 | HTTP client with structured exception hierarchy | Already used; `RemoteProtocolError` is a subclass of `ProtocolError -> TransportError -> RequestError -> HTTPError` |
| pydantic | 2.12.5 | Settings and API response validation | Already used; `ValidationError` is a `ValueError` subclass |
| loguru | 0.7.3 | Logging with custom sink for redaction | Already used; custom sink intercepts full formatted output including tracebacks |
| json (stdlib) | 3.11+ | State file parsing with `JSONDecodeError` handling | Already used |

### Supporting
No new libraries needed. All fixes use existing dependencies.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.Lock | asyncio.Semaphore(1) | Lock is simpler and more explicit for mutual exclusion |
| Custom sink redaction | loguru `patcher` | Sink wrapper is simpler — patcher modifies record dict but doesn't cover the formatted traceback string |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Current File Structure (files to modify)
```
fetcharr/
├── logging.py           # QUAL-05: traceback redaction via custom sink
├── state.py             # QUAL-03, QUAL-04: temp cleanup + schema migration
├── config.py            # (no changes needed)
├── clients/
│   └── base.py          # QUAL-06: httpx hierarchy fix + ValidationError catch
├── search/
│   ├── engine.py        # QUAL-06: deduplicate_to_seasons missing field handling
│   └── scheduler.py     # QUAL-01: asyncio.Lock in make_search_job
└── web/
    └── routes.py        # QUAL-01: asyncio.Lock in search_now; QUAL-02: validate-before-write; QUAL-05: redaction refresh
```

### Pattern 1: asyncio.Lock for Search Cycle Serialization (QUAL-01)

**What:** A single `asyncio.Lock` stored on `app.state` protects all search cycle execution. Both the scheduler job closure and the manual search-now route acquire the lock before running a cycle.

**When to use:** Whenever two async code paths can concurrently mutate `app.state.fetcharr_state`.

**Current bug:** `make_search_job` (scheduler) and `search_now` (route handler) both read/write `app.state.fetcharr_state` and call `save_state`. If APScheduler fires while a manual search is in progress, both coroutines race on the same state dict and state file.

**Fix location:** `scheduler.py` (create lock in `create_lifespan`, pass to `make_search_job`) and `routes.py` (acquire lock in `search_now`).

**Example:**
```python
# In scheduler.py create_lifespan:
app.state.search_lock = asyncio.Lock()

# In make_search_job job closure:
async def job() -> None:
    async with app.state.search_lock:
        client = getattr(app.state, f"{app_name}_client", None)
        if client is None:
            return
        # ... existing cycle + save_state logic ...

# In routes.py search_now:
async with request.app.state.search_lock:
    request.app.state.fetcharr_state = await cycle_fn(...)
    save_state(...)
```

**Key detail:** `asyncio.Lock` is NOT reentrant. This is fine because neither the scheduler job nor the search-now handler calls the other. The lock scope must include both the cycle call AND the `save_state` call — saving outside the lock would still race.

### Pattern 2: Validate Settings Before Writing (QUAL-02)

**What:** Construct the `Settings` Pydantic model from the form data dict BEFORE writing the TOML file to disk.

**Current bug:** In `routes.py save_settings`:
1. `config_path.write_text(tomli_w.dumps(new_config))` — writes to disk
2. `new_settings = load_settings(config_path)` — validates via Pydantic
If step 2 raises `ValidationError`, invalid config is already on disk and the app will crash on next restart.

**Fix:**
```python
# Validate FIRST
try:
    new_settings = Settings(**new_config)
except ValidationError:
    logger.warning("Invalid settings rejected")
    return RedirectResponse(url="/settings", status_code=303)

# THEN write (config is known-good)
config_path.write_text(tomli_w.dumps(new_config))
os.chmod(config_path, 0o600)
request.app.state.settings = new_settings
```

**Key detail:** `Settings(**new_config)` bypasses the TOML file source and uses `init_settings` directly, which is the highest-priority source per `settings_customise_sources`. This already works because `load_settings` does the same thing. The `ValidationError` import comes from `pydantic`, not `pydantic_settings`.

### Pattern 3: Temp File Cleanup on os.replace Failure (QUAL-03 — write side)

**What:** Wrap `os.replace` in try/except and unlink the temp file on failure. Also handle `json.dump` failures.

**Current bug:** In `state.py save_state`, if `os.replace(tmp.name, state_path)` raises (e.g., cross-filesystem, permission denied), the temp file is left as an orphan in the parent directory.

**Fix:**
```python
def save_state(state: FetcharrState, state_path: Path = STATE_PATH) -> None:
    parent = state_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", dir=parent, suffix=".tmp", delete=False
    ) as tmp:
        json.dump(state, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())

    try:
        os.replace(tmp.name, state_path)
    except OSError:
        # Clean up orphaned temp file
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
```

### Pattern 4: Corrupt State Recovery + Schema Migration (QUAL-03 read side + QUAL-04)

**What:** `load_state` catches `json.JSONDecodeError` and returns defaults. After loading, it merges the loaded data over a fresh default state to fill missing keys.

**Current bug (QUAL-03 read):** If the state file is truncated or contains garbage, `json.load(f)` raises `json.JSONDecodeError` and the app crashes.

**Current bug (QUAL-04):** If a new version adds fields to `AppState` (e.g., `missing_count`), an old state file missing those keys will cause `KeyError` when the code tries to access them. The `_build_app_context` function uses `.get()` safely, but the search engine uses direct bracket access like `state["radarr"]["missing_cursor"]`.

**Fix:**
```python
def _merge_defaults(loaded: dict) -> FetcharrState:
    """Merge loaded state over defaults so missing keys get default values."""
    defaults = _default_state()
    for app_name in ("radarr", "sonarr"):
        if app_name in loaded and isinstance(loaded[app_name], dict):
            defaults[app_name] = {**defaults[app_name], **loaded[app_name]}
    if "search_log" in loaded and isinstance(loaded["search_log"], list):
        defaults["search_log"] = loaded["search_log"]
    return defaults


def load_state(state_path: Path = STATE_PATH) -> FetcharrState:
    if not state_path.exists():
        return _default_state()
    try:
        with open(state_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt state file at {path} — resetting to defaults", path=state_path)
        return _default_state()
    return _merge_defaults(data)
```

**Key detail:** The merge must be shallow per-app (not deep) because `AppState` is a flat dict. The `search_log` is replaced wholesale since it's a list not a dict.

### Pattern 5: Log Redaction Covering Tracebacks (QUAL-05)

**What:** Replace the current `filter=` approach with a custom sink wrapper that redacts secrets from the COMPLETE formatted output, including exception tracebacks.

**Current bug:** The redaction filter only modifies `record["message"]`, which is the log message text. When `logger.exception()` or `logger.error(..., exc_info=True)` is used, the formatted traceback is appended AFTER the filter runs and can contain API keys (e.g., in the httpx client URL or exception message).

**Verified via testing:** A custom sink function receives the fully formatted string including the traceback. Replacing secrets in the sink output redacts both the message and the traceback.

**Fix:**
```python
def create_redacting_sink(secrets: list[str], stream=sys.stderr):
    """Create a loguru sink that redacts secrets from the full output (including tracebacks)."""
    def sink(message):
        text = str(message)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        stream.write(text)
        stream.flush()
    return sink


def setup_logging(level: str, secrets: list[str]) -> int:
    """Configure loguru with redacting sink. Returns handler ID for removal."""
    logger.remove()
    handler_id = logger.add(
        create_redacting_sink(secrets),
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
        level=level.upper(),
        colorize=False,  # Sink is a function, not a stream — no ANSI
    )
    return handler_id
```

**Hot-reload (QUAL-05 second half):** When `save_settings` in `routes.py` changes API keys, the redaction filter must be refreshed. The fix: `setup_logging` returns the handler ID. Store it on `app.state`. On settings save, call `setup_logging` again with the new secrets (which internally does `logger.remove()` + `logger.add()`).

**Example in routes.py save_settings:**
```python
# After updating settings, refresh redaction if keys changed
from fetcharr.startup import collect_secrets
from fetcharr.logging import setup_logging

secrets = collect_secrets(new_settings)
setup_logging(new_settings.general.log_level, secrets)
```

**Key detail:** `colorize=False` is needed because custom sink functions receive the message as a `str` (loguru's `Message` type), not a file stream. Colorization requires a file-like object with `isatty()`.

### Pattern 6: httpx Exception Hierarchy + ValidationError + Missing Fields (QUAL-06)

**What:** Three related fixes to API client error handling.

**Bug 6a — Missing `RemoteProtocolError` in retry:**
The `_request_with_retry` method catches `httpx.HTTPStatusError`, `httpx.ConnectError`, and `httpx.TimeoutException`. But `RemoteProtocolError` (server sends malformed HTTP, e.g., truncated response) is a sibling under `TransportError`, not a subclass of any of those three.

httpx exception hierarchy (verified from installed httpx 0.28.1):
```
HTTPError
├── HTTPStatusError           (response has 4xx/5xx status)
└── RequestError
    ├── TransportError
    │   ├── TimeoutException  (ConnectTimeout, ReadTimeout, WriteTimeout, PoolTimeout)
    │   ├── NetworkError      (ConnectError, ReadError, WriteError, CloseError)
    │   ├── ProtocolError     (LocalProtocolError, RemoteProtocolError)  <-- MISSED
    │   ├── ProxyError
    │   └── UnsupportedProtocol
    ├── DecodingError
    └── TooManyRedirects
```

**Fix:** Catch `httpx.RemoteProtocolError` in the retry tuple, or better, catch `httpx.TransportError` which covers all transport-level failures (network, timeout, protocol). This is the most robust approach since it also covers `ReadError`, `ProxyError`, etc.

```python
# In _request_with_retry:
except (httpx.HTTPStatusError, httpx.TransportError):
    # Retry once
    ...
```

**Rationale:** `TransportError` is the parent of `TimeoutException`, `NetworkError` (incl. `ConnectError`), and `ProtocolError` (incl. `RemoteProtocolError`). Using it simplifies the catch clause AND covers all transient transport failures. `HTTPStatusError` remains separate because it's NOT a `TransportError`.

The same fix applies to the cycle abort catches in `engine.py`:
```python
except httpx.HTTPError as exc:  # Catches both HTTPStatusError and all RequestError subclasses
```
This is actually already partially done (the current code catches `httpx.HTTPError` as the final catch), but redundantly also catches `HTTPStatusError`, `ConnectError`, and `TimeoutException` before it. Simplify to just `httpx.HTTPError`.

**Bug 6b — `validate_connection` and `get_paginated` miss `ValidationError`:**
Both methods call `PaginatedResponse.model_validate()` or `SystemStatus.model_validate()`. If the *arr API returns unexpected JSON structure, `ValidationError` is raised and uncaught.

**Fix for `validate_connection`:** Add `except pydantic.ValidationError` alongside existing catches.
**Fix for `get_paginated`:** Let it propagate as an unrecoverable error (the data is genuinely malformed), but catch it in the cycle abort handler.

```python
# In validate_connection, add:
except pydantic.ValidationError as exc:
    logger.warning(
        "{app}: Unexpected API response format: {exc}",
        app=self._app_name,
        exc=exc,
    )
    return False
```

**Bug 6c — `deduplicate_to_seasons` crashes on missing fields:**
Uses `ep["seriesId"]` and `ep["seasonNumber"]` with bracket notation, which raises `KeyError` if the API returns an episode without those fields (theoretically possible with Sonarr v3/v4 edge cases).

**Fix:** Use `.get()` with skip-on-missing:
```python
for ep in episodes:
    series_id = ep.get("seriesId")
    season_number = ep.get("seasonNumber")
    if series_id is None or season_number is None:
        continue  # Skip malformed episode record
    key = (series_id, season_number)
    ...
```

### Anti-Patterns to Avoid
- **Reentrant lock usage:** `asyncio.Lock` is NOT reentrant. Never call a locked function from within the same lock scope.
- **Broad except in retry:** Don't catch `Exception` in the retry path — only transport/HTTP errors should trigger retry. Application-level errors (e.g., `ValidationError`) should NOT be retried.
- **Logging secrets via `repr()`:** Never log the full client object or exception with `repr()` — httpx client headers contain the API key.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async mutual exclusion | Custom flag + event | `asyncio.Lock` | Lock handles edge cases (exception during hold, cancellation) correctly |
| Config validation | Manual field checks | `Settings(**dict)` (Pydantic) | Already validates all fields, types, constraints |
| JSON parse error handling | Custom parser | `json.JSONDecodeError` catch | Standard library exception, clean semantics |

**Key insight:** Every fix in this phase uses existing stdlib or library facilities. The bugs are all about missing error handling or incorrect ordering, not missing functionality.

## Common Pitfalls

### Pitfall 1: Lock Scope Too Narrow
**What goes wrong:** Acquiring the lock for the cycle function but NOT for the `save_state` call means two coroutines can still write the state file concurrently.
**Why it happens:** Developer thinks "I only need to protect the mutation" but forgets the file write is also part of the critical section.
**How to avoid:** The lock must span from cycle start through `save_state` completion.
**Warning signs:** Intermittent state file corruption or cursor regression under load.

### Pitfall 2: Validating Settings After Write
**What goes wrong:** Writing TOML to disk, then constructing `Settings()`, then discovering validation fails — but the bad config is already on disk.
**Why it happens:** The original code was written in build-up order (write then read) rather than defense-in-depth order (validate then write).
**How to avoid:** Always construct `Settings(**new_config)` FIRST. Only write to disk on success.
**Warning signs:** App crashes on restart after a settings edit that included invalid values.

### Pitfall 3: colorize=True with Custom Sink
**What goes wrong:** Passing `colorize=True` to `logger.add()` when the sink is a function (not a file stream) causes loguru to emit ANSI escape codes into the redacted string, but the sink cannot auto-detect terminal support.
**Why it happens:** Loguru only auto-detects colorization for file-like objects with `isatty()`.
**How to avoid:** Set `colorize=False` when using a custom sink function. The sink writes to stderr manually.
**Warning signs:** Log output contains `\x1b[` escape sequences in container logs.

### Pitfall 4: Catching HTTPError Instead of TransportError in Retry
**What goes wrong:** Catching `HTTPError` in the retry path would retry 4xx/5xx responses. A 401 (bad API key) should NOT be retried — it will never succeed.
**Why it happens:** `HTTPStatusError` and `TransportError` are both children of `HTTPError`.
**How to avoid:** Retry catches `httpx.HTTPStatusError` (for 5xx only, or all status errors) plus `httpx.TransportError` (for network/protocol issues). Or keep the current pattern of catching specific types.
**Warning signs:** Unnecessary retries on 401/403 responses.

### Pitfall 5: Deep Merge for State Migration
**What goes wrong:** Using a recursive deep merge overwrites nested structures unexpectedly.
**Why it happens:** `AppState` is flat (no nested dicts), so deep merge is overkill and risks complexity.
**How to avoid:** Shallow merge per app key: `{**defaults["radarr"], **loaded["radarr"]}`.
**Warning signs:** Unexpected key values after loading an old state file.

## Code Examples

### Complete asyncio.Lock Integration
```python
# scheduler.py — create_lifespan (inside lifespan function)
import asyncio

app.state.search_lock = asyncio.Lock()

# scheduler.py — make_search_job (job closure)
async def job() -> None:
    async with app.state.search_lock:
        client = getattr(app.state, f"{app_name}_client", None)
        if client is None:
            return
        try:
            app.state.fetcharr_state = await cycle_fn(
                client, app.state.fetcharr_state, app.state.settings,
            )
            save_state(app.state.fetcharr_state, state_path)
        except Exception as exc:
            logger.error("{app}: Unhandled error in search cycle -- {exc}",
                         app=app_name.title(), exc=exc)

# routes.py — search_now
async with request.app.state.search_lock:
    request.app.state.fetcharr_state = await cycle_fn(
        client, request.app.state.fetcharr_state, request.app.state.settings,
    )
    save_state(request.app.state.fetcharr_state, request.app.state.state_path)
```

### Complete State Recovery with Schema Migration
```python
# state.py
def _merge_defaults(loaded: dict) -> FetcharrState:
    defaults = _default_state()
    for app_name in ("radarr", "sonarr"):
        if app_name in loaded and isinstance(loaded[app_name], dict):
            defaults[app_name] = {**defaults[app_name], **loaded[app_name]}
    if "search_log" in loaded and isinstance(loaded["search_log"], list):
        defaults["search_log"] = loaded["search_log"]
    return defaults

def load_state(state_path: Path = STATE_PATH) -> FetcharrState:
    if not state_path.exists():
        return _default_state()
    try:
        with open(state_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt state file — resetting to defaults")
        return _default_state()
    return _merge_defaults(data)
```

### Complete Redacting Sink
```python
# logging.py
import sys
from collections.abc import Callable
from loguru import logger

def create_redacting_sink(secrets: list[str], stream=sys.stderr) -> Callable:
    def sink(message):
        text = str(message)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        stream.write(text)
        stream.flush()
    return sink

def setup_logging(level: str, secrets: list[str]) -> None:
    logger.remove()
    logger.add(
        create_redacting_sink(secrets),
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
        level=level.upper(),
        colorize=False,
    )
```

### Simplified httpx Exception Handling in Retry
```python
# clients/base.py — _request_with_retry
async def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
    try:
        response = await self._client.request(method, path, **kwargs)
        response.raise_for_status()
        return response
    except (httpx.HTTPStatusError, httpx.TransportError):
        logger.debug("{app}: Request to {path} failed, retrying in 2s",
                     app=self._app_name, path=path)
        await asyncio.sleep(2)
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            logger.warning("{app}: Retry failed for {path}: {exc}",
                           app=self._app_name, path=path, exc=exc)
            raise
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| loguru filter-based redaction | Custom sink-based redaction | loguru 0.6+ (2022) | Sink receives full formatted output including tracebacks |
| httpx.ConnectError + TimeoutException | httpx.TransportError (parent) | httpx 0.23+ (2022) | Single catch covers all transport failures |
| Manual dict validation | Pydantic model_validate + Settings(**kwargs) | Pydantic v2 (2023) | Validate before write pattern |

**Deprecated/outdated:**
- None — all approaches use current library APIs.

## Open Questions

1. **Should 5xx responses be retried differently than transport errors?**
   - What we know: Current code retries all `HTTPStatusError` (including 4xx). A 401 will never self-resolve.
   - What's unclear: Whether to differentiate 5xx (retry) from 4xx (don't retry).
   - Recommendation: Keep current behavior (retry once for all status errors) — the retry is only once with a 2s delay, so the cost of retrying a 4xx is negligible. The alternative (checking status code) adds complexity for minimal benefit.

## Sources

### Primary (HIGH confidence)
- httpx 0.28.1 installed package — exception hierarchy verified via `inspect.getmembers(httpx)` introspection
- Pydantic 2.12.5 installed package — `ValidationError` MRO verified as `ValueError` subclass
- loguru 0.7.3 installed package — custom sink behavior verified via test showing full traceback redaction
- Python 3.11+ stdlib — `asyncio.Lock`, `json.JSONDecodeError`, `os.replace`, `tempfile.NamedTemporaryFile` behavior verified

### Secondary (MEDIUM confidence)
- Codebase analysis of all 20 Python source files — every bug location identified and fix pattern verified against actual code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed, versions verified, APIs tested
- Architecture: HIGH - every bug was reproduced or confirmed via code reading and runtime testing
- Pitfalls: HIGH - all pitfalls derive from actual bugs found in the codebase and verified behavior

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable — no library upgrades needed)
