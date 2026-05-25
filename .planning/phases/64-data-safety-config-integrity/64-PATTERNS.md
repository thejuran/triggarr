# Phase 64: Data Safety & Config Integrity - Pattern Map

**Mapped:** 2026-05-25
**Files to modify:** 3 source (config.py, db.py — comment only, web/routes.py — none required)
**Files to create:** 3 test additions (test_config.py, test_web.py, test_db.py — all extensions to existing files)
**Analogs found:** 6 / 6 (all required patterns are already in the codebase)

## Scope Extracted from RESEARCH.md

RESEARCH.md is explicit about exact file:line targets. No CONTEXT.md exists. The phase work is:

| Target | Action | RESEARCH cite |
|--------|--------|---------------|
| `triggarr/config.py:113-115` | Patch `_atomic_toml_write` except block: log non-FNF OSErrors, preserve FNF suppression | RESEARCH 247-303 |
| `triggarr/config.py:214-241` | Wrap TOML load in `ensure_config` with friendly handler + backup-path hint + `sys.exit(1)` | RESEARCH 320-375 |
| `triggarr/db.py:329` (docstring) or near 339-350 | Add comment documenting that pending rows are exempt from trim cap | RESEARCH 237-239 |
| `tests/test_config.py` (extend) | Add TEST-02 cases: syntax-error → friendly log + SystemExit; invalid-UTF-8 → same; backup-path-mentioned-when-exists; SAFETY-04 cleanup-OSError logging, FNF silence, replace-failure logging | RESEARCH 426-680 |
| `tests/test_web.py` (extend) | Add TEST-03: two concurrent `POST /settings` via `httpx.AsyncClient + ASGITransport + asyncio.gather`, assert non-interleaved enter/exit order | RESEARCH 377-424, 575-588 |
| `tests/test_db.py` (extend) | Add SAFETY-01 soak test: insert 2× max_rows resolved entries, verify steady-state cap | RESEARCH 237-238 |

**No CONTEXT.md** — file list extracted directly from RESEARCH.md per orchestrator instructions.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/config.py` (`_atomic_toml_write` except block patch) | config layer / atomic write | file-I/O | self — surrounding lines `config.py:102-119` (same function) | exact |
| `triggarr/config.py` (`ensure_config` TOML-load wrapper) | startup layer / config loader | file-I/O + structured logging | `config.py:228-234` (existing warn-then-exit pattern); `db.py:64` (`.v{n}-backup` precedent) | role-match (no exact analog — new error-recovery handler in this file) |
| `triggarr/db.py` (comment near `insert_search_entry` trim SQL) | data layer / documentation | n/a (comment only) | `db.py:338` existing inline `# Tracking-aware pruning (DEBT-03): ...` comment | exact |
| `tests/test_config.py` (TEST-02 + SAFETY-04 cases) | test / config error handling | request-response (sync) | `tests/test_config.py:670-680` (atomic-write cleanup test); `tests/test_config.py:688-694` (TOML decode error test); `tests/test_startup.py:261-267` (loguru sink capture) | exact (combined) |
| `tests/test_web.py` (TEST-03 concurrent PUT) | test / async concurrency | event-driven (asyncio) | `tests/test_web.py:584-598` (concurrent rate-limit test — but that one uses sync `TestClient`; ASGITransport pattern is **new** for web tests) | partial — closest concurrency test uses TestClient; ASGITransport precedent lives in `tests/test_startup.py:257` and `tests/test_clients.py` |
| `tests/test_db.py` (SAFETY-01 soak test) | test / trim-cap soak | CRUD | `tests/test_db.py:95-106` (`test_insert_prunes_old_entries`); `tests/test_db.py:411-427` (`test_pruning_preserves_pending_rows`) | exact |

## Pattern Assignments

### `triggarr/config.py` — `_atomic_toml_write` SAFETY-04 patch

**Analog:** self — the function in its current shape at `triggarr/config.py:92-119`.

