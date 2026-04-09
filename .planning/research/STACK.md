# Stack Research

**Domain:** Community health files + unhappy-path test hardening for existing Python/FastAPI Docker app
**Researched:** 2026-04-09
**Confidence:** HIGH

## Recommended Stack

### Zero New Dependencies

The most important finding: **no new production or dev dependencies are needed**. The existing stack already covers every requirement for v2.4.

| Requirement | Covered By | Already Installed |
|-------------|-----------|-------------------|
| GitHub issue template YAML forms | Pure YAML files in `.github/ISSUE_TEMPLATE/` | N/A (no code) |
| CONTRIBUTING.md, SECURITY.md | Plain Markdown files | N/A (no code) |
| Repo metadata (topics, Discussions) | `gh` CLI / GitHub web UI | N/A (no code) |
| Mocking httpx failures | `unittest.mock.AsyncMock` + `httpx` exception classes | Yes |
| Mocking httpx responses | `httpx.MockTransport` | Yes |
| SQLite corruption simulation | `aiosqlite` + `unittest.mock.patch` | Yes |
| TOML parse error simulation | `unittest.mock.patch` + stdlib | Yes |
| Async test support | `pytest-asyncio` with `asyncio_mode=auto` | Yes |
| Env var manipulation | `pytest` built-in `monkeypatch` fixture | Yes |
| Temp file/directory fixtures | `pytest` built-in `tmp_path` fixture | Yes |

### Community Health Files (No Code Required)

These are pure content files with specific GitHub conventions:

| File | Location | Format | Notes |
|------|----------|--------|-------|
| `CONTRIBUTING.md` | Repo root | Markdown | GitHub auto-links from issue sidebar |
| `SECURITY.md` | Repo root | Markdown | GitHub auto-links "Security" tab; renders security policy |
| Bug report template | `.github/ISSUE_TEMPLATE/bug_report.yml` | YAML form | Uses GitHub issue forms schema |
| Feature request template | `.github/ISSUE_TEMPLATE/feature_request.yml` | YAML form | Uses GitHub issue forms schema |
| Template chooser config | `.github/ISSUE_TEMPLATE/config.yml` | YAML | Controls blank issue toggle, external links |

### GitHub Issue Template YAML Forms

Issue forms use a specific YAML schema. Key structure:

**Required top-level keys:** `name`, `description`, `body`
**Optional top-level keys:** `title` (pre-filled title template), `labels` (auto-applied labels), `assignees`, `projects`

**Supported body element types:**
- `markdown` -- static instructional text (not submitted)
- `input` -- single-line text field
- `textarea` -- multi-line text field (supports `render` for syntax highlighting)
- `dropdown` -- select from options
- `checkboxes` -- multi-select checkboxes

Each body element requires `type` and `attributes` (with at minimum `label`). Validation via `validations.required: true`.

**Template chooser config** (`.github/ISSUE_TEMPLATE/config.yml`):
- `blank_issues_enabled: false` -- forces use of templates
- `contact_links` -- redirects to external resources (e.g., Discussions for questions)

### Existing Test Patterns (Already in Codebase)

The project already uses these patterns extensively across 466 tests. The unhappy-path work extends existing conventions, not introduces new ones.

| Pattern | Used In | How |
|---------|---------|-----|
| `AsyncMock(side_effect=httpx.ConnectError(...))` | `test_search.py`, `test_tracking.py` | Simulates connection failures |
| `AsyncMock(side_effect=httpx.TimeoutException(...))` | `test_search.py`, `test_update_check.py` | Simulates timeouts |
| `AsyncMock(side_effect=httpx.HTTPStatusError(...))` | `test_tracking.py` | Simulates 4xx/5xx responses |
| `httpx.MockTransport(handler)` | `test_startup.py` | Full request/response cycle mocking |
| `monkeypatch.setenv(...)` | `test_config_dir.py` | Environment variable manipulation |
| `monkeypatch.setattr(Path, ...)` | `test_db.py` | Filesystem operation mocking |
| `unittest.mock.patch(...)` | `test_search.py`, `test_update_check.py` | Module-level patching |
| `tmp_path` fixture | `test_db.py` | Temporary SQLite databases |

### httpx Exception Classes for Unhappy-Path Tests

These are the httpx exception types relevant for simulating failures (all already available via the `httpx` dependency):

| Exception | Simulates |
|-----------|-----------|
| `httpx.ConnectError` | Connection refused, DNS failure, network unreachable |
| `httpx.TimeoutException` | General request timeout |
| `httpx.ReadTimeout` | Response body read timeout |
| `httpx.ConnectTimeout` | TCP connection timeout |
| `httpx.HTTPStatusError` | 4xx/5xx responses (requires mock `request` + `response` args) |
| `httpx.DecodingError` | Malformed response body (garbled JSON) |
| `httpx.RemoteProtocolError` | Server sent bad HTTP (connection reset mid-response) |

### SQLite / State / Config Failure Simulation Techniques

For testing corrupt database, state files, and config parsing:

