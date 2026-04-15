"""Authentication helpers: password hashing, cookie signing, and token generation."""

from __future__ import annotations

import secrets

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds).

    Args:
        plaintext: The password to hash.

    Returns:
        Bcrypt hash string suitable for storage.

    Raises:
        ValueError: If password exceeds 72 bytes (bcrypt limit).
    """
    raw = plaintext.encode()
    if len(raw) > 72:
        msg = "Password must be 72 bytes or fewer"
        raise ValueError(msg)
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plaintext: The password to verify.
        hashed: The stored bcrypt hash.

    Returns:
        True if the password matches the hash, False for mismatches
        or invalid inputs (empty hash, malformed hash, >72-byte password).
    """
    raw = plaintext.encode()
    if len(raw) > 72:
        return False
    try:
        return bcrypt.checkpw(raw, hashed.encode())
    except (ValueError, TypeError):
        return False


def generate_api_key() -> str:
    """Generate a 32-character hex API key using CSPRNG.

    Returns:
        Cryptographically random 32-character hex string.
    """
    return secrets.token_hex(16)


def generate_session_secret() -> str:
    """Generate a 64-character hex session secret using CSPRNG.

    Returns:
        Cryptographically random 64-character hex string.
    """
    return secrets.token_hex(32)


def sign_session(username: str, secret: str) -> str:
    """Create a signed session cookie value.

    Args:
        username: The authenticated username to embed.
        secret: The session secret from config.

    Returns:
        Signed cookie string safe for HTTP Set-Cookie.
    """
    if not username:
        raise ValueError("username must not be empty")
    if not secret:
        raise ValueError("session_secret must not be empty")
    signer = TimestampSigner(secret)
    return signer.sign(username).decode()


def validate_session(cookie_value: str | None, secret: str) -> str | None:
    """Validate a signed session cookie and extract the username.

    Args:
        cookie_value: The raw cookie value from the request, or None if missing.
        secret: The session secret from config.

    Returns:
        The username if valid and not expired, None otherwise.
    """
    if not secret:
        return None
    if cookie_value is None:
        return None
    signer = TimestampSigner(secret)
    try:
        return signer.unsign(cookie_value, max_age=COOKIE_MAX_AGE).decode()
    except (SignatureExpired, BadSignature):
        return None
