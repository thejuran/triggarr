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
    """
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plaintext: The password to verify.
        hashed: The stored bcrypt hash.

    Returns:
        True if the password matches the hash.
    """
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())


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
    signer = TimestampSigner(secret)
    return signer.sign(username).decode()


def validate_session(cookie_value: str, secret: str) -> str | None:
    """Validate a signed session cookie and extract the username.

    Args:
        cookie_value: The raw cookie value from the request.
        secret: The session secret from config.

    Returns:
        The username if valid and not expired, None otherwise.
    """
    signer = TimestampSigner(secret)
    try:
        return signer.unsign(cookie_value, max_age=COOKIE_MAX_AGE).decode()
    except (SignatureExpired, BadSignature):
        return None