| Technique | What It Tests |
|-----------|---------------|
| Write garbage bytes to `tmp_path / "triggarr.db"` then call `init_db()` | Corrupt database file handling |
| `patch("aiosqlite.connect", side_effect=Exception("disk I/O error"))` | Database connection failure |
| `patch.object(cursor, "execute", side_effect=aiosqlite.OperationalError(...))` | Query execution failure |
| Write invalid TOML string to config file, then load | TOML parse error handling (`tomllib.TOMLDecodeError`) |
| Write valid TOML with wrong types/missing keys, then load | Pydantic `ValidationError` handling |
| Write malformed JSON to state file, then load | `json.JSONDecodeError` handling |
| `patch("builtins.open", side_effect=PermissionError(...))` | File permission errors |
| `patch("os.replace", side_effect=OSError(...))` | Atomic write failure (temp file cleanup path) |
| Write TOML with unknown keys / extra sections | Config forward-compatibility |

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `unittest.mock.AsyncMock` | `respx` v0.22.0 | Project already uses AsyncMock + httpx exceptions consistently across 466 tests. Adding respx creates two mocking paradigms. AsyncMock with `side_effect` is simpler for error-path testing. |
| `unittest.mock.AsyncMock` | `pytest-httpx` v0.35.0 | Same reasoning. Fixture-based response mocking is nice for happy-path mocking but overkill when focus is `side_effect=httpx.ConnectError(...)`. |
| Plain YAML issue forms | Markdown issue templates | YAML forms produce structured data, enforce required fields, render as proper form UI. Markdown templates are freeform and often poorly filled out. |
| `blank_issues_enabled: false` | Allowing blank issues | For a small project, forcing templates keeps issue quality high. Users can still reach out via Discussions. |

## What NOT to Add

| Avoid | Why | Do Instead |
|-------|-----|------------|
| `respx` | Introduces second mocking paradigm alongside established `AsyncMock` pattern | Continue using `unittest.mock.AsyncMock` with `httpx` exception classes |
| `pytest-httpx` | Same issue -- two mocking conventions in one test suite creates confusion | Continue existing patterns |
| `pytest-cov` | Coverage metrics are nice-to-have but not required for targeted unhappy-path work; adds CI complexity | Run manually with `uv run pytest --cov` if curiosity strikes |
| Markdown linters (`markdownlint`, `mdformat`) | Over-engineering for 2-3 static markdown files | Manual review is sufficient |
| `pre-commit` hooks | Project uses ruff directly in CI; pre-commit adds config overhead for single-maintainer project | Keep `uv run ruff check` in CI |
| Any new production dependencies | v2.4 is community polish + test hardening, not feature work | Zero dependency changes to `pyproject.toml` |
| `jsonschema` for validating YAML templates | GitHub validates templates on push; local validation adds a dependency for no practical benefit | Let GitHub validate on push |

## Version Compatibility

No new packages, so no compatibility concerns. Existing stack versions are locked via `uv.lock`.

| Existing Package | Constraint | Relevant For v2.4 |
|------------------|-----------|-------------------|
| `httpx` | Latest via uv.lock | Exception classes (`ConnectError`, `TimeoutException`, etc.) stable since 0.23+ |
| `pytest` | Latest via uv.lock | `monkeypatch`, `tmp_path` fixtures |
| `pytest-asyncio` | Latest via uv.lock | `asyncio_mode=auto` for async test functions |
| `aiosqlite` | Latest via uv.lock | `OperationalError` for corruption simulation |
| `pydantic-settings[toml]` | Latest via uv.lock | `ValidationError` for bad config tests |

## GitHub CLI Commands for Repo Metadata

One-time setup commands (not code changes):

```bash
# Add repository topics
gh repo edit --add-topic radarr,sonarr,automation,docker,fastapi,htmx,python,arr

# Enable GitHub Discussions
gh repo edit --enable-discussions
```

## Installation

No changes to `pyproject.toml`:

```bash
# Existing (unchanged)
uv sync --extra dev
```

## Sources

- [GitHub Docs: Syntax for issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) -- YAML form schema, required keys, body element types (HIGH confidence)
- [GitHub Docs: Syntax for GitHub's form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema) -- element attributes, validation options (HIGH confidence)
- [GitHub Docs: Configuring issue templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository) -- config.yml, blank_issues_enabled, contact_links (HIGH confidence)
- [respx on PyPI](https://pypi.org/project/respx/) -- v0.22.0, evaluated and rejected (HIGH confidence)
- [pytest-httpx on PyPI](https://pypi.org/project/pytest-httpx/) -- evaluated and rejected (HIGH confidence)
- Existing codebase: `tests/test_search.py`, `tests/test_tracking.py`, `tests/test_startup.py`, `tests/test_clients.py`, `tests/test_update_check.py` -- established mocking patterns verified by direct inspection (HIGH confidence)

---
*Stack research for: Triggarr v2.4 Community Polish & Test Hardening*
*Researched: 2026-04-09*
