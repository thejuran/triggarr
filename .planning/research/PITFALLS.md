# Domain Pitfalls

**Domain:** Community health files + unhappy-path test hardening for existing Python/FastAPI project
**Researched:** 2026-04-09
**Confidence:** HIGH (based on direct codebase analysis of all test files, security patterns, CI config, and README)

---

## Critical Pitfalls

Mistakes that cause security confusion, broken contributor experience, or false test confidence.

### Pitfall 1: SECURITY.md contradicts actual security model

**What goes wrong:** SECURITY.md uses boilerplate language like "we take security seriously" and describes protections the app does not have (authentication, encrypted storage, Redis rate limiting) or omits protections it does have (SecretStr discipline, SSRF validation, Origin-based CSRF, log redaction, config file 0600 permissions). Contributors read SECURITY.md, find it does not match the code, and lose trust in the project.

**Why it happens:** Copy-pasting SECURITY.md from another project without auditing against the codebase. Triggarr has a deliberately unusual security posture: no authentication by design, but strong credential hygiene and attack surface reduction. Generic templates assume authentication exists.

**Consequences:** Security researchers file false positives ("no auth is a vulnerability"). Contributors add unnecessary auth middleware thinking it was forgotten. The README Security Model section (lines 163-227) and SECURITY.md tell different stories.

**Prevention:**
- Write SECURITY.md by extracting from the existing README Security Model section, not from a template
- Explicitly state the "no auth by design" philosophy with the same language the README uses
- Reference specific code patterns: `SecretStr`, `OriginCheckMiddleware`, SSRF validation in `web/validation.py`, `BLOCKED_HOSTS`, `0600` config permissions
- Cross-reference: SECURITY.md for reporting instructions, README.md for the full security model
- Review both documents side-by-side before shipping

**Detection:** Diff the claims in SECURITY.md against README Security Model. Any claim in SECURITY.md not backed by code or README is a red flag.

**Phase to address:** Community health files phase -- first file to write, since it anchors the security narrative.

---

### Pitfall 2: Mocking the wrong layer in unhappy-path tests

**What goes wrong:** Tests mock `httpx.AsyncClient.get` or `aiosqlite.Connection.execute` directly instead of using the established `httpx.MockTransport` pattern. This creates tests that pass but do not exercise the actual error handling code paths (retry logic in `_request_with_retry`, exception sanitization in `_sanitize_exc`, timeout handling).

**Why it happens:** The quick way to test "connection refused" is `mock.patch("httpx.AsyncClient.get", side_effect=ConnectionError)`. But Triggarr's client layer uses `_request_with_retry` which wraps raw httpx calls with retry + sleep + error sanitization. Mocking above that layer skips the code that matters.

**Consequences:** Tests give false confidence. The retry-then-reraise path, the timeout path, and the sanitized-exception path never get exercised. A real connection failure in production hits code that was never tested.

**Prevention:**
- Follow the existing pattern in `test_clients.py` lines 80-135: use `httpx.MockTransport` with handler functions that return error responses or raise exceptions
- For database tests, use the existing in-memory aiosqlite pattern from `test_db.py`
- Mock at the transport boundary, not the client method layer
- Rule of thumb: if a test mocks a method on a Triggarr class rather than on httpx/aiosqlite, it is probably at the wrong layer

**Detection:** Review each new test: does the mock sit below the code being tested, or at/above it? Mocking a Triggarr method means you are testing the mock, not the code.

**Phase to address:** All unhappy-path test phases -- establish the rule in the first test phase, enforce in all subsequent ones.

---

### Pitfall 3: Issue templates that demand info the reporter cannot provide

**What goes wrong:** Bug report template requires Docker logs, config file contents, Radarr/Sonarr versions, and exact reproduction steps -- all as required fields. Reporters who hit a UI glitch or have a quick question abandon the issue rather than gather all that info. Feature request template asks for "proposed implementation" which gates non-technical users.

**Why it happens:** Template authors optimize for maintainer triage convenience, not reporter experience. Every "required" field raises the bar for reporting.

**Consequences:** Fewer bug reports filed. Users go to Reddit/Discord instead of GitHub Issues, where problems are invisible to maintainers.

**Prevention:**
- Use GitHub YAML form syntax (not old markdown templates) for structured input
- Make only the description/summary field required. Everything else optional but encouraged with helpful placeholder text
- Bug reports: required = description only; optional = environment, logs, steps, screenshots
- Feature requests: required = description only; optional = use case, alternatives considered
- Add `config.yml` in `.github/ISSUE_TEMPLATE/` with a link to GitHub Discussions for support questions
- YAML gotchas: wrap text containing `#` in quotes (YAML comment), wrap boolean-like strings (`yes`, `no`, `true`, `false`) in quotes

**Detection:** Count required fields. More than 2 required fields on a bug report is a warning sign. Test by filing an issue yourself.

**Phase to address:** Issue templates phase -- design with minimal friction from the start.

---

## Moderate Pitfalls

### Pitfall 4: CONTRIBUTING.md describes a workflow the project does not use

