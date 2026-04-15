---
phase: 54-auth-config-helpers
reviewed: 2026-04-14T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - pyproject.toml
  - tests/test_auth_config.py
  - tests/test_auth_helpers.py
  - triggarr/auth.py
  - triggarr/models/config.py
  - triggarr/startup.py
findings:
  critical: 2
  warning: 2
  info: 0
  total: 4
status: issues_found
---

# Phase 54: Code Review Report

**Reviewed:** 2026-04-14
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

The new auth module introduces password hashing (bcrypt), cookie signing (itsdangerous), API key generation, and a Pydantic `AuthConfig` model integrated into `Settings`. The `collect_secrets` function in `startup.py` is correctly extended to redact auth secrets from logs.

The cryptographic primitives are well-chosen (bcrypt 12 rounds, `secrets.token_hex`, `TimestampSigner` with `max_age`). However, there are two critical issues: (1) `hash_password` crashes on passwords longer than 72 bytes due to the bcrypt library raising `ValueError`, and (2) `sign_session` accepts an empty secret string without complaint, producing trivially forgeable session cookies. Two additional warnings cover `verify_password` crashing on an empty/invalid hash and an assertion gap in a test.

## Critical Issues

### CR-01: hash_password crashes on passwords exceeding 72 bytes

**File:** `triggarr/auth.py:22`
**Issue:** The `bcrypt` library (modern versions) raises `ValueError: password cannot be longer than 72 bytes` when the plaintext exceeds 72 bytes. Since `hash_password` performs no length check or truncation, any user entering a long password will get an unhandled 500 error instead of a clean validation message. This is a crash bug on user input.
**Fix:**
```python
def hash_password(plaintext: str) -> str:
    raw = plaintext.encode()
    if len(raw) > 72:
        msg = "Password must be 72 bytes or fewer"
        raise ValueError(msg)
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode()
```
Alternatively, truncate silently with `raw[:72]`, but an explicit error is more transparent. Either way, add a corresponding test.

### CR-02: sign_session accepts empty secret, producing forgeable cookies

**File:** `triggarr/auth.py:66`
**Issue:** `TimestampSigner("")` happily signs and verifies tokens. If auth is configured but `session_secret` remains at its default empty string (e.g., a misconfigured TOML file), all session cookies are signed with an empty key. An attacker who knows this can forge arbitrary session cookies. The function should refuse to operate with an empty secret.
**Fix:**
```python
def sign_session(username: str, secret: str) -> str:
    if not secret:
        raise ValueError("session_secret must not be empty")
    signer = TimestampSigner(secret)
    return signer.sign(username).decode()


def validate_session(cookie_value: str, secret: str) -> str | None:
    if not secret:
        return None
    signer = TimestampSigner(secret)
    try:
        return signer.unsign(cookie_value, max_age=COOKIE_MAX_AGE).decode()
    except (SignatureExpired, BadSignature):
        return None
```

## Warnings

### WR-01: verify_password crashes with ValueError on empty or invalid hash

**File:** `triggarr/auth.py:35`
**Issue:** `bcrypt.checkpw(password, b"")` raises `ValueError: Invalid salt`. Since `AuthConfig.password_hash` defaults to `SecretStr("")`, any code path that calls `verify_password(input, settings.auth.password_hash.get_secret_value())` before setup completes will crash instead of returning `False`. The function should handle invalid hashes gracefully.
**Fix:**
```python
def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False
```

### WR-02: Test assertion does not actually verify absence of auth secrets

**File:** `tests/test_auth_config.py:118`
**Issue:** The assertion `assert len([s for s in secrets if s in ("",)]) == 0` checks that no element in `secrets` equals the empty string -- it does not verify that auth secrets were excluded. If `collect_secrets` accidentally included empty strings, this would catch it, but if it included some non-empty default, the test would still pass. A more robust assertion would check the total count or specific absence.
**Fix:**
```python
def test_collect_secrets_skips_empty_auth_secrets() -> None:
    """collect_secrets does not include empty auth secret values."""
    settings = Settings()
    # Default AuthConfig has empty radarr/sonarr + empty auth secrets
    secrets = collect_secrets(settings)
    # With no instances and default (empty) auth, there should be zero secrets
    assert secrets == []
```

---

_Reviewed: 2026-04-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