**Current code to patch** (`config.py:102-119`):
```python
    dir_fd = None
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        # fsync the directory to ensure rename is durable
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
```

**Imports already present in file** (`config.py:1-16`) — no new imports needed (`contextlib`, `os`, `logger` already imported):
```python
import contextlib
import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

import tomli_w
from loguru import logger
```

**Existing loguru-call pattern in this file** (`config.py:230-233`) — copy this `{name}=value` formatter style for the new error log:
```python
logger.warning(
    "Default config written to {path} -- edit the config file and restart Triggarr",
    path=config_path,
)
```

**Patch shape (RESEARCH-recommended, lines 247-303):**
```python
    except OSError as exc:
        logger.error("Config write failed: {path} - {exc}", path=path, exc=exc)
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass  # expected: temp already gone
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
```

**Invariants to preserve:**
- `FileNotFoundError` from `os.unlink(tmp_path)` cleanup → silently suppressed (no log).
- Any other `OSError` from cleanup → logged then suppressed (continue to `raise`).
- `OSError` from `os.replace` / `os.fsync` → logged with path, then re-raised.
- TypeError / ValueError from `tomli_w.dump` → not logged here (still propagates).
- The outer `finally: os.close(dir_fd)` block is unchanged.

**Note:** RESEARCH Pitfall 6 (lines 492-495) explicitly calls out the existing `contextlib.suppress(OSError)` as too broad. The replacement uses explicit `try/except FileNotFoundError: pass` per the user's global CLAUDE.md rule "Never use bare `except:` — always catch specific exceptions" and SIM ruff rule preference for explicit exception types over `contextlib.suppress` when the body has more than one statement.

---

### `triggarr/config.py` — `ensure_config` friendly TOML-load handler

**Analog:** No exact analog exists for "wrap startup load + log friendly error + exit(1)" in this codebase. **Closest precedents:**

1. **Existing warn-then-exit pattern at `config.py:228-234`** (the missing-config branch — copy this exit shape):
```python
    if not config_path.exists():
        generate_default_config(config_path)
        logger.warning(
            "Default config written to {path} -- edit the config file and restart Triggarr",
            path=config_path,
        )
        sys.exit(1)
```

2. **Existing migration backup-path pattern at `config.py:236-239`** (copy this "log info about backup path" shape):
```python
    migrated = detect_and_migrate_v22(config_path)
    if migrated:
        backup_path = config_path.with_suffix(".toml.bak")
        logger.info("v2.2 config backed up to {path}", path=backup_path)
```

3. **`with_suffix(...-backup)` precedent at `db.py:64`** — same `Path.with_suffix(...)` idiom for backup file naming.

4. **Loguru error logging idiom used throughout** (RESEARCH 503-510):
```python
logger.error("...", arg=value, exc=exc)
```

**Patch shape (RESEARCH-recommended, lines 326-366):**
```python
def ensure_config(config_path: Path) -> Settings:
    if not config_path.exists():
        generate_default_config(config_path)
        logger.warning(
            "Default config written to {path} -- edit the config file and restart Triggarr",
            path=config_path,
        )
        sys.exit(1)

    try:
        migrated = detect_and_migrate_v22(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)

    if migrated:
        backup_path = config_path.with_suffix(".toml.bak")
        logger.info("v2.2 config backed up to {path}", path=backup_path)

    try:
        return load_settings(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)


def _log_corrupt_config_and_exit(config_path: Path, exc: Exception) -> None:
    backup_path = config_path.with_suffix(".toml.bak")
    logger.error(
        "Failed to parse config file {path}: {exc}",
        path=config_path, exc=exc,
    )
    if backup_path.exists():
        logger.error(
            "A backup is available at {backup} -- to restore: cp {backup} {path}",
            backup=backup_path, path=config_path,
        )
    else:
        logger.error(
            "No automatic backup exists. Restore from your own backup or "
            "delete {path} to regenerate the default template.",
            path=config_path,
        )
    sys.exit(1)
```

