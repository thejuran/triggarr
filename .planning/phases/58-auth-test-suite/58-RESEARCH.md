# Phase 58: Auth Test Suite - Research

**Researched:** 2026-04-15
**Domain:** Python test engineering (pytest + FastAPI TestClient) for auth coverage gaps
**Confidence:** HIGH

## Summary

Phase 58 is a pure verification phase. All auth code is already implemented across Phases 54-57. The existing test suite contains 86 passing auth tests across 4 files. The task is to audit coverage against 5 success criteria, fill identified gaps, and add a new `test_auth_integration.py` for cross-cutting end-to-end flows.

Coverage gap analysis reveals the existing suite is ~75% complete against the 5 success criteria. The major gaps are: (1) no API-key-specific tests for missing key or 401 JSON response, (2) no integration tests for cross-module flows (setup->login->use->logout), (3) no edge case tests for tampered/expired cookies at the middleware level, (4) no auth mode transition tests, and (5) the Disabled mode startup warning log is not yet implemented in code -- D-11 says to test that passthrough behavior works AND the warning fires, but the warning log itself does not exist yet in any module.

**Primary recommendation:** Audit-then-fill approach per D-04. Add ~25-35 new tests across existing files plus one new `test_auth_integration.py`. No new dependencies needed -- pytest, FastAPI TestClient, and unittest.mock are sufficient.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Gap-fill existing test files (`test_auth_config.py`, `test_auth_helpers.py`, `test_auth_middleware.py`, `test_auth_routes.py`) rather than creating parallel files. Keeps tests co-located with the code they verify.
- **D-02:** One new file `test_auth_integration.py` for cross-cutting end-to-end flows (e.g., setup->login->use->logout) that span multiple modules.
- **D-03:** Each test file includes a traceability comment block at the top mapping tests to success criteria (SC-1 through SC-5). Makes full coverage verifiable at a glance.
- **D-04:** Audit-then-fill approach. First pass: read all existing tests and map each to a success criterion. Second pass: write tests only for identified gaps. No duplicate coverage.
- **D-05:** Existing TDD tests from Phases 54-57 count toward coverage. Phase 58 fills what those phases didn't cover, not re-tests what they did.
- **D-06:** Security-focused edge cases: expired/tampered cookies, malformed Authorization headers, invalid API keys (wrong length, empty, whitespace), open redirect attempts in `?next=`, setup endpoint after auth already configured.
- **D-07:** Test session cookie signed with a different `session_secret` (simulating secret rotation or config tampering) -- verify it is rejected by middleware.
- **D-08:** Skip unlikely runtime scenarios: concurrent setup race conditions, partial config corruption, every possible malformed header variant. Focus on what an attacker or misconfiguration would actually produce.
- **D-09:** Test each auth mode (Forms, Basic, External, Disabled) in isolation with its expected behavior.
- **D-10:** Test 2-3 key mode transitions: Forms->Basic (session cookie still valid?), any->Disabled (warning logged?), Disabled->Forms (re-requires login?). No exhaustive 4x4 permutation matrix.
- **D-11:** Disabled mode tests verify both passthrough behavior (requests pass unauthenticated) AND that the startup warning log message fires. Do not test the 60-second interval timing.