**What goes wrong:** CONTRIBUTING.md says "pip install -e .", "run black/flake8", or other standard tooling instructions. The actual workflow uses `uv sync --extra dev`, `ruff check`, `pytest-asyncio` with `asyncio_mode=auto`, and specific patterns like `MockTransport` and factory functions in `conftest.py`. Contributors follow wrong instructions, their environment does not match, and their first PR fails CI.

**Why it happens:** Generic CONTRIBUTING.md templates assume standard Python tooling. Triggarr uses `uv` (not pip), `ruff` (not flake8/black), `pytest-asyncio` auto mode (no `@pytest.mark.asyncio` decorators needed), and has established test factories (`make_settings`, `default_state`).

**Prevention:**
- Start from CLAUDE.md's Development Commands section -- those are the actual commands
- Include exact commands: `uv sync --extra dev`, `uv run pytest tests/ -x -q`, `uv run ruff check triggarr/ tests/`
- Document the Tailwind CSS build step for template changes
- Document test conventions: MockTransport for HTTP, factory functions in conftest.py, asyncio_mode=auto
- Do NOT mention tools the project does not use (pip, black, isort, mypy, tox, pre-commit)

**Detection:** Run the setup instructions from a clean checkout. If they fail or produce a different environment, the docs are wrong.

**Phase to address:** CONTRIBUTING.md phase -- validate by following own instructions.

---

### Pitfall 5: Unhappy-path tests that create real files in the working directory

**What goes wrong:** Tests for corrupt config or corrupt database create actual files in the repo directory instead of using `tmp_path` fixtures. This pollutes the working tree, causes flaky test ordering, and can accidentally get committed.

**Why it happens:** Quick approach for "test corrupt config" is `Path("test_config.toml").write_text("garbage")`. Under time pressure, developers skip proper fixture setup.

**Consequences:** Flaky tests on CI (file ordering differs), polluted working directory, test isolation violations.

**Prevention:**
- Always use pytest's `tmp_path` fixture for any file I/O in tests
- Database corruption tests: `aiosqlite.connect(":memory:")` or `tmp_path / "test.db"`
- Config corruption tests: write to `tmp_path / "triggarr.toml"` and patch `get_config_dir()` to return `tmp_path`
- Existing `test_config_dir.py` and `test_state.py` demonstrate correct patterns -- follow them

**Detection:** Grep for file operations in tests that do not reference `tmp_path`.

**Phase to address:** All unhappy-path test phases.

---

### Pitfall 6: Unhappy-path tests that slow down the entire suite

**What goes wrong:** Tests for timeout scenarios use real `asyncio.sleep` waits or real network timeouts. A single "test connection timeout" adds 10-30 seconds per test. With multiple such tests, the suite goes from seconds to minutes.

**Why it happens:** Testing timeout behavior by actually waiting is the naive approach. The existing codebase already patches `asyncio.sleep` with `AsyncMock` (see `test_clients.py` line 113: `patch("asyncio.sleep", new_callable=AsyncMock)`), but new tests may not follow this pattern.

**Consequences:** CI takes minutes instead of seconds. Developers stop running tests locally. The fast-feedback loop that supports 466 tests breaks down.

**Prevention:**
- Always mock `asyncio.sleep` when testing retry/timeout paths
- Use `httpx.MockTransport` handlers that immediately raise `httpx.ConnectError` or return error codes -- no actual network waits
- For APScheduler tests, mock the scheduler rather than waiting for real intervals
- Add `timeout-minutes: 5` to the CI test job as a safety net

**Detection:** Run `pytest --durations=10` to find slow tests. Any test over 1 second is likely doing real I/O or real sleeping.

**Phase to address:** All unhappy-path test phases.

---

### Pitfall 7: Discussions enabled but nobody monitors them

**What goes wrong:** Repo metadata enables GitHub Discussions, but nobody checks the Discussions tab. Questions pile up unanswered, making the project look abandoned.

**Why it happens:** Discussions are easy to enable, easy to forget. Unlike Issues, they lack urgency in maintainer workflows.

**Prevention:**
- Only enable Discussions if the maintainer commits to checking weekly
- If enabling, create only a "Q&A" category (not General, Ideas, Show and Tell)
- Alternative: skip Discussions entirely, add a "Question" issue type via `config.yml` with a "question" label
- Set expectations in CONTRIBUTING.md about where to ask questions

**Detection:** Unanswered questions in Discussions older than 2 weeks signal the feature should be disabled or actively monitored.

**Phase to address:** Repo metadata phase -- decide before enabling.

---

## Minor Pitfalls

### Pitfall 8: YAML issue template syntax errors that silently break

**What goes wrong:** Template YAML has syntax errors: unquoted `#` parsed as comments, `yes`/`no` dropdown options parsed as booleans, missing `name` field. GitHub silently falls back to blank issue form.

**Prevention:**
- Use `type: input` and `type: textarea` (not `type: text`)
- Wrap dropdown options in quotes, especially boolean-like values
- Wrap any `label` or `description` containing `#` in double quotes
- Every template needs top-level `name`, `description`, and `body` keys
- Validate by filing an actual issue on GitHub after pushing

