"""Tests for auth helper functions: password hashing, cookie signing, token generation."""

from __future__ import annotations

import re

from triggarr.auth import (
    COOKIE_MAX_AGE,
    generate_api_key,
    generate_session_secret,
    hash_password,
    sign_session,
    validate_session,
    verify_password,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_cookie_max_age_is_30_days() -> None:
    """COOKIE_MAX_AGE equals exactly 30 days in seconds."""
    assert COOKIE_MAX_AGE == 30 * 24 * 60 * 60
    assert COOKIE_MAX_AGE == 2592000


# ---------------------------------------------------------------------------
# Password hashing (bcrypt, 12 rounds)
# ---------------------------------------------------------------------------


def test_hash_password_returns_bcrypt_hash() -> None:
    """hash_password returns a bcrypt hash string starting with $2b$12$."""
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2b$12$")


def test_hash_password_unique_salt_each_time() -> None:
    """hash_password produces different hashes for the same input."""
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2


def test_verify_password_correct() -> None:
    """verify_password returns True for matching password."""
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong() -> None:
    """verify_password returns False for wrong password."""
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


# ---------------------------------------------------------------------------
# API key generation (secrets.token_hex(16))
# ---------------------------------------------------------------------------


def test_generate_api_key_length() -> None:
    """generate_api_key returns a 32-character string."""
    key = generate_api_key()
    assert len(key) == 32


def test_generate_api_key_hex_chars() -> None:
    """generate_api_key contains only valid hex characters."""
    key = generate_api_key()
    assert re.fullmatch(r"[0-9a-f]{32}", key)


def test_generate_api_key_unique() -> None:
    """generate_api_key produces different values each call."""
    k1 = generate_api_key()
    k2 = generate_api_key()
    assert k1 != k2


# ---------------------------------------------------------------------------
# Session secret generation (secrets.token_hex(32))
# ---------------------------------------------------------------------------


def test_generate_session_secret_length() -> None:
    """generate_session_secret returns a 64-character string."""
    secret = generate_session_secret()
    assert len(secret) == 64


def test_generate_session_secret_hex_chars() -> None:
    """generate_session_secret contains only valid hex characters."""
    secret = generate_session_secret()
    assert re.fullmatch(r"[0-9a-f]{64}", secret)


def test_generate_session_secret_unique() -> None:
    """generate_session_secret produces different values each call."""
    s1 = generate_session_secret()
    s2 = generate_session_secret()
    assert s1 != s2


# ---------------------------------------------------------------------------
# Cookie signing (itsdangerous.TimestampSigner, 30-day max_age)
# ---------------------------------------------------------------------------


def test_sign_session_returns_nonempty_string() -> None:
    """sign_session returns a non-empty signed string."""
    secret = generate_session_secret()
    signed = sign_session("admin", secret)
    assert isinstance(signed, str)
    assert len(signed) > 0


def test_sign_session_validate_roundtrip() -> None:
    """sign_session + validate_session round-trips correctly."""
    secret = generate_session_secret()
    signed = sign_session("admin", secret)
    assert validate_session(signed, secret) == "admin"


def test_validate_session_tampered_returns_none() -> None:
    """validate_session rejects a tampered cookie value."""
    secret = generate_session_secret()
    assert validate_session("tampered-value", secret) is None


def test_validate_session_none_cookie_returns_none() -> None:
    """validate_session returns None when cookie_value is None (missing cookie)."""
    secret = generate_session_secret()
    assert validate_session(None, secret) is None


def test_validate_session_wrong_secret_returns_none() -> None:
    """validate_session rejects a cookie signed with a different secret."""
    secret1 = generate_session_secret()
    secret2 = generate_session_secret()
    signed = sign_session("admin", secret1)
    assert validate_session(signed, secret2) is None


def test_validate_session_expired_returns_none() -> None:
    """validate_session rejects an expired cookie (>30 days)."""
    from unittest.mock import patch

    from itsdangerous import TimestampSigner

    secret = generate_session_secret()
    signed = sign_session("admin", secret)

    # Patch get_timestamp on TimestampSigner to simulate 31 days in the future.
    # itsdangerous 2.x uses self.get_timestamp() to get current epoch seconds.
    original_get_timestamp = TimestampSigner.get_timestamp

    def future_timestamp(self: TimestampSigner) -> int:
        return original_get_timestamp(self) + (31 * 24 * 60 * 60)

    with patch.object(TimestampSigner, "get_timestamp", future_timestamp):
        result = validate_session(signed, secret)
    assert result is None