**Important constraints:**
- `tomllib.TOMLDecodeError` is a subclass of `ValueError` (RESEARCH line 371). Catch it specifically — do NOT widen to `ValueError`.
- `UnicodeDecodeError` is raised separately by `tomllib.load` for invalid UTF-8 bytes (RESEARCH 370, Assumption A2).
- Do NOT catch `OSError` here (RESEARCH Open Question 3, lines 710-712) — permission-denied at startup is fatal and should keep its traceback.
- Loguru works before `setup_logging()` is invoked (RESEARCH Pitfall 5, lines 487-490; Assumption A3) — default stderr handler delivers the message.
- Both `tomllib.load` call sites (`config.py:144-145` inside `detect_and_migrate_v22`, and `config.py:182-184` inside `load_settings`) are wrapped at the **caller** boundary in `ensure_config` rather than inside the loader functions, preserving the leaf functions' clean signatures.

---

### `triggarr/db.py` — documentation comment for SAFETY-01

**Analog:** Existing inline comment at `db.py:338`:
```python
# Tracking-aware pruning (DEBT-03): only prune resolved rows, preserve pending (outcome='searched')
```

**Patch shape:** The comment is already present and correct. Either (a) leave as-is and treat SAFETY-01 as "already implemented + tested", or (b) extend the docstring at `db.py:329` to make the contract explicit. Recommended (b):

**Current docstring fragment** (`db.py:329`):
```python
        max_rows: Maximum resolved rows to keep (pending rows are exempt).
```

