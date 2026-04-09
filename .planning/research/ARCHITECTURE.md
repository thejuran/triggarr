# Architecture Research: Community Health Files & Test Hardening

**Domain:** Search automation daemon -- open-source readiness and failure mode testing
**Researched:** 2026-04-09
**Confidence:** HIGH (based on full codebase audit of existing test patterns and .github structure)

## Current Architecture (Baseline)

The existing architecture is stable from v2.3. This milestone adds no new runtime components -- it adds static repository files and test coverage for existing error handling paths.

### Existing Error Handling Patterns

The codebase has a mature, consistent error handling strategy:

| Component | Error Pattern | Catch Scope | Tested? |
|-----------|--------------|-------------|---------|
| `clients/base.py` `_request_with_retry` | Retry once on `httpx.HTTPStatusError` / `httpx.TransportError` | Per-request | Partially (retry + reraise tested, not all transport subtypes) |
| `clients/base.py` `validate_connection` | Typed dispatch: 401 vs ConnectError vs Timeout vs ValidationError | Per-connection | Yes (all 4 branches) |
| `search/engine.py` cycle functions | `(httpx.HTTPError, pydantic.ValidationError)` for fetch abort | Per-cycle | Yes (ConnectError tested, not HTTPStatusError or ValidationError) |
| `search/engine.py` per-item search | `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` | Per-item | Partially (ConnectError and Timeout, not aiosqlite.Error or OSError) |
| `tracking.py` | `(httpx.HTTPError, pydantic.ValidationError)` per-item group | Per-tracking-group | Yes (ConnectError + HTTPStatusError) |
| `config.py` `_atomic_toml_write` | Generic `Exception` with temp file cleanup | Per-write | Yes (failure cleanup tested) |
| `config.py` `load_settings` | `tomllib.TOMLDecodeError` on corrupt config | Per-load | NOT tested |
| `state.py` `load_state` | `(json.JSONDecodeError, OSError)` on corrupt state | Per-load | Yes (corrupt JSON recovery) |
| `db.py` `run_migrations` | `sqlite3.OperationalError` suppression in migration | Per-migration | Yes (OperationalError suppression) |
| `search/engine.py` `_sanitize_exc` | Type-based dispatch to avoid leaking internals | Per-exception | Yes (HTTP status + timeout) |

### Existing Test Organization

```
tests/
  conftest.py            -- make_settings(), default_state() factories
  test_changelog.py      -- Changelog parsing
  test_clients.py        -- ArrClient base + subclass behavior (779 lines)
  test_config.py         -- TOML loading, migration, atomic writes (688 lines)
  test_config_dir.py     -- TRIGGARR_CONFIG_DIR env var handling
  test_correlation.py    -- Grab correlation logic
  test_db.py             -- SQLite CRUD, migrations (1020 lines)
  test_log_buffer.py     -- Log buffer ring buffer
  test_logging.py        -- Loguru redaction sink
  test_middleware.py      -- CSRF middleware
  test_root_path.py      -- Reverse proxy support
  test_scheduler.py      -- APScheduler job wiring
  test_search.py         -- Engine functions + cycle orchestration (2205 lines)
  test_startup.py        -- Connection validation, banner
  test_state.py          -- State load/save, corruption recovery
  test_tracking.py       -- Tracking orchestrator
  test_update_check.py   -- GitHub release check
  test_validation.py     -- Input validation
  test_web.py            -- FastAPI route tests
```

**Key observation:** Tests are organized by module (one test file per source module). Unhappy-path tests are mixed alongside happy-path tests in the same files. This pattern should continue -- do NOT create separate "unhappy path" test files.

### Existing .github Structure

```
.github/
  workflows/
    ci.yml       -- pytest + ruff + Docker build
    release.yml  -- GHCR publishing
```

No issue templates, no ISSUE_TEMPLATE directory, no FUNDING.yml, no CONTRIBUTING.md, no SECURITY.md.

## Integration Points for v2.4

### Community Health Files (Static Files -- No Runtime Impact)

These files are purely additive. They do not touch any runtime code paths.

