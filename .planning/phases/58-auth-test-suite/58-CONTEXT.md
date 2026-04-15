# Phase 58: Auth Test Suite - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

All authentication paths are covered by automated tests -- middleware enforcement, session lifecycle, setup flow, login/logout, API key auth, auth mode switching, and edge cases. This is a verification phase that validates all requirements from Phases 54-57 indirectly.

</domain>

<decisions>
## Implementation Decisions

### Test Organization
- **D-01:** Gap-fill existing test files (`test_auth_config.py`, `test_auth_helpers.py`, `test_auth_middleware.py`, `test_auth_routes.py`) rather than creating parallel files. Keeps tests co-located with the code they verify.
- **D-02:** One new file `test_auth_integration.py` for cross-cutting end-to-end flows (e.g., setup->login->use->logout) that span multiple modules.
- **D-03:** Each test file includes a traceability comment block at the top mapping tests to success criteria (SC-1 through SC-5). Makes full coverage verifiable at a glance.

### Coverage Gap Strategy
- **D-04:** Audit-then-fill approach. First pass: read all existing tests and map each to a success criterion. Second pass: write tests only for identified gaps. No duplicate coverage.
- **D-05:** Existing TDD tests from Phases 54-57 count toward coverage. Phase 58 fills what those phases didn't cover, not re-tests what they did.

### Edge Case Depth
- **D-06:** Security-focused edge cases: expired/tampered cookies, malformed Authorization headers, invalid API keys (wrong length, empty, whitespace), open redirect attempts in `?next=`, setup endpoint after auth already configured.
- **D-07:** Test session cookie signed with a different `session_secret` (simulating secret rotation or config tampering) -- verify it is rejected by middleware.
- **D-08:** Skip unlikely runtime scenarios: concurrent setup race conditions, partial config corruption, every possible malformed header variant. Focus on what an attacker or misconfiguration would actually produce.

### Auth Mode Switching
- **D-09:** Test each auth mode (Forms, Basic, External, Disabled) in isolation with its expected behavior.
- **D-10:** Test 2-3 key mode transitions: Forms->Basic (session cookie still valid?), any->Disabled (warning logged?), Disabled->Forms (re-requires login?). No exhaustive 4x4 permutation matrix.
- **D-11:** Disabled mode tests verify both passthrough behavior (requests pass unauthenticated) AND that the startup warning log message fires. Do not test the 60-second interval timing.

### Claude's Discretion
- Test helper/fixture structure (shared fixtures in conftest.py vs per-file helpers)
- Exact test names and grouping within each file
- Whether to use parametrize for mode-specific tests or separate test functions
- Integration test flow structure (how many end-to-end scenarios to write)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Specification
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- Full auth design: all four modes, middleware spec, session management, setup flow, settings security

### Prior Phase Context
- `.planning/phases/54-auth-config-helpers/54-CONTEXT.md` -- AuthConfig model, auth.py helpers, SecretStr discipline
- `.planning/phases/55-auth-middleware-health-endpoint/55-CONTEXT.md` -- Middleware placement, auth check order (D-10), exempt paths, Basic auth session handling
- `.planning/phases/56-first-run-setup-login/56-CONTEXT.md` -- Setup flow, login flow, logout, ?next= redirect, AIDesigner templates
- `.planning/phases/57-settings-security-nav-logout/57-CONTEXT.md` -- Settings security section, password change, API key management, auth mode dropdown

### Existing Test Files (audit these first)
- `tests/test_auth_config.py` (118 lines) -- AuthConfig model validation tests
- `tests/test_auth_helpers.py` (164 lines) -- Password hashing, cookie signing, API key generation tests
- `tests/test_auth_middleware.py` (317 lines) -- Middleware deny-all dispatch, D-10 check order tests
- `tests/test_auth_routes.py` (670 lines) -- Route integration tests: setup, login, logout, _safe_next_url

### Requirements
- `.planning/REQUIREMENTS.md` -- All SETUP-*, LOGIN-*, MID-*, SET-* requirements (Phase 58 validates all indirectly)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `conftest.py`: `make_settings()` factory for building Settings with test defaults
- `test_auth_middleware.py`: `_make_auth_app()` helper builds minimal FastAPI app with AuthMiddleware
- `test_auth_routes.py`: `_configured_auth()` helper, `_reset_auth_state` autouse fixture, full app setup with templates/static
- Auth helpers: `generate_session_secret()`, `hash_password()`, `sign_session()` used directly in tests

### Established Patterns
- FastAPI TestClient for synchronous HTTP testing (not async httpx)
- MagicMock for `app.state.settings` in middleware tests
- Real auth helpers called in tests (no mocking of crypto functions)
- `autouse` fixtures for state cleanup between tests

### Integration Points
- New `test_auth_integration.py` will reuse existing helpers from `test_auth_routes.py` and `test_auth_middleware.py`
- Traceability headers will reference SC-1 through SC-5 from ROADMAP.md success criteria

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 58-auth-test-suite*
*Context gathered: 2026-04-15*
