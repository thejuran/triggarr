# Plan 66-02: SEC-03 Basic Auth Hardening — SUMMARY

**Date:** 2026-05-26
**Plan:** 66-02-PLAN.md
**Requirement:** SEC-03 (Reject Basic auth credentials with null bytes / control characters; log decode failures at WARNING)
**Type:** TDD
**Wave:** 1
**Status:** Complete

## What Shipped

Hardened the Basic auth header decode path in `triggarr/web/middleware.py`:

1. Added module-level helper `_has_control_chars(s)` that returns True for any C0 control char (0x00–0x1F) or DEL (0x7F).
2. In `_handle_basic_auth`:
   - Compute `client_ip` once with `None` guard (`request.client` may be None — Pitfall 2).
   - Use `base64.b64decode(authorization[6:], validate=True)` so malformed payloads like `Basic !!!!` raise `binascii.Error` into the existing `except` branch (codex M3, 2026-05-26).
   - After successful decode, check username/password for control chars BEFORE `secrets.compare_digest`. Reject with WARNING + 401.
   - Replace the previously-silent `except (ValueError, UnicodeDecodeError): pass` with a `decode_failure` WARNING.

## Tasks Completed

| Task | Type | Outcome |
|------|------|---------|
| 1. RED — Add failing tests | tdd | 5 new tests: null_byte_in_password, control_char_in_username, del_in_password, decode_failure_logs_warning, non_ascii_password_accepted (regression guard) |
| 2. GREEN — Implement helper + handler changes | tdd | `_has_control_chars` helper added; `_handle_basic_auth` updated with strict base64 + control-char check + WARNING log for both rejection paths |
| 3. REFACTOR — Regression sweep | tdd | Verify-only; 42/42 auth-middleware tests pass; full suite green |

## Files Changed

| File | +/- |
|------|-----|
| `triggarr/web/middleware.py` | +22 −2 |
| `tests/test_auth_middleware.py` | +133 |

## Test Results

- `tests/test_auth_middleware.py` — 42 passed
- Full suite (`uv run pytest tests/ -x -q`) — 928 passed
- `uv run ruff check triggarr/ tests/` — All checks passed

## Key Decisions

1. **Control-char range `0x00..0x1F` + `0x7F` only** — not strict ASCII-printable. Matches CONTEXT D-09: conservative rejection that preserves legitimate non-ASCII (e.g., é, ñ) passwords.
2. **`validate=True` strict base64** — codex M3 (adversarial review). Without this, `base64.b64decode("!!!!")` silently returns `b""` and the decode_failure WARNING never fires.
3. **PII-minimal log format `"basic_auth_rejected reason={reason} client_ip={ip}"`** — D-10: only `event`, `reason`, `client_ip`. Username, decoded bytes, raw header all excluded. Negative grep in acceptance criteria enforces this.
4. **`request.client.host if request.client else "unknown"`** — Pitfall 2: `request.client` is `None` in some edge cases (TestClient with no HTTP/1.1 client info, unix-socket transport).

## Codex Adversarial Findings Addressed

- **M3 (non-strict base64):** `base64.b64decode(..., validate=True)` ensures malformed inputs raise `binascii.Error` (a `ValueError` subclass) into the existing `except` branch, firing the decode_failure WARNING.

## Decisions Covered

- D-09 (reject 0x00–0x1F + 0x7F) ✓
- D-10 (PII-min log: event, reason, client_ip only) ✓
- D-11 (WARNING on previously-silent decode failure) ✓