| File | Location | Integration |
|------|----------|-------------|
| `CONTRIBUTING.md` | Repo root | References `uv sync --extra dev`, `pytest`, `ruff` from CLAUDE.md conventions |
| `SECURITY.md` | Repo root | Documents existing security model (SecretStr, CSRF, SSRF, redacting sink) |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | `.github/ISSUE_TEMPLATE/` | YAML form (not markdown template) |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | `.github/ISSUE_TEMPLATE/` | YAML form (not markdown template) |
| `.github/ISSUE_TEMPLATE/config.yml` | `.github/ISSUE_TEMPLATE/` | Controls template chooser (link to Discussions) |

### Unhappy-Path Tests (Test Files Only -- No Runtime Changes)

New tests target existing error handling code that lacks coverage. No source code modifications required.

## Component Details

### 1. Issue Templates (`.github/ISSUE_TEMPLATE/`)

**Structure:** Use YAML form templates (not legacy markdown templates). YAML forms provide structured input with dropdowns, checkboxes, and required fields -- better signal-to-noise than freeform markdown.

**Required files:**

```
.github/
  ISSUE_TEMPLATE/
    bug_report.yml        -- Bug report form
    feature_request.yml   -- Feature request form
    config.yml            -- Template chooser config
```

**`config.yml` pattern:**
```yaml
blank_issues_enabled: false
contact_links:
  - name: Question / Discussion
    url: https://github.com/thejuran/triggarr/discussions
    about: Ask questions or discuss ideas
```

Setting `blank_issues_enabled: false` forces users through templates, improving issue quality.

**`bug_report.yml` fields:**
- Description (required textarea)
- Steps to reproduce (required textarea)
- Expected vs actual behavior (required textarea)
- Triggarr version (required input -- from Docker tag or `triggarr --version`)
- Deployment method (dropdown: Docker Compose, Docker run, bare Python)
- Radarr/Sonarr versions (optional input)
- Relevant log output (optional textarea, render as code block)
- Config snippet (optional textarea, render as code block, with warning to redact API keys)

**`feature_request.yml` fields:**
- Problem description (required textarea -- "what problem does this solve?")
- Proposed solution (required textarea)
- Alternatives considered (optional textarea)
- Additional context (optional textarea)

### 2. CONTRIBUTING.md

**Integration points with existing tooling:**
- Dev setup: `uv sync --extra dev` (from pyproject.toml)
- Test command: `uv run pytest tests/ -x -q` (from CLAUDE.md)
- Lint command: `uv run ruff check triggarr/ tests/` (from CLAUDE.md)
- CSS dev: `uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch`
- Docker build: `docker build -t triggarr:local .`
- Code style: ruff with E, F, I, UP, B, SIM rules, 120 char line length (from pyproject.toml)
- Async: pytest-asyncio with `asyncio_mode=auto`

**Sections:**
1. Fork and branch workflow (fork -> feature branch -> PR to main)
2. Dev environment setup (Python 3.11+, uv)
3. Running tests and linting
4. Code conventions (SecretStr, loguru, atomic writes)
5. PR expectations (tests pass, ruff clean, descriptive commit messages)

### 3. SECURITY.md

**Documents existing security model (no new security features):**
- Vulnerability reporting: private email or GitHub Security Advisory
- Security model summary: no auth (local network tool), SecretStr API key discipline, CSRF via Origin/Referer, SSRF validation, input clamping, loguru redacting sink
- Supported versions: latest release only
- Response timeline expectations

### 4. Repo Metadata

**GitHub topics** (set via `gh repo edit --add-topic`):
- radarr, sonarr, arr, automation, docker, fastapi, htmx, python, search, media-management

**GitHub Discussions:** Enable via `gh repo edit --enable-discussions` or GitHub web UI.

## Test Architecture: Unhappy-Path Coverage

### Test Organization Pattern

**Keep unhappy-path tests in existing files.** The codebase already mixes happy and unhappy tests in the same module-aligned file (e.g., `test_clients.py` has both `test_arr_client_sets_header` and `test_validate_connection_connect_error`). Adding new unhappy-path tests to existing files maintains this pattern and keeps related tests discoverable together.

**Grouping within files:** Use comment section headers (already established pattern):

```python
# ---------------------------------------------------------------------------
# Unhappy path: connection failures
# ---------------------------------------------------------------------------
```

### Fixture Strategy

**Existing pattern to follow:** The codebase uses `unittest.mock.AsyncMock` and `unittest.mock.patch` for all mocking. There are no custom httpx transport mocks or respx usage. Continue this pattern.