**Suggested expansion** (still inside the existing docstring — same loguru/style conventions don't apply, this is just a docstring):
```python
        max_rows: Maximum resolved rows to keep after insert.
            Pending rows (outcome='searched') are exempt from this cap
            and bounded only by ``tracking_window_minutes`` (default 60).
            Trimming runs inside the same transaction as the insert, so the
            cap holds immediately on the next read.
```

Per RESEARCH 237-239: "Optionally: document in a comment that pending rows are exempt and bounded by the tracking window. This is operator-relevant." No SQL change required.

---

### `tests/test_config.py` — TEST-02 + SAFETY-04 cases

**Analog:** `tests/test_config.py:670-680` (test_atomic_toml_write_cleans_temp_on_failure) and `tests/test_config.py:688-694` (test_toml_syntax_error_raises_decode_error), and `tests/test_startup.py:261-267` (loguru sink capture).

**Imports already present in test_config.py** (`test_config.py:1-22`) — only need to add `io`, `sys`, and `logger` from loguru:
```python
from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w
from pydantic import ValidationError

from triggarr.config import (
    _atomic_toml_write,
    _is_v22_format,
    _migrate_v22_to_v23,
    detect_and_migrate_v22,
    ensure_config,
    generate_default_config,
    load_settings,
)
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
```

**New imports needed in test_config.py:**
```python
import io
import sys  # only if using SystemExit assertions cleanly
from loguru import logger
```

**Existing atomic-write-failure test pattern to copy** (`test_config.py:670-680`):
```python
def test_atomic_toml_write_cleans_temp_on_failure(tmp_path: Path) -> None:
    """_atomic_toml_write removes temp file when tomli_w.dump raises (BUG-06)."""
    config_file = tmp_path / "test.toml"

    with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("bad data")), \
         pytest.raises(TypeError):
        _atomic_toml_write(config_file, {"key": "value"})

    # No temp files should remain in the directory
    remaining = list(tmp_path.glob("*.tmp"))
    assert remaining == [], f"Temp files should be cleaned up, found: {remaining}"
```

Use this exact shape for the SAFETY-04 tests — `with patch(...), pytest.raises(...):` (no `@patch` decorators; RESEARCH State of the Art line 732).

**Existing TOML-decode-error test pattern to extend** (`test_config.py:688-694`):
```python
def test_toml_syntax_error_raises_decode_error(tmp_path: Path) -> None:
    """Broken TOML syntax (missing closing bracket) raises TOMLDecodeError."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general\nlog_level = "info"')

    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings(config_file)
```

This test stays — it validates the low-level loader. **New tests target `ensure_config`** (the caller wrapping).

**Loguru capture pattern to copy** (`tests/test_startup.py:261-267`):
```python
sink = io.StringIO()
handler_id = logger.add(sink, format="{message}", level="WARNING")
try:
    result = await sonarr.detect_api_version()
finally:
    logger.remove(handler_id)
assert "version detection failed" in sink.getvalue()
```

For TEST-02, capture at `ERROR` level (the friendly handler uses `logger.error`). The `try/finally` to remove the handler is mandatory — leaking sinks across tests is a known loguru gotcha.

**Test cases to add (RESEARCH 594-627, 642-678):**

1. **`test_ensure_config_logs_friendly_error_on_toml_syntax_error`** — write `[general\nlog_level = "info"` (missing `]`) to file, call `ensure_config`, assert `pytest.raises(SystemExit)` with `exc_info.value.code == 1`, sink contains `str(config_path)` and "parse"/"decode".

2. **`test_ensure_config_logs_friendly_error_on_invalid_utf8`** — write `b"\xff\xfe\x00garbage"` via `write_bytes`, same assertions.

3. **`test_ensure_config_mentions_backup_path_when_backup_exists`** — pre-create `triggarr.toml.bak`, corrupt main file, assert sink contains the backup path string.

4. **`test_ensure_config_mentions_no_backup_when_absent`** — corrupt file, no .bak, assert sink contains "No automatic backup".

5. **`test_atomic_toml_write_logs_cleanup_oserror`** — `patch tomli_w.dump → TypeError`, `patch os.unlink → PermissionError`, `pytest.raises(TypeError)`, assert sink contains "Failed to clean up temp file".

6. **`test_atomic_toml_write_suppresses_filenotfound_silently`** — `patch tomli_w.dump → TypeError`, `patch os.unlink → FileNotFoundError`, `pytest.raises(TypeError)`, assert sink does NOT contain "Failed to clean up".

7. **`test_atomic_toml_write_logs_os_replace_failure`** — `patch os.replace → OSError("EROFS")`, `pytest.raises(OSError)`, assert sink contains "Config write failed" and "EROFS".

All `patch` targets use the **import-path** form (e.g. `triggarr.config.tomli_w.dump`, `triggarr.config.os.unlink`, `triggarr.config.os.replace`) — copy the path style from `test_config.py:674` (`triggarr.config.tomli_w.dump`).

---

### `tests/test_web.py` — TEST-03 concurrent PUT

**Analog:** `tests/test_web.py:584-598` (`test_search_now_rate_limit_concurrent_protection`) — closest concurrency-style test, but uses sync `TestClient` (RESEARCH Pitfall 2 line 471: cannot produce true concurrency). For genuine concurrency the new test must use `httpx.AsyncClient(transport=ASGITransport(...))`.

**Existing concurrent-rate-limit test (for shape only, NOT for driver)** (`test_web.py:584-598`):
```python
def test_search_now_rate_limit_concurrent_protection(client, test_app):
    """Two rapid POST /api/search-now/radarr calls: second returns 429 (DRSEC-03).

    Validates that the re-check inside search_lock prevents concurrent bypass.
    """
    with patch(
        "triggarr.web.routes.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch("triggarr.web.routes.save_state"):
        resp1 = client.post("/api/search-now/radarr/Default")
        assert resp1.status_code == 200, f"First request should succeed, got {resp1.status_code}"

        resp2 = client.post("/api/search-now/radarr/Default")
        assert resp2.status_code == 429, f"Second request within rate window should be 429, got {resp2.status_code}"
        assert "Rate limited" in resp2.text
```

Note `with patch("triggarr.web.routes.X", ...)` — the patch targets `triggarr.web.routes._atomic_toml_write` for the new test (the import binding in `routes.py`).

**ASGITransport precedent (from another module — `tests/test_startup.py:257`):**
```python
transport = httpx.MockTransport(_handler)
async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
    sonarr = SonarrClient("http://test", "fake-key")
    sonarr._client = client
```

Note: `MockTransport` is used there for mocking *outbound* HTTP; `ASGITransport` is used for driving a FastAPI app from the test. The shape is similar (`async with httpx.AsyncClient(transport=..., base_url="http://test") as ac:`).

**Existing `test_app` fixture to reuse** (`test_web.py:25-118`) — it already provides:
- `app.state.search_lock = asyncio.Lock()` (line 112)
- `app.state.config_path = tmp_path / "triggarr.toml"` (line 108)
- Full settings, scheduler mock, clients, db connection
- Lives inside `async with aiosqlite.connect(db_path) as db:` (line 35), so the concurrent test must run inside the same fixture scope.

**Valid form payload to copy** (use `test_web.py:684-712` `test_save_settings_with_new_fields` data dict as template — all fields the Pydantic Settings model requires):
```python
data={
    "log_level": "info",
    "hard_max_per_cycle": "0",
    "max_history_rows": "5000",
    "request_timeout": "60",
    "page_size": "100",
    "tracking_window_minutes": "120",
    "radarr__Default__url": "http://radarr:7878",
    "radarr__Default__api_key": "",
    "radarr__Default__enabled": "on",
    "radarr__Default__search_interval": "30",
    "radarr__Default__search_missing_count": "5",
    "radarr__Default__search_cutoff_count": "5",
    "radarr__Default__missing_tag": "",
    "radarr__Default__cutoff_tag": "",
    "sonarr__Default__url": "http://sonarr:8989",
    "sonarr__Default__api_key": "",
    "sonarr__Default__enabled": "on",
    "sonarr__Default__search_interval": "30",
    "sonarr__Default__search_missing_count": "5",
    "sonarr__Default__search_cutoff_count": "5",
    "sonarr__Default__missing_tag": "",
    "sonarr__Default__cutoff_tag": "",
}
```

**Shape of the new test (RESEARCH 388-419):**
```python
async def test_concurrent_settings_save_serialized(test_app, tmp_path):
    """Two concurrent POST /settings cannot interleave: SAFETY-05.

    Uses httpx.AsyncClient + ASGITransport because TestClient is synchronous
    and cannot fire two truly concurrent requests on the same event loop.
    """
    import time
    import httpx
    from httpx import ASGITransport
    from triggarr.config import _atomic_toml_write as real_write

    call_order: list[str] = []

    def slow_write(path, data):
        call_order.append("enter")
        time.sleep(0.05)  # block the executor thread to force lock contention
        call_order.append("exit")
        return real_write(path, data)

    form_a = {...}  # valid form, log_level=info (full payload above)
    form_b = {...}  # valid form, log_level=debug

    with patch("triggarr.web.routes._atomic_toml_write", side_effect=slow_write):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            r1, r2 = await asyncio.gather(
                ac.post("/settings", data=form_a, follow_redirects=False),
                ac.post("/settings", data=form_b, follow_redirects=False),
            )

    assert r1.status_code == 303
    assert r2.status_code == 303
    assert call_order == ["enter", "exit", "enter", "exit"], (
        f"Lock did not serialize writes: {call_order}"
    )
```

**Critical notes from RESEARCH:**
- Use `time.sleep`, NOT `asyncio.sleep` (RESEARCH line 422). `_atomic_toml_write` is dispatched via `run_in_executor`, runs in a thread pool — blocking the thread (not the event loop) is what produces realistic contention.
- The test is `async def`, so `pytest-asyncio` (asyncio_mode=auto, pyproject.toml:38) runs it without a decorator.
- Patch target is `triggarr.web.routes._atomic_toml_write` — the import binding in routes.py, not the source in config.py. Copy this target style from `test_web.py:775`.

---

### `tests/test_db.py` — SAFETY-01 soak test

**Analog:** `tests/test_db.py:95-106` (`test_insert_prunes_old_entries`) and `tests/test_db.py:411-427` (`test_pruning_preserves_pending_rows`).

**Existing trim test to extend** (`test_db.py:95-106`):
```python
async def test_insert_prunes_old_entries(tmp_path):
    """Inserting beyond max_rows resolved entries prunes the oldest resolved rows."""
    db, db_path = await _init_test_db(tmp_path)

    # Insert 510 entries with outcome='failed' (resolved, so prunable)
    for i in range(510):
        await insert_search_entry(db, "Radarr", "missing", f"Movie {i}", outcome="failed", max_rows=500)

    async with db.execute("SELECT COUNT(*) FROM search_history") as cursor:
        row = await cursor.fetchone()
    assert row[0] == 500
    await db.close()
```

**Existing pending-exempt test for invariant cross-check** (`test_db.py:411-427`):
```python
async def test_pruning_preserves_pending_rows(tmp_path):
    """Pruning does not delete rows with outcome='searched' even when over max_rows."""
    db, db_path = await _init_test_db(tmp_path)
    # Insert 5 pending (searched) rows
    for i in range(5):
        await insert_search_entry(db, "Radarr", "missing", f"Pending {i}", outcome="searched", max_rows=3)
    # Insert 5 resolved rows
    for i in range(5):
        await insert_search_entry(db, "Radarr", "missing", f"Resolved {i}", outcome="grabbed", max_rows=3)
    # Count: all 5 pending should survive, only 3 resolved should survive
    async with db.execute("SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'") as cursor:
        pending = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM search_history WHERE outcome != 'searched'") as cursor:
        resolved = (await cursor.fetchone())[0]
    assert pending == 5
    assert resolved == 3
    await db.close()
```

**Shape of the new soak test (RESEARCH line 238):**
```python
async def test_insert_caps_at_max_rows_over_large_soak(tmp_path):
    """Steady-state cap holds across 2x max_rows resolved inserts (SAFETY-01)."""
    db, db_path = await _init_test_db(tmp_path)
    max_rows = 1000

    for i in range(2 * max_rows):
        await insert_search_entry(
            db, "Radarr", "missing", f"Movie {i}", outcome="failed", max_rows=max_rows,
        )

    async with db.execute(
        "SELECT COUNT(*) FROM search_history WHERE outcome != 'searched'"
    ) as cursor:
        resolved = (await cursor.fetchone())[0]
    assert resolved == max_rows, f"Resolved rows should be capped at {max_rows}, got {resolved}"
    await db.close()
```

**Conventions to follow:**
- Use the `_init_test_db(tmp_path)` helper (`test_db.py:29-34`) — never reinvent the connect+migrate dance.
- `async def test_*` — no `@pytest.mark.asyncio` decorator (pyproject.toml `asyncio_mode = "auto"`).
- Always `await db.close()` at end (existing pattern at every test in this file).
- Use `async with db.execute(...) as cursor:` for queries (existing pattern at `test_db.py:103`, `421`, `423`).

## Shared Patterns

### Loguru sink capture in tests

**Source:** `tests/test_startup.py:261-267`
**Apply to:** All new tests asserting log content (test_config.py SAFETY-04 + TEST-02 cases)

```python
sink = io.StringIO()
handler_id = logger.add(sink, format="{message}", level="ERROR")
try:
    # call code under test
    ...
finally:
    logger.remove(handler_id)
assert "expected text" in sink.getvalue()
```

The `try/finally` to remove the handler is required — loguru sinks persist across tests if not cleaned up.

### `with patch(...)` context manager (no decorators)

**Source:** `tests/test_config.py:674`, `tests/test_web.py:589-592`, `tests/test_web.py:774-775`
**Apply to:** All new tests requiring mocks

```python
with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("bad data")), \
     pytest.raises(TypeError):
    _atomic_toml_write(config_file, {"key": "value"})
```

Per RESEARCH State of the Art line 732, this repo uses `with patch(...)` context managers, not `@patch` decorators. Maintain this consistency.

### Atomic write convention (already-correct pattern, do NOT duplicate)

**Source:** `triggarr/config.py:92-119` (`_atomic_toml_write`)
**Apply to:** Any future write that needs atomicity. **Do NOT introduce a second write path.** Note RESEARCH line 40: there is a near-duplicate inline tempfile dance in `generate_default_config` (config.py:187-211); leave it alone unless explicitly in scope (it is not in scope for phase 64).

### Loguru-only logging

**Source:** `triggarr/config.py:14` (`from loguru import logger`), used everywhere
**Apply to:** All new log lines

```python
logger.error("Message with {var} and {exc}", var=value, exc=exc)
```

Per `./CLAUDE.md`: "Loguru for logging with custom redacting sink (never print/logging module)". The redacting sink is set up via `setup_logging(...)` in `triggarr/logging.py`. Startup-time errors fire before that sink is installed — that's acceptable because no secrets are loaded yet (RESEARCH Pitfall 5, lines 487-490).

### Specific-exception handling (no bare except)

**Source:** Convention from user global CLAUDE.md and project CLAUDE.md
**Apply to:** Both `_atomic_toml_write` patch and `ensure_config` wrapper

- Catch `(tomllib.TOMLDecodeError, UnicodeDecodeError)` for friendly TOML errors. Do NOT widen to `ValueError`.
- Catch `FileNotFoundError` + `OSError` separately in cleanup. Do NOT use `except OSError as exc` to silently swallow.
- Do NOT use bare `except:` anywhere (ruff rule + CLAUDE.md).

### asyncio.Lock around config writes

**Source:** `triggarr/web/routes.py:573-577` (representative of all 8 call sites)
**Apply to:** No new call sites in this phase. All 8 existing call sites already follow this pattern (RESEARCH 80-99, Assumption A5):

```python
async with request.app.state.search_lock:
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = new_settings
```

The TEST-03 test validates that this serialization works. No production code changes required for SAFETY-05.

### async test naming (asyncio_mode=auto)

**Source:** `pyproject.toml:38` (`asyncio_mode = "auto"`) plus `tests/test_db.py`, `tests/test_web.py:655` etc.
**Apply to:** New TEST-03 in test_web.py and the SAFETY-01 soak test in test_db.py

```python
async def test_something(test_app, tmp_path):
    ...
```

No `@pytest.mark.asyncio` decorator. Reuse existing fixtures (`test_app`, `tmp_path`).

## No Analog Found

Files with no close match (planner should fall back to RESEARCH.md guidance):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All required patterns have at least a partial analog in the codebase. The closest "no analog" case is the `httpx.AsyncClient + ASGITransport` driver for TEST-03 — `MockTransport` is used in `tests/test_startup.py:257` and `tests/test_clients.py`, but no existing web test drives the full app via ASGI. RESEARCH 379-424 supplies the full sketch; flag the pattern in a comment for future tests. RESEARCH Assumption A4 (line 721) confirms HIGH confidence in the approach. |

## Metadata

**Analog search scope:** `/Users/julianamacbook/triggarr/triggarr/` and `/Users/julianamacbook/triggarr/tests/`
**Files scanned:** `config.py`, `db.py`, `web/routes.py`, `search/scheduler.py`, `__main__.py` (sources); `test_config.py`, `test_db.py`, `test_web.py`, `test_startup.py`, `test_clients.py` (tests)
**Pattern extraction date:** 2026-05-25
**Skills consulted:** None (project has `.claude/skills/aidesigner-frontend` only; not applicable to this Python hardening phase)