### Claude's Discretion
- Test helper/fixture structure (shared fixtures in conftest.py vs per-file helpers)
- Exact test names and grouping within each file
- Whether to use parametrize for mode-specific tests or separate test functions
- Integration test flow structure (how many end-to-end scenarios to write)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Test execution | Test harness (pytest) | -- | All tests are unit/integration tests run by pytest |
| Auth middleware verification | Test harness | API/Backend | Tests exercise middleware via FastAPI TestClient |
| Route integration testing | Test harness | API/Backend | Tests exercise route handlers with real auth config |
| Edge case verification | Test harness | -- | Pure test logic, no production code changes expected |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | (existing) | Test runner | Already in use, project standard [VERIFIED: existing pyproject.toml] |
| FastAPI TestClient | (existing) | HTTP integration testing | Already in use across all 4 test files [VERIFIED: codebase] |
| unittest.mock | (stdlib) | MagicMock for app.state | Already in use in test_auth_middleware.py [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest.mark.parametrize | (builtin) | Mode-specific test variations | Auth mode isolation tests (D-09) where behavior differs by mode |

### Alternatives Considered
None. The stack is already established. No new dependencies needed.

## Architecture Patterns

### Existing Test Architecture

```
tests/
  conftest.py              -> make_settings() factory, default_state()
  test_auth_config.py      -> AuthConfig model + Settings integration (11 tests)
  test_auth_helpers.py     -> auth.py helper functions (17 tests)
  test_auth_middleware.py   -> AuthMiddleware deny-all dispatch (21 tests)
  test_auth_routes.py      -> Route integration: setup/login/logout/settings (37 tests)
  test_auth_integration.py -> [NEW] Cross-cutting e2e flows (D-02)
```

### Pattern 1: Middleware Unit Tests (test_auth_middleware.py)
**What:** Minimal FastAPI app via `_make_auth_app()` with mock settings, no real routes/templates.
**When to use:** Testing middleware behavior in isolation -- exempt paths, mode dispatch, cookie/key validation.
**Example:**
```python
# Source: tests/test_auth_middleware.py (existing pattern)
def _make_auth_app(auth_config: AuthConfig | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    settings = MagicMock()
    settings.auth = auth_config or AuthConfig()
    app.state.settings = settings
    # ... stub routes
    return app
```

### Pattern 2: Route Integration Tests (test_auth_routes.py)
**What:** Full FastAPI app via `_make_route_app()` with real router, templates, static files.
**When to use:** Testing actual HTML responses, form submissions, cookie setting, TOML writes.
**Example:**
```python
# Source: tests/test_auth_routes.py (existing pattern)
def _make_route_app(auth_config=None, config_path=None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    # ... mount static, set app.state
    return app
```

### Pattern 3: Integration Flow Tests (test_auth_integration.py - NEW)
**What:** Multi-step scenarios that span setup -> login -> authenticated access -> logout.
**When to use:** Verifying cross-cutting flows where state carries between requests.
**Example pattern:**
```python
# Reuse _make_route_app from test_auth_routes.py or duplicate locally
def test_full_setup_login_use_logout_flow(tmp_path):
    """Complete flow: setup -> login -> access protected route -> logout -> denied."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    # Step 1: Setup creates credentials
    # Step 2: Login with those credentials
    # Step 3: Access protected route with session cookie
    # Step 4: Logout
    # Step 5: Verify access denied
```

### Anti-Patterns to Avoid
- **Duplicating existing tests:** D-05 says existing TDD tests count. Do not re-test what's already covered.
- **Mocking auth helpers:** Existing pattern calls real `hash_password()`, `sign_session()`, etc. Keep this -- mocking crypto defeats the purpose.
- **Using `follow_redirects=True` for redirect assertions:** Always use `follow_redirects=False` when testing redirect behavior, as established in existing tests.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP testing | Raw httpx async client | FastAPI TestClient (sync) | Established project pattern, simpler, no async test complexity |
| Cookie management | Manual header manipulation | TestClient cookies param | TestClient handles cookie jar correctly |
| Auth config construction | Inline AuthConfig with all fields | `_configured_auth()` helper | Already exists in both middleware and routes test files |

## Coverage Gap Analysis

### SC-1: Middleware enforcement (redirect/401 + /health exempt)

| Behavior | Existing Test | Gap? |
|----------|--------------|------|
| /health accessible without auth | `test_health_no_auth` | No |
| /static exempt | `test_static_no_auth` | No |
| /login exempt | `test_login_no_auth` | No |
| /setup exempt | `test_setup_no_auth` | No |
| Unauth browser -> 302 /login | `test_unauth_browser_redirects_to_login` | No |
| Unauth API -> 401 JSON | `test_unauth_api_returns_401` | No |
| Needs-setup browser -> 302 /setup | `test_needs_setup_browser_redirects_to_setup` | No |
| Needs-setup API -> 401 + setup_url | `test_needs_setup_api_returns_401_with_setup_url` | No |
| /health returns {"status":"ok"} body | -- | **YES** (existing test checks 200 status but not body) |
| Unauth browser redirect includes ?next= | `test_unauth_browser_redirects_to_login` | Partially (checks `/login?next=/` but not deeper paths) |

**Gap count: ~1-2 tests**

### SC-2: First-run setup flow

| Behavior | Existing Test | Gap? |
|----------|--------------|------|
| /setup renders when needs_setup | `test_setup_page_renders_when_needs_setup` | No |
| POST /setup creates credentials | `test_setup_post_creates_credentials` | No |
| POST /setup shows API key | `test_setup_post_creates_credentials` (checks `api-key-display`) | No |
| /setup returns 404 after config | `test_setup_page_returns_404_when_configured` | No |
| POST /setup returns 404 after config | `test_setup_post_returns_404_when_configured` | No |
| POST /setup password mismatch error | `test_setup_post_password_mismatch_shows_error` | No |
| POST /setup empty password error | `test_setup_post_empty_password_shows_error` | No |
| POST /setup sets session cookie | `test_setup_post_sets_session_cookie` | No |
| Setup redirect from all routes | `test_needs_setup_browser_redirects_to_setup` | No |
| Setup empty username error | -- | **YES** (no test for empty username submission) |

**Gap count: ~1 test**

### SC-3: Login/logout with session lifecycle

| Behavior | Existing Test | Gap? |
|----------|--------------|------|
| Login page renders | `test_login_page_renders` | No |
| Valid login -> redirect + cookie | `test_login_post_valid_credentials_redirects` | No |
| Invalid login -> error | `test_login_post_invalid_credentials_shows_error` | No |
| Login respects ?next= | `test_login_post_respects_next_param` | No |
| Login rejects open redirect | `test_login_post_rejects_open_redirect_next` | No |
| Already-authed login redirect | `test_login_page_redirects_when_authenticated` | No |
| Logout clears cookie + redirect | `test_logout_clears_cookie_and_redirects` | No |
| Valid session cookie passes | `test_valid_session_cookie_passes_through` | No |
| 30-day cookie expiry | `test_cookie_max_age_is_30_days` + `test_validate_session_expired_returns_none` | No |
| Cookie max-age=30d in Set-Cookie | -- | **YES** (no test verifies Set-Cookie max-age value on login) |
| Session cookie with wrong secret rejected at middleware level | -- | **YES** (D-07: only tested at helper level, not middleware) |
| Expired session cookie rejected at middleware level | -- | **YES** (only tested at helper level) |
| Login wrong username | -- | **YES** (only wrong password tested at route level) |
| Login empty fields | -- | **YES** (no test for empty username/password submission) |

**Gap count: ~4-5 tests**

### SC-4: Auth mode behavior (Forms/Basic/External/Disabled)

| Behavior | Existing Test | Gap? |
|----------|--------------|------|
| Forms redirect to /login | `test_unauth_browser_redirects_to_login` | No |
| Basic returns WWW-Authenticate | `test_basic_auth_missing_authorization_returns_401` | No |
| Basic valid creds -> 200 + cookie | `test_basic_auth_valid_credentials_passes`, `test_basic_auth_valid_sets_session_cookie` | No |
| Basic invalid creds -> 401 | `test_basic_auth_invalid_credentials_returns_401` | No |
| Basic wrong username -> 401 | `test_basic_auth_wrong_username_returns_401` | No |
| Basic malformed header -> 401 | `test_basic_auth_malformed_header_returns_401`, `test_basic_auth_missing_colon_returns_401` | No |
| External passthrough | `test_external_mode_passes_through` | No |
| Disabled passthrough | `test_disabled_mode_passes_through` | No |
| Session cookie works in Basic mode | `test_session_cookie_works_in_basic_mode` | No |
| Disabled startup warning log fires | -- | **YES** (D-11: not implemented in code yet -- see Open Questions) |
| Forms->Basic transition: session still valid | -- | **YES** (D-10) |
| Any->Disabled transition: warning logged | -- | **YES** (D-10) |
| Disabled->Forms transition: re-requires login | -- | **YES** (D-10) |
| API key works across all active modes | -- | **YES** (only tested in Forms mode) |

**Gap count: ~4-5 tests**

### SC-5: API key authentication

| Behavior | Existing Test | Gap? |
|----------|--------------|------|
| Valid X-Api-Key passes | `test_valid_api_key_passes_through` | No |
| Invalid X-Api-Key fails | `test_invalid_api_key_does_not_pass` | Partially (doesn't check specific 401 JSON response) |
| Missing X-Api-Key with no other auth -> 401 | -- | **YES** (tested as general unauth, not API-key-specific) |
| Empty X-Api-Key header | -- | **YES** (D-06) |
| Whitespace X-Api-Key header | -- | **YES** (D-06) |
| Invalid API key returns 401 JSON (not redirect) | -- | **YES** (existing test only checks `!= 200`) |

**Gap count: ~3-4 tests**

### Cross-cutting integration (test_auth_integration.py)

| Flow | Existing Test | Gap? |
|------|--------------|------|
| Setup -> login -> access -> logout -> denied | -- | **YES** (D-02) |
| Setup -> API key access works immediately | -- | **YES** |
| Login -> change password -> old session still valid | -- | **YES** |

**Gap count: ~3 tests**

### Edge Cases (D-06, D-07)

| Edge Case | Existing Test | Gap? |
|-----------|--------------|------|
| Tampered cookie at helper level | `test_validate_session_tampered_returns_none` | No |
| Wrong secret at helper level | `test_validate_session_wrong_secret_returns_none` | No |
| None cookie at helper level | `test_validate_session_none_cookie_returns_none` | No |
| Expired cookie at helper level | `test_validate_session_expired_returns_none` | No |
| Tampered cookie at middleware level | -- | **YES** |
| Wrong secret at middleware level (D-07) | -- | **YES** |
| Open redirect in ?next= (GET /login) | -- | **YES** (only POST tested) |
| Protocol-relative ?next= | -- | **YES** |
| Setup POST after already configured | `test_setup_post_returns_404_when_configured` | No |

**Gap count: ~4 tests**

### Total Estimated New Tests: 20-25

## Common Pitfalls

### Pitfall 1: TestClient Cookie Deprecation Warning
**What goes wrong:** `DeprecationWarning: Setting per-request cookies=<...> is being deprecated`.
**Why it happens:** Starlette TestClient is deprecating per-request cookie kwargs in favor of client-level cookie setting.
**How to avoid:** Use `client.cookies.set("triggarr_session", value)` instead of `cookies={"triggarr_session": value}` in request calls. Or accept the warning for now since tests still pass.
**Warning signs:** 14 warnings already present in current test output. [VERIFIED: test run output]

### Pitfall 2: Duplicate Helper Functions
**What goes wrong:** `_configured_auth()` and `_make_auth_app()` are defined in BOTH `test_auth_middleware.py` and `test_auth_routes.py` with slight differences.
**Why it happens:** Phase 55 and 56 were developed independently.
**How to avoid:** For new `test_auth_integration.py`, either import from one of the existing files or create shared fixtures. Do NOT add a third copy. Consider moving shared helpers to conftest.py.
**Warning signs:** If you see `_configured_auth` defined in 3+ files.

### Pitfall 3: Auth State Leakage Between Tests
**What goes wrong:** `auth_state` is a module-level mutable dict. Tests that modify it can affect subsequent tests.
**Why it happens:** Template globals are shared across the module.
**How to avoid:** The `_reset_auth_state` autouse fixture in `test_auth_routes.py` handles this. The new `test_auth_integration.py` MUST also include this fixture or import it.
**Warning signs:** Tests pass individually but fail when run together.

### Pitfall 4: Disabled Warning Log Not Implemented
**What goes wrong:** D-11 says to test that the disabled mode warning log fires, but no such log exists in the codebase.
**Why it happens:** LOGIN-05 specifies "startup warning logged every 60s" but this was deferred or missed in Phase 57.
**How to avoid:** The test should verify the warning log fires during startup/lifespan, not the 60-second interval. If the warning code doesn't exist, the test will correctly fail and the code needs to be added as part of this phase or flagged.
**Warning signs:** Test for log message fails because no logger.warning call exists.

## Code Examples

### Traceability Comment Block (D-03)
```python
# Source: CONTEXT.md D-03 requirement
"""Tests for [module] -- Phase 58 gap-fill.

Traceability:
  SC-1 (middleware enforcement): test_health_returns_ok_body, ...
  SC-3 (session lifecycle): test_wrong_secret_cookie_rejected_by_middleware, ...
  SC-5 (API key auth): test_missing_api_key_returns_401_json, ...
"""
```

### API Key Edge Case Tests Pattern
```python
# Pattern for SC-5 gap tests in test_auth_middleware.py
def test_missing_api_key_api_returns_401_json():
    """API request with no X-Api-Key and no session gets 401 JSON (not redirect)."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_empty_api_key_does_not_pass():
    """Request with empty X-Api-Key header does not authenticate."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": "", "Accept": "application/json"})
    assert response.status_code == 401
```

### Wrong Secret Cookie at Middleware Level (D-07)
```python
# Pattern for D-07 gap test in test_auth_middleware.py
def test_wrong_secret_cookie_rejected_by_middleware():
    """Session cookie signed with different secret is rejected by middleware (D-07)."""
    different_secret = generate_session_secret()
    auth = _configured_auth()  # uses _SESSION_SECRET
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    wrong_cookie = sign_session("admin", different_secret)
    response = client.get("/", cookies={"triggarr_session": wrong_cookie}, headers={"Accept": "text/html"})
    assert response.status_code == 302  # redirected to login
```

### Integration Flow Pattern (D-02)
```python
# Pattern for test_auth_integration.py
def test_full_lifecycle(tmp_path):
    """Setup -> login -> access protected -> logout -> denied."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)

    # 1. Setup
    resp = client.post("/setup", data={...})
    assert resp.status_code == 200
    session_cookie = resp.cookies.get("triggarr_session")

    # 2. Access protected route with session
    resp = client.get("/", cookies={"triggarr_session": session_cookie})
    assert resp.status_code == 200

    # 3. Logout
    resp = client.post("/logout", cookies={"triggarr_session": session_cookie})
    assert resp.status_code == 303

    # 4. Access denied without cookie
    resp = client.get("/", headers={"Accept": "text/html"})
    assert resp.status_code == 302
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Disabled mode startup warning log is not implemented in any module | Coverage Gap Analysis SC-4 | If it exists in code I missed, the gap for D-11 is smaller (just need the test, not the code). LOW risk -- thorough grep found nothing. |
| A2 | ~20-25 new tests will achieve full SC-1 through SC-5 coverage | Coverage Gap Analysis | If more gaps exist, planner may need to add tasks. LOW risk -- audit was thorough. |

## Open Questions

1. **Disabled mode startup warning (D-11 / LOGIN-05)**
   - What we know: The design spec says "logs a prominent warning every 60 seconds." No such warning exists in `startup.py`, `__main__.py`, `scheduler.py`, or middleware.
   - What's unclear: Was this intentionally deferred from Phase 57, or is it a gap?
   - Recommendation: Phase 58 tests should include a test that the warning fires. If the code doesn't exist, either: (a) add the warning log in a small code addition within this phase, or (b) write the test as `@pytest.mark.xfail` with a note. The CONTEXT.md D-11 explicitly says to verify the warning fires, which implies the code should exist.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_auth_integration.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SC-1 | Middleware enforcement | unit | `uv run pytest tests/test_auth_middleware.py -x -q` | Yes (gap-fill) |
| SC-2 | Setup flow | integration | `uv run pytest tests/test_auth_routes.py -x -q -k setup` | Yes (gap-fill) |
| SC-3 | Login/logout/session | integration | `uv run pytest tests/test_auth_routes.py -x -q -k login` | Yes (gap-fill) |
| SC-4 | Auth mode behavior | unit+integration | `uv run pytest tests/test_auth_middleware.py tests/test_auth_routes.py -x -q` | Yes (gap-fill) |
| SC-5 | API key auth | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k api_key` | Yes (gap-fill) |
| Cross | Integration flows | integration | `uv run pytest tests/test_auth_integration.py -x -q` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth_config.py tests/test_auth_helpers.py tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_auth_integration.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth_integration.py` -- new file for cross-cutting flows (D-02)
- [ ] Traceability comment blocks in all 5 test files (D-03)

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys -- call `.get_secret_value()` only at HTTP client init
- Loguru for logging (never print/logging module)
- pytest-asyncio with asyncio_mode=auto
- Test command: `uv run pytest tests/ -x -q`
- Lint command: `uv run ruff check triggarr/ tests/`

## Sources

### Primary (HIGH confidence)
- Codebase audit: `tests/test_auth_config.py` (11 tests), `tests/test_auth_helpers.py` (17 tests), `tests/test_auth_middleware.py` (21 tests), `tests/test_auth_routes.py` (37 tests) -- all 86 tests verified passing
- Codebase audit: `triggarr/auth.py` -- all helper functions reviewed
- Codebase audit: `triggarr/web/middleware.py` -- AuthMiddleware dispatch order verified
- Codebase audit: `triggarr/web/routes.py` -- auth routes, settings endpoints, auth_state reviewed
- Design spec: `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- auth flow, modes, session management

### Secondary (MEDIUM confidence)
- Coverage gap analysis performed by manually mapping each test name to SC-1 through SC-5 criteria

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new deps, all tools already in use
- Architecture: HIGH -- test patterns fully established, just gap-filling
- Pitfalls: HIGH -- verified warnings in test output, confirmed auth_state fixture pattern
- Coverage gaps: HIGH -- manual audit of 86 tests against 5 success criteria

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable -- test infrastructure unlikely to change)