**Factory fixtures already available:**
- `make_settings()` in `conftest.py` -- builds `Settings` with test defaults
- `default_state()` in `conftest.py` -- builds fresh `TriggarrState`
- `_init_test_db()` in `test_db.py` (local helper) -- creates test SQLite database

**New fixtures NOT needed.** The existing mock patterns are sufficient:

```python
# httpx failures -- already established pattern
client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
client.search_movies = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

# HTTP status errors -- established in test_tracking.py
mock_request = httpx.Request("GET", "http://test/api")
mock_response = httpx.Response(404, request=mock_request)
exc = httpx.HTTPStatusError("Not found", request=mock_request, response=mock_response)
client.get_grab_history.side_effect = exc

# Pydantic validation errors -- trigger by returning bad JSON shapes
client.get_wanted_missing = AsyncMock(return_value=[{"bad": "shape"}])

# SQLite errors
# Use real aiosqlite with tmp_path, then corrupt the database file
# Or mock db operations with side_effect=aiosqlite.OperationalError
```

### Coverage Gap Analysis

#### Category 1: Connection Failures (target: `test_clients.py`, `test_search.py`)

**Already tested:**
- `_request_with_retry` retry on HTTP status error
- `_request_with_retry` reraise after both attempts fail
- `validate_connection` ConnectError, TimeoutException
- Radarr/Sonarr/Lidarr cycle network failure (ConnectError)

**Missing -- add to `test_clients.py`:**
- `_request_with_retry` with `httpx.ReadTimeout` (subtype of TransportError)
- `_request_with_retry` with `httpx.ConnectTimeout` (subtype of TransportError)
- `_request_with_retry` first attempt fails, retry succeeds (partial coverage exists but only for HTTPStatusError, not TransportError)
- `get_paginated` when a mid-pagination page fails (page 1 succeeds, page 2 raises)
- `get_json_list` when response is not a JSON array (returns dict instead)
- `get_total_records` when response has malformed pagination envelope

**Missing -- add to `test_search.py`:**
- Cycle abort on `pydantic.ValidationError` (API returns unexpected shape)
- Per-item search failure logged as "failed" outcome in DB (currently tests ConnectError, not `aiosqlite.Error`)
- Cycle continues after per-item `aiosqlite.Error` on `insert_search_entry`

#### Category 2: Bad API Responses (target: `test_clients.py`, `test_search.py`, `test_tracking.py`)

**Already tested:**
- `get_paginated` malformed response (ValidationError)
- `validate_connection` with pydantic.ValidationError

**Missing -- add to `test_clients.py`:**
- `get_tags` returns non-list response
- `get_tags` returns items missing `id` or `label` fields
- `get_paginated` returns `totalRecords: -1` (negative)
- `get_paginated` returns `records: null` instead of array
- HTTP 500 on first attempt, success on retry (verify retry works for server errors)

**Missing -- add to `test_search.py`:**
- `filter_unreleased_movies` with items missing date fields entirely (not just null -- key absent)
- `resolve_tag_id` when `get_tags` raises (already tested for ConnectError, but not for malformed tag response)
- Cycle handles empty `records` array from paginated response gracefully

**Missing -- add to `test_tracking.py`:**
- Tracking with grab history returning empty list (no grabs found)
- Tracking with grab history returning events with missing timestamp fields
- `correlate_grabs` with mismatched item IDs

#### Category 3: Corrupt State/Config (target: `test_config.py`, `test_state.py`, `test_db.py`)

**Already tested:**
- Corrupt JSON state recovery (`test_state.py`)
- Atomic TOML write failure cleanup (`test_config.py`)
- Migration suppresses OperationalError (`test_db.py`)

**Missing -- add to `test_config.py`:**
- `load_settings` with corrupt/invalid TOML (binary garbage, truncated file)
- `load_settings` with valid TOML but invalid schema (e.g., `search_interval = "not_a_number"`)
- `load_settings` with missing required sections
- `detect_and_migrate_v22` with corrupt TOML file
- `_atomic_toml_write` when directory does not exist
- Config file with wrong permissions (read-only)

**Missing -- add to `test_state.py`:**
- State file is empty (0 bytes)
- State file contains valid JSON but wrong shape (array instead of object)
- `save_state` when disk is full (OSError simulation)

