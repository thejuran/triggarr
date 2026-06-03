---
phase: 72
slug: password-reset-backend-token-lifecycle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 72 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `72-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio, `asyncio_mode=auto` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_reset.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~quick <5s / full ~60s (984 baseline tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_reset.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green (984 baseline preserved + new reset tests)
- **Max feedback latency:** ~5 seconds (quick), ~60 seconds (full)

---

## Per-Task Verification Map

| Req | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| RCOV-02 | POST /reset/request mints token in state; NOT in response | T-72-redaction | Token never in body/headers | integration | `uv run pytest tests/test_reset.py::test_request_mints_token -x` | ❌ W0 | ⬜ pending |
| RCOV-02 | Token file written `config_path.parent/reset-token.txt` mode 0600 | T-72-fileperm | 0600 perms, atomic write | integration | `uv run pytest tests/test_reset.py::test_token_file_written_0600 -x` | ❌ W0 | ⬜ pending |
| RCOV-02 | Token value not in HTTP response body or headers | T-72-redaction | No token leak in response | integration | `uv run pytest tests/test_reset.py::test_token_not_in_response -x` | ❌ W0 | ⬜ pending |
| RCOV-03 | Token stored with 900s TTL (expiry = monotonic + 900) | — | TTL bounded | unit | `uv run pytest tests/test_reset.py::test_token_ttl_stored_correctly -x` | ❌ W0 | ⬜ pending |
| RCOV-03 | Expired token rejected (monotonic injectable) | T-72-expiry | Generic reject, no state change | unit | `uv run pytest tests/test_reset.py::test_expired_token_rejected -x` | ❌ W0 | ⬜ pending |
| RCOV-03 | New mint invalidates prior token | — | Supersession | unit | `uv run pytest tests/test_reset.py::test_new_mint_supersedes_prior -x` | ❌ W0 | ⬜ pending |
| RCOV-03 | Single-use: confirmed token cannot be reused | T-72-replay | One-time use | integration | `uv run pytest tests/test_reset.py::test_token_single_use -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | Valid token + matching password → 303 dashboard + cookie | — | Auto-login on success | integration | `uv run pytest tests/test_reset.py::test_confirm_success_redirects_with_cookie -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | `session_secret` rotated in persisted TOML | T-72-session | Old sessions invalidated | integration | `uv run pytest tests/test_reset.py::test_confirm_rotates_session_secret -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | Pre-reset cookie fails `validate_session` after reset | T-72-session | Rotation evicts old cookies | integration | `uv run pytest tests/test_reset.py::test_pre_reset_cookie_invalid_after_reset -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | New cookie validates under new secret | — | Fresh session works | integration | `uv run pytest tests/test_reset.py::test_new_cookie_validates_after_reset -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | Wrong token → generic error, no state change | T-72-enum | No detail leak | integration | `uv run pytest tests/test_reset.py::test_wrong_token_generic_error -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | Password mismatch → per-field error | — | Inline field error | integration | `uv run pytest tests/test_reset.py::test_password_mismatch_field_error -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | Empty password → per-field error | — | Inline field error | integration | `uv run pytest tests/test_reset.py::test_empty_password_field_error -x` | ❌ W0 | ⬜ pending |
| RCOV-04 | >72-byte password → per-field error (bcrypt limit) | — | ValueError surfaced as field error | integration | `uv run pytest tests/test_reset.py::test_password_too_long_field_error -x` | ❌ W0 | ⬜ pending |
| RCOV-05 | Second /reset/request within 60s → 429 | T-72-flood | Throttle log/file flooding | integration | `uv run pytest tests/test_reset.py::test_request_rate_limited -x` | ❌ W0 | ⬜ pending |
| RCOV-05 | Rapid /reset/confirm attempts → 429 | T-72-bruteforce | Throttle token guessing | integration | `uv run pytest tests/test_reset.py::test_confirm_rate_limited -x` | ❌ W0 | ⬜ pending |
| RCOV-06 | GET /reset/request reachable unauthenticated | — | Exempt prefix reachable logged-out | integration | `uv run pytest tests/test_reset.py::test_reset_routes_unauthenticated -x` | ❌ W0 | ⬜ pending |
| RCOV-06 | /reset/* does not expose any other authenticated route | T-72-overexpose | Prefix scope is /reset only | integration | `uv run pytest tests/test_reset.py::test_no_other_route_exposed -x` | ❌ W0 | ⬜ pending |
| RCOV-06 | Token file deleted after successful reset | T-72-cleanup | No stale token on disk | integration | `uv run pytest tests/test_reset.py::test_token_file_deleted_on_success -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · ❌ W0 = file created in Wave 0*

---

## Wave 0 Requirements

- [ ] `tests/test_reset.py` — all tests listed above (new file, does not exist yet)

*Existing test infrastructure covers all ancillary needs: `tests/conftest.py` shared fixtures, the `_make_route_app` helper + cookie/TOML assertion patterns + `monkeypatch` of `time.monotonic` + session-rotation tests in `tests/test_auth_routes.py` (lines ~604–707), and `tomllib` for TOML verification. Only the new `tests/test_reset.py` file is a Wave 0 gap.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator reads token from `docker logs` | RCOV-02 | Requires a real container + log stream | Milestone-end NAS walkthrough: forgot-password → read token from `docker logs` → complete reset |
| Operator reads token from mounted config volume | RCOV-02 | Requires a real volume mount | Walkthrough: `cat /config/reset-token.txt` on the deployed build |

*All in-process behaviors (token lifecycle, rate-limit, session rotation, redaction, middleware reachability) have automated verification above. Only the two operator-facing read channels are walkthrough-verified.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`tests/test_reset.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (full suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
