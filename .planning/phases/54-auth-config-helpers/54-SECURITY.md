---
phase: 54-auth-config-helpers
threats_total: 8
threats_closed: 8
threats_open: 0
status: SECURED
asvs_level: 1
audited: "2026-04-14"
---

# Phase 54 Security Audit: auth-config-helpers

## Summary

All 8 threats verified. 7 mitigations confirmed present in source and test files. 1 accepted risk documented below.

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-54-01 | Info Disclosure | mitigate | CLOSED | `triggarr/models/config.py:92-94` — `password_hash`, `api_key`, `session_secret` all typed `SecretStr`. `triggarr/startup.py:70-73` — `collect_secrets()` iterates all three for log redaction. Test: `tests/test_auth_config.py:97-109` `test_collect_secrets_includes_auth_secrets` |
| T-54-02 | Tampering | mitigate | CLOSED | `triggarr/models/config.py:90` — `method: Literal["Forms", "Basic", "External", "Disabled"]`. Test: `tests/test_auth_config.py:55-58` `test_auth_config_rejects_invalid_method` raises `ValidationError` |
| T-54-03 | Info Disclosure | mitigate | CLOSED | `SecretStr` renders as `**********` in `str()`, `repr()`, and `model_dump_json()`. Test: `tests/test_auth_config.py:66-76` `test_auth_config_secretstr_masking` asserts secret absent from all three |
| T-54-04 | Info Disclosure | mitigate | CLOSED | `triggarr/auth.py:47` — `bcrypt.checkpw(raw, hashed.encode())` — constant-time comparison. No `==` operator used for hash comparison anywhere in auth.py |
| T-54-05 | Spoofing | mitigate | CLOSED | `triggarr/auth.py:58` — `secrets.token_hex(16)`. No `import random` present in auth.py. Test: `tests/test_auth_helpers.py:69-72` verifies 32-char lowercase hex output |
| T-54-06 | Tampering | mitigate | CLOSED | `triggarr/auth.py:84,102-105` — `TimestampSigner` HMAC signing; `validate_session` catches `BadSignature` and returns `None`. Test: `tests/test_auth_helpers.py:126-129` `test_validate_session_tampered_returns_none` and `138-143` `test_validate_session_wrong_secret_returns_none` |
| T-54-07 | Spoofing | mitigate | CLOSED | `triggarr/auth.py:104` — `signer.unsign(cookie_value, max_age=COOKIE_MAX_AGE)` where `COOKIE_MAX_AGE = 2592000`. `SignatureExpired` caught at line 105, returns `None`. Test: `tests/test_auth_helpers.py:146-164` `test_validate_session_expired_returns_none` mocks 31-day-forward timestamp |
| T-54-08 | EoP | accept | CLOSED | Accepted risk — see Accepted Risks log below |

## Accepted Risks

| Threat ID | Category | Rationale | Implementation Note |
|-----------|----------|-----------|---------------------|
| T-54-08 | Elevation of Privilege (bcrypt 72-byte limit) | Single-user homelab application. The probability of a legitimate password exceeding 72 UTF-8 bytes is negligible in this deployment context. bcrypt 5.0+ raises `ValueError` on oversized input rather than silently truncating. | `triggarr/auth.py:26-28` — `hash_password` raises `ValueError` for passwords exceeding 72 bytes. `verify_password` returns `False` for the same condition. This is a defence-in-depth improvement beyond what the accepted disposition requires. |

## Unregistered Flags

None. Neither `54-01-SUMMARY.md` nor `54-02-SUMMARY.md` contains a `## Threat Flags` section.

## Files Verified

- `triggarr/auth.py` — auth helpers: bcrypt hashing, CSPRNG generation, itsdangerous signing
- `triggarr/models/config.py` — `AuthConfig` model with `SecretStr` fields and `Literal` method validation
- `triggarr/startup.py` — `collect_secrets()` extended for auth secret redaction
- `tests/test_auth_config.py` — 11 tests covering model defaults, validation, SecretStr masking, Settings integration, collect_secrets
- `tests/test_auth_helpers.py` — 16 tests covering password hashing, CSPRNG generation, cookie sign/validate round-trip, tamper rejection, expiry rejection