**Missing -- add to `test_db.py`:**
- `init_db` on a corrupted SQLite file (not a valid database)
- `insert_search_entry` when DB is read-only
- `get_search_history` when table has been dropped (schema corruption)
- Migration on a DB that's ahead of expected version (downgrade scenario)
- `get_dashboard_stats` with empty tables (zero division edge case)

#### Category 4: Search Logic Edge Cases (target: `test_search.py`)

**Already tested:**
- Empty item lists, wrap-around cursors, batch slicing edge cases
- Filter monitored with missing key, Sonarr episode filtering

**Missing -- add to `test_search.py`:**
- `cap_batch_sizes` with `hard_max = 0` (disabled) -- verify no capping
- `cap_batch_sizes` with all items in one queue (missing=100, cutoff=0)
- `slice_batch` with `batch_size` larger than item list
- `deduplicate_to_seasons` with episodes missing `seriesId` or `seasonNumber`
- Cycle with all items already searched (cursor at end, wraps to 0, nothing new)
- Cycle with `search_missing_count = 0` and `search_cutoff_count = 0`
- `_sanitize_exc` with unexpected exception types (not HTTP or timeout)

## Data Flow: No Changes

This milestone adds no runtime data flow changes. All community health files are static. All test changes exercise existing code paths -- they do not modify production code.

```
BEFORE v2.4:                    AFTER v2.4:
[Same runtime architecture]     [Same runtime architecture]
                                + CONTRIBUTING.md (static)
                                + SECURITY.md (static)
                                + .github/ISSUE_TEMPLATE/*.yml (static)
                                + ~50-80 new test cases in existing files
```

## Patterns to Follow

### Pattern 1: YAML Issue Form Templates (not Markdown)

**What:** Use `.yml` form-based templates in `.github/ISSUE_TEMPLATE/` instead of legacy `.md` templates.

**Why:** YAML forms enforce structured input (required fields, dropdowns, code blocks). Markdown templates are freeform and users frequently delete the template text, submit incomplete reports.

**Example:**
```yaml
name: Bug Report
description: Report a bug in Triggarr
labels: ["bug"]
body:
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What went wrong?
    validations:
      required: true
  - type: dropdown
    id: deployment
    attributes:
      label: Deployment Method
      options:
        - Docker Compose
        - Docker run
        - Bare Python (uv)
    validations:
      required: true
```

### Pattern 2: Unhappy Tests Inline with Module Tests

**What:** Add failure-mode tests to the existing test file for each module, not in separate "unhappy path" files.

**Why:** The codebase already mixes happy and unhappy tests. Keeping them together means you see all behavior (normal + failure) when reading one file. Separate files would split related tests and make refactoring harder.

**How:** Use section comment headers to group new tests:
```python
# ---------------------------------------------------------------------------
# Connection failure scenarios
# ---------------------------------------------------------------------------
```

### Pattern 3: AsyncMock side_effect for httpx Failures

**What:** Use `AsyncMock(side_effect=httpx.SomeError(...))` to simulate HTTP failures.

**Why:** This is the established pattern throughout the test suite. No need for respx, httpx MockTransport, or custom test doubles. The existing approach is simple and works.

**When NOT to use:** If testing the actual HTTP retry timing (sleep), patch `asyncio.sleep` as already done in `test_clients.py`.

### Pattern 4: tmp_path for File Corruption Tests

**What:** Use pytest's `tmp_path` fixture to create corrupt files, then pass them to config/state/db loaders.

**Why:** Already established in `test_config.py`, `test_state.py`, `test_db.py`. Avoids filesystem side effects.

