# Phase 47: Test Hardening -- State & Search Edge Cases - Research

**Researched:** 2026-04-09
**Domain:** Python test hardening (pytest-asyncio, TOML config, SQLite, JSON state, search logic)
**Confidence:** HIGH

## Summary

Phase 47 adds edge-case tests for two domains: (1) corrupt/invalid persistent state recovery (TOML config, SQLite DB, JSON state files, config migration), and (2) search logic boundary conditions (empty queues, tag filtering edge cases, batch/cursor overflow). The codebase already has substantial test infrastructure (586 tests passing) with existing partial coverage for several requirements.

The audit identified that SRCH-04 (batch exceeds available) and SRCH-05 (cursor past end) are likely FULLY covered by existing `slice_batch` unit tests. STATE-03 has a single test for corrupt JSON but needs expansion. SRCH-01 and SRCH-03 have partial coverage. The remaining requirements (STATE-01, STATE-02, STATE-04, SRCH-02) have no existing coverage.

**Primary recommendation:** Audit existing tests first to avoid duplication, then add targeted tests for uncovered edge cases. Most new tests are simple unit tests; only SQLite corruption requires more setup.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATE-01 | Recovery from broken TOML config (syntax errors, missing fields, wrong types) | `load_settings()` calls `tomllib.load()` which raises `TOMLDecodeError` on syntax errors, and `Settings(**data)` raises `pydantic.ValidationError` on bad types/missing fields. Currently NO test covers these failure modes -- `ensure_config` calls `load_settings` and has no error handling for parse failures. Tests need to verify the app does not crash. |
| STATE-02 | Recovery from corrupt SQLite (locked DB, schema mismatch) | `init_db()` runs migrations via `aiosqlite`. No existing tests for locked DB or schema mismatch. Need to test behavior when DB file is not a valid SQLite file, when DB is locked by another connection, or when schema_version table has unexpected version. |
| STATE-03 | Recovery from invalid JSON state file (truncated, wrong structure) | `test_state_corrupt_recovers_to_defaults` exists for invalid JSON text. Need additional tests for: truncated JSON (partial write), wrong top-level structure (list instead of dict), wrong nested structure (radarr value is string instead of dict), empty file. |
| STATE-04 | Config migration handles unexpected starting state | `detect_and_migrate_v22` tests exist for happy path. Need tests for: partial v2.2 config (only radarr, no sonarr), unknown/extra fields in config, missing `[general]` section, config that is neither v2.2 nor v2.3 format. |
| SRCH-01 | Correct behavior with empty queues | `test_slice_batch_empty_list` exists for the utility function. Need integration-level tests: `run_radarr_cycle` with empty wanted-missing AND empty wanted-cutoff returns gracefully. |
| SRCH-02 | Correct behavior when all items filtered out by tags | No existing tests. Need tests where tag filter removes ALL items from both queues -- verify no searches attempted, cursor unchanged or reset to 0, no errors. |
| SRCH-03 | Graceful handling of tag resolution failure (configured tag doesn't exist) | `test_radarr_tag_resolution_failure_searches_all` and `test_sonarr_tag_resolution_failure_searches_all` exist -- these test fail-open behavior. Also `test_tag_warning_state_stored_when_tag_not_found_radarr/sonarr` exist. May need Lidarr variant or additional edge cases (e.g., tag fetch network error already covered by BUG-08 tests). |
| SRCH-04 | Correct behavior when batch size exceeds available items | `test_slice_batch_batch_larger_than_remaining` covers this at unit level. Integration test may not be needed -- verify and document. |
| SRCH-05 | Correct behavior when cursor position exceeds queue length | `test_slice_batch_cursor_past_end` covers this at unit level. Integration test may not be needed -- verify and document. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys
- Loguru for logging with custom redacting sink
- Atomic file writes (write-then-rename) for config and state
- pytest-asyncio with asyncio_mode=auto
- `uv run pytest tests/ -x -q` to run tests
- `uv run ruff check triggarr/ tests/` to lint

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | (installed) | Test framework | Project standard |
| pytest-asyncio | (installed) | Async test support | asyncio_mode=auto |
| aiosqlite | (installed) | SQLite async driver | Used by DB module |
| pydantic | (installed) | Config validation | Settings model |
| loguru | (installed) | Logging | Log capture in tests |

[VERIFIED: pyproject.toml and existing test imports]

**Installation:** None needed -- all dependencies already present.

## Architecture Patterns

### Existing Test Structure
```
tests/
    conftest.py          # make_settings(), default_state() helpers
    test_state.py        # JSON state load/save/migration (17 tests)
    test_config.py       # TOML config load/validation/migration (38 tests)
    test_db.py           # SQLite init/CRUD/migration (30+ tests)
    test_search.py       # Search engine functions + cycle orchestration (80+ tests)
```

### Pattern: State Recovery Test
**What:** Test that corrupt/invalid persistent files recover gracefully to defaults
**When to use:** All STATE-* requirements
**Example:**
```python
# Source: existing test_state.py pattern
def test_state_corrupt_recovers_to_defaults(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text("not valid json")
    state = load_state(state_file)
    assert state["radarr"] == {}
```

### Pattern: Cycle Integration Test with Mocked Client
**What:** Test full search cycle with AsyncMock client returning edge-case data
**When to use:** All SRCH-* requirements
**Example:**
```python
# Source: existing test_search.py pattern
async def test_run_radarr_cycle_empty_queues(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()
    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert client.search_movies.call_count == 0
    await db.close()
```

### Anti-Patterns to Avoid
- **Duplicating existing coverage:** SRCH-04 and SRCH-05 have unit-level coverage. Do not write redundant integration tests unless they test a different code path.
- **Testing implementation details:** Test observable behavior (recovery, graceful handling), not internal implementation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SQLite lock simulation | Manual file locking | `aiosqlite` with two connections + WAL mode checks | Realistic simulation |
| TOML syntax errors | String manipulation | Write known-bad TOML strings to files | Direct and reliable |
| Async test boilerplate | Manual event loop setup | pytest-asyncio auto mode | Already configured |

## Existing Coverage Audit

This is the critical analysis the planner needs. Each requirement is evaluated against existing tests.

### STATE-01: Broken TOML Config -- NO existing coverage
- `load_settings()` in config.py does `tomllib.load(f)` then `Settings(**data)` with NO try/except
- `ensure_config()` calls `load_settings()` also with no error handling for parse failures
- Tests needed: TOML syntax error, missing required field (api_key), wrong type (enabled = "yes" instead of bool)
- Key insight: `tomllib.load()` raises `tomllib.TOMLDecodeError` on syntax errors. Pydantic raises `ValidationError` on schema issues. Neither is caught in `load_settings()` -- tests should verify the exceptions propagate cleanly (not that they're caught), since the app currently lets them crash at startup. The phase requirement says "recovery" so tests may just verify the error types and that no data loss occurs.

### STATE-02: Corrupt SQLite -- NO existing coverage
- `init_db()` runs CREATE TABLE IF NOT EXISTS and migrations
- Tests needed: DB file is not valid SQLite (write random bytes), DB locked by another process, schema_version at unexpected value
- `aiosqlite.connect()` to a non-SQLite file will raise `aiosqlite.Error` (wrapping sqlite3.DatabaseError)

### STATE-03: Invalid JSON State -- PARTIAL coverage
- `test_state_corrupt_recovers_to_defaults` covers "not valid json" text
- Missing: truncated JSON (`{"radarr":`), wrong structure (list `[]`), empty file, wrong nested types (radarr value is string)
- All should recover to defaults via the existing `json.JSONDecodeError` catch in `load_state()`

### STATE-04: Config Migration Unexpected State -- PARTIAL coverage
- v2.2-to-v2.3 migration tests exist for happy paths
- Missing: partial v2.2 (only radarr section, no sonarr), unknown extra fields, missing [general], config that has some nested and some flat sections
- `_is_v22_format()` and `_migrate_v22_to_v23()` are pure functions -- easy to test edge cases

### SRCH-01: Empty Queues -- PARTIAL coverage
- `test_slice_batch_empty_list` covers the utility function
- No integration test for `run_radarr_cycle` or `run_sonarr_cycle` with empty queues from the API
- Test should verify: no search calls made, cursor stays at 0, no errors, connected=True

### SRCH-02: All Items Filtered by Tags -- NO existing coverage
- No test where tag filtering removes ALL items
- Test should verify: tag filter resolves correctly, all items filtered out, no searches attempted, cursor wraps to 0 (since slice_batch on empty list returns cursor=0)

### SRCH-03: Nonexistent Tag -- LIKELY FULLY covered
- `test_radarr_tag_resolution_failure_searches_all` -- Radarr fail-open
- `test_sonarr_tag_resolution_failure_searches_all` -- Sonarr fail-open
- `test_tag_warning_state_stored_when_tag_not_found_radarr` -- warning stored
- `test_tag_warning_state_stored_when_tag_not_found_sonarr` -- warning stored
- `test_radarr_tag_fetch_failure_no_tag_not_found_warning` -- BUG-08
- Missing: Lidarr nonexistent tag test (only has `test_lidarr_cycle_missing_tag_filters` for happy path)

### SRCH-04: Batch Size Exceeds Available -- FULLY covered
- `test_slice_batch_batch_larger_than_remaining`: items=[0,1,2], cursor=1, batch_size=10 -> batch=[1,2], new_cursor=0
- This is the exact edge case. The search cycle functions call `slice_batch()` which handles this correctly.

### SRCH-05: Cursor Past End -- FULLY covered
- `test_slice_batch_cursor_past_end`: items=[0..4], cursor=99, batch_size=2 -> batch=[0,1], new_cursor=2
- This is the exact edge case. Cursor resets to 0 and slices from the beginning.

## Common Pitfalls

### Pitfall 1: Testing Error Handling That Doesn't Exist Yet
**What goes wrong:** STATE-01 requires "recovery" from broken TOML, but `load_settings()` currently has NO try/except -- it will crash the app on bad TOML.
**Why it happens:** The requirement says "tests verify recovery" but the code may not have recovery logic yet.
**How to avoid:** Tests should verify current behavior (exception type, no partial state corruption) AND any new recovery behavior added. The plan should decide: do we add recovery logic, or just test that exceptions propagate cleanly?
**Warning signs:** Tests that can never pass against current code without source changes.

### Pitfall 2: Duplicating Existing Tests
**What goes wrong:** Writing tests for SRCH-04 and SRCH-05 that duplicate existing `slice_batch` tests.
**Why it happens:** Not reading existing test files before writing new ones.
**How to avoid:** Planner should mark SRCH-04 and SRCH-05 as already covered, only add integration-level tests if there is a gap between the unit test and the cycle function.

### Pitfall 3: SQLite Lock Tests Being Flaky
**What goes wrong:** Tests that depend on OS-level file locking can be flaky across platforms.
**Why it happens:** SQLite locking behavior varies between macOS and Linux.
**How to avoid:** Use `aiosqlite` with explicit `PRAGMA busy_timeout` or mock the database error rather than trying to create real lock contention.

## Code Examples

### Broken TOML Config Test
```python
# Verify that syntax-error TOML raises TOMLDecodeError (not a random crash)
import tomllib
def test_toml_syntax_error_raises_decode_error(tmp_path):
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general\nlog_level = 'info'")  # missing closing bracket
    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings(config_file)
```

### Empty Queue Integration Test
```python
async def test_run_radarr_cycle_empty_queues(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()
    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert client.search_movies.call_count == 0
    assert result["radarr"]["Default"]["missing_cursor"] == 0
    assert result["radarr"]["Default"]["connected"] is True
    await db.close()
```

### All Items Filtered by Tags
```python
async def test_radarr_cycle_all_filtered_by_tag(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="triggarr")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [99]},  # wrong tag
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [100]},  # wrong tag
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()
    instance_config.missing_tag = "triggarr"
    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert client.search_movies.call_count == 0  # nothing to search
    assert result["radarr"]["Default"]["missing_eligible"] == 0
    await db.close()
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml (asyncio_mode=auto) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-01 | TOML syntax/missing/wrong-type recovery | unit | `uv run pytest tests/test_config.py -x -q -k "broken_toml or syntax_error or wrong_type or missing_field"` | No -- Wave 0 |
| STATE-02 | SQLite corrupt/locked/mismatch recovery | unit/integration | `uv run pytest tests/test_db.py -x -q -k "corrupt or locked or mismatch"` | No -- Wave 0 |
| STATE-03 | JSON state truncated/wrong-structure recovery | unit | `uv run pytest tests/test_state.py -x -q -k "truncated or wrong_structure or empty_file"` | Partial |
| STATE-04 | Config migration unexpected state | unit | `uv run pytest tests/test_config.py -x -q -k "migration_unexpected or partial_v22 or unknown_fields"` | No -- Wave 0 |
| SRCH-01 | Empty queue cycle behavior | integration | `uv run pytest tests/test_search.py -x -q -k "empty_queue"` | No -- Wave 0 |
| SRCH-02 | All items filtered by tags | integration | `uv run pytest tests/test_search.py -x -q -k "all_filtered"` | No -- Wave 0 |
| SRCH-03 | Nonexistent tag handling | integration | `uv run pytest tests/test_search.py -x -q -k "tag_resolution_failure"` | Mostly covered |
| SRCH-04 | Batch exceeds available | unit | `uv run pytest tests/test_search.py -x -q -k "batch_larger"` | Fully covered |
| SRCH-05 | Cursor past end | unit | `uv run pytest tests/test_search.py -x -q -k "cursor_past_end"` | Fully covered |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
None -- existing test infrastructure (conftest.py, pytest-asyncio auto mode, tmp_path fixtures) covers all needs. No new framework or fixture setup required.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | STATE-01 "recovery" means verifying exceptions propagate cleanly (not adding try/except to source code) | Phase Requirements | If recovery logic needs to be ADDED to config.py, the phase scope expands beyond test-only |
| A2 | SRCH-04 and SRCH-05 are fully covered by existing slice_batch tests | Existing Coverage Audit | If integration-level coverage is required, 2-4 more tests needed |

## Open Questions (RESOLVED)

1. **STATE-01: Does "recovery" require source code changes?** RESOLVED: Tests verify exceptions propagate cleanly (TOMLDecodeError, ValidationError). No source code changes needed — "recovery" means confirming clean failure, not adding try/except.
   - What we know: `load_settings()` has no try/except for TOMLDecodeError or ValidationError. The app will crash on startup with bad TOML.
   - Resolution: Tests verify current behavior (clean exception propagation, no data loss). Recovery logic is beyond "test hardening" scope.

2. **STATE-02: How deep should SQLite corruption testing go?** RESOLVED: Test both actual file corruption (256 random bytes → aiosqlite.DatabaseError) and locked DB (PRAGMA busy_timeout=0 → OperationalError).
   - What we know: `init_db()` creates tables and runs migrations. No existing error handling for corrupt DB files.
   - Resolution: Test actual corrupt file (write garbage bytes) and locked DB scenario. Both use real file operations, not mocks.

## Sources

### Primary (HIGH confidence)
- Codebase: `triggarr/state.py` -- JSON state load/save with atomic writes and migration
- Codebase: `triggarr/config.py` -- TOML config loading, migration, validation
- Codebase: `triggarr/db.py` -- SQLite init, migration, CRUD
- Codebase: `triggarr/search/engine.py` -- Search cycle orchestration, tag filtering, batch slicing
- Codebase: `tests/test_state.py` -- 17 existing state tests
- Codebase: `tests/test_config.py` -- 38 existing config tests
- Codebase: `tests/test_search.py` -- 80+ existing search tests
- Codebase: `tests/test_db.py` -- 30+ existing DB tests

### Secondary (MEDIUM confidence)
- Python stdlib docs: `tomllib.TOMLDecodeError` behavior [ASSUMED from Python 3.11 stdlib]
- aiosqlite error handling: wraps sqlite3.DatabaseError [ASSUMED from library behavior]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new deps
- Architecture: HIGH -- follows existing test patterns exactly
- Pitfalls: HIGH -- based on direct codebase analysis
- Existing coverage audit: HIGH -- based on reading every relevant test file

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- test patterns unlikely to change)