**Detection:** Navigate to "New Issue" page. Missing or broken templates mean YAML errors. GitHub does not report these errors visibly.

**Phase to address:** Issue templates phase.

---

### Pitfall 9: Repo topics too generic or missing ecosystem terms

**What goes wrong:** Topics set to only "python" and "docker" which do not help discoverability in the *arr ecosystem.

**Prevention:**
- Include ecosystem terms: `radarr`, `sonarr`, `lidarr`, `arr`, `usenet`, `torrent`, `automation`, `media-management`
- Include tech terms: `python`, `fastapi`, `htmx`, `docker`, `self-hosted`
- Limit to 10-15 topics

**Detection:** Search GitHub for "radarr automation" -- does Triggarr appear?

**Phase to address:** Repo metadata phase.

---

### Pitfall 10: CONTRIBUTING.md omits license terms for contributions

**What goes wrong:** Contributors submit code without understanding license terms. Later disputes about code ownership.

**Prevention:**
- State explicitly: "By submitting a PR, you agree that your contribution is licensed under [project license]."
- Verify the repo has a LICENSE file

**Detection:** Read CONTRIBUTING.md -- if it does not mention the license, add a one-liner.

**Phase to address:** CONTRIBUTING.md phase.

---

### Pitfall 11: Unhappy-path tests that duplicate happy-path coverage without testing new behavior

**What goes wrong:** Developer adds "test connection failure returns error" but the test only verifies the exception type, not the actual behavior that matters: Does the error get sanitized? Does the log message redact secrets? Does the state reflect the failure? Does the UI show the right error? The test adds to the count but not to actual coverage.

**Why it happens:** "Add unhappy-path tests" feels like "add `pytest.raises` blocks." The value is in testing the error HANDLING, not the error itself.

**Prevention:**
- Each unhappy-path test should assert at least one behavioral outcome beyond the exception type
- Connection failure: assert `state["instances"]["X"]["connected"]` is False, assert log message contains sanitized (not raw) error
- Corrupt config: assert graceful fallback behavior, not just "it raised ValueError"
- Bad API response: assert the search cycle continues (not crashes), assert partial results are handled
- Use the existing patterns: `test_request_with_retry_reraises_when_retry_fails` verifies the retry COUNT and the exception type -- both are behavioral assertions

**Detection:** If a test is just `with pytest.raises(SomeError): do_thing()` and nothing else, it is probably not testing enough.

**Phase to address:** All unhappy-path test phases.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| SECURITY.md | Contradicts README Security Model (#1) | Extract from README, do not use a generic template |
| CONTRIBUTING.md | Describes wrong toolchain (#4), omits license (#10) | Base on CLAUDE.md dev commands, validate by following own instructions |
| Issue templates | Too many required fields (#3), YAML syntax errors (#8) | Minimal required fields, validate by filing a test issue |
| Repo metadata | Discussions unmonitored (#7), topics too generic (#9) | Decide monitoring commitment, include *arr ecosystem terms |
| Unhappy-path: connection failures | Wrong mock layer (#2), real timeouts (#6) | Use MockTransport pattern, mock asyncio.sleep |
| Unhappy-path: bad API responses | Wrong mock layer (#2), shallow assertions (#11) | MockTransport handlers returning malformed JSON, assert behavioral outcomes |
| Unhappy-path: corrupt state/config | Real files in working dir (#5) | Use tmp_path fixture exclusively |
| Unhappy-path: search edge cases | Slow tests (#6), shallow assertions (#11) | Mock scheduler, mock sleep, assert cycle continues |

---

## Sources

- [GitHub Docs: Syntax for issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) -- YAML form schema reference
- [GitHub Docs: Common validation errors when creating issue forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/common-validation-errors-when-creating-issue-forms) -- Boolean parsing, missing name field, empty body
- [Open Source Guides: Security Best Practices](https://opensource.guide/security-best-practices-for-your-project/) -- SECURITY.md structure and reporting procedures
- Triggarr README.md lines 163-227 -- existing security model documentation (HIGH confidence, direct source)
- Triggarr `tests/test_clients.py` lines 80-135 -- established MockTransport and AsyncMock patterns (HIGH confidence)
- Triggarr `tests/conftest.py` -- factory functions `make_settings`, `default_state` (HIGH confidence)
- Triggarr `triggarr/web/validation.py` -- SSRF validation, BLOCKED_HOSTS, input clamping (HIGH confidence)
- Triggarr `triggarr/web/middleware.py` -- OriginCheckMiddleware CSRF implementation (HIGH confidence)
- Triggarr CLAUDE.md -- canonical dev commands and test conventions (HIGH confidence)
- Triggarr `pyproject.toml` line 36 -- `asyncio_mode = "auto"` configuration (HIGH confidence)

---
*Pitfalls research for: Triggarr v2.4 community health files and unhappy-path test hardening*
*Researched: 2026-04-09*