**Example for corrupt TOML:**
```python
def test_load_settings_corrupt_toml(tmp_path):
    config_path = tmp_path / "triggarr.toml"
    config_path.write_text("this is not valid [[[toml")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings(config_path)
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Test Files for Unhappy Paths

**What:** Creating `test_clients_unhappy.py`, `test_search_failures.py`, etc.
**Why bad:** Splits related tests across files. When someone changes `_request_with_retry`, they should find ALL tests (happy + unhappy) in one place. The existing convention is module-aligned files.
**Do this instead:** Add tests to existing `test_clients.py`, `test_search.py`, etc.

### Anti-Pattern 2: Overly Complex Failure Fixtures

**What:** Building elaborate fixture hierarchies for simulating failures (custom httpx transports, mock servers, failure injection frameworks).
**Why bad:** The existing `AsyncMock(side_effect=...)` pattern is simple, readable, and proven across 466 tests. Adding complexity for no gain.
**Do this instead:** Continue using `AsyncMock` + `side_effect`. For file corruption, write bad content to `tmp_path` files.

### Anti-Pattern 3: Testing Framework Internals

**What:** Testing that httpx raises the right exception types, or that aiosqlite raises OperationalError on corrupt files.
**Why bad:** You are testing third-party library behavior, not your code. Fragile, slow, and low value.
**Do this instead:** Mock the exception at the boundary (the method your code calls) and verify your code's response to it.

### Anti-Pattern 4: Code of Conduct in Community Health Files

**What:** Adding CODE_OF_CONDUCT.md with Contributor Covenant text.
**Why bad:** Known to trigger Anthropic content filters during AI-assisted development. Also, for a homelab tool with a small community, it adds ceremony without value.
**Do this instead:** Skip it. CONTRIBUTING.md covers behavioral expectations implicitly through PR expectations.

## Suggested Build Order

Build order is straightforward since there are no dependencies between community files and tests.

### Phase 1: Community Health Files

**What:** CONTRIBUTING.md, SECURITY.md, `.github/ISSUE_TEMPLATE/` (bug_report.yml, feature_request.yml, config.yml).

**Why first:** Static files, zero risk, fast to write, immediately useful if anyone opens an issue.

**Dependencies:** None.

**Test surface:** None (static files). Optionally add a test that CONTRIBUTING.md and SECURITY.md exist (like the existing `test_changelog.py` pattern).

### Phase 2: Repo Metadata

**What:** GitHub topics, enable Discussions.

**Why second:** Quick administrative task, no files to write (just `gh` commands).

**Dependencies:** None.

### Phase 3: Connection Failure Tests

**What:** New tests in `test_clients.py` and `test_search.py` for transport error subtypes, mid-pagination failures, retry-then-succeed scenarios.

**Why third:** Highest value unhappy-path coverage. Connection failures are the most common real-world failure mode for a tool that talks to external APIs.

**Dependencies:** None.

### Phase 4: Bad API Response Tests

**What:** New tests in `test_clients.py`, `test_search.py`, `test_tracking.py` for malformed JSON, unexpected shapes, missing fields.

**Why fourth:** Second most common failure mode. *arr APIs can return unexpected shapes during version upgrades.

**Dependencies:** None (can run in parallel with Phase 3).

### Phase 5: Corrupt State/Config Tests

**What:** New tests in `test_config.py`, `test_state.py`, `test_db.py` for broken TOML, empty files, corrupt SQLite, schema mismatch.

**Why fifth:** Less likely in practice (files are written atomically) but important for robustness confidence.

**Dependencies:** None (can run in parallel with Phases 3-4).

### Phase 6: Search Logic Edge Cases

**What:** New tests in `test_search.py` for zero-count batches, missing fields in deduplicated episodes, cursor boundary conditions.

**Why last:** Lowest risk -- these are pure functions with no I/O. Edge cases are unlikely to cause production issues but improve confidence.

**Dependencies:** None.

## Scaling Considerations

Not applicable for this milestone. Community health files and tests do not affect runtime behavior or resource usage.

The only scaling concern is test suite run time. Adding ~50-80 tests to a suite of 466 should add approximately 2-5 seconds (most tests use mocks, not real I/O). The CI workflow already caches uv packages, so no CI time concern.

## Sources

- Full codebase audit of all 20 test files and 13 source modules in `triggarr/` (HIGH confidence)
- GitHub YAML issue form template documentation: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms (HIGH confidence -- official docs)
- GitHub community health files documentation: https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions (HIGH confidence -- official docs)
- Existing test patterns in codebase: AsyncMock + side_effect, tmp_path for file tests, section comment headers (HIGH confidence -- direct observation)
- CLAUDE.md project conventions for dev commands and code style (HIGH confidence -- project file)

---
*Architecture research for: Triggarr v2.4 Community Polish & Test Hardening*
*Researched: 2026-04-09*
