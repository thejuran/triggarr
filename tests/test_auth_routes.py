"""TDD tests for _safe_next_url open redirect prevention and _settings_to_dict auth extension.

Tests cover:
- _safe_next_url: rejects absolute URLs, protocol-relative, backslash, non-slash prefix
- _settings_to_dict: includes auth section with SecretStr values extracted to plain strings
"""

from __future__ import annotations

from pydantic import SecretStr

from triggarr.models.config import AuthConfig, GeneralConfig, InstanceConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.routes import _safe_next_url, _settings_to_dict

# ---------------------------------------------------------------------------
# _safe_next_url tests
# ---------------------------------------------------------------------------


def test_safe_next_url_none_returns_root():
    """_safe_next_url(None) returns '/'."""
    assert _safe_next_url(None) == "/"


def test_safe_next_url_empty_returns_root():
    """_safe_next_url('') returns '/'."""
    assert _safe_next_url("") == "/"


def test_safe_next_url_valid_relative():
    """_safe_next_url('/settings') returns '/settings'."""
    assert _safe_next_url("/settings") == "/settings"


def test_safe_next_url_valid_relative_with_query():
    """_safe_next_url('/history?page=2') returns '/history?page=2'."""
    assert _safe_next_url("/history?page=2") == "/history?page=2"


def test_safe_next_url_rejects_http():
    """_safe_next_url('http://evil.com') returns '/'."""
    assert _safe_next_url("http://evil.com") == "/"


def test_safe_next_url_rejects_https():
    """_safe_next_url('https://evil.com') returns '/'."""
    assert _safe_next_url("https://evil.com") == "/"


def test_safe_next_url_rejects_protocol_relative():
    """_safe_next_url('//evil.com') returns '/'."""
    assert _safe_next_url("//evil.com") == "/"


def test_safe_next_url_rejects_backslash():
    r"""_safe_next_url('/foo\\bar') returns '/'."""
    assert _safe_next_url("/foo\\bar") == "/"


def test_safe_next_url_rejects_no_slash_prefix():
    """_safe_next_url('settings') returns '/'."""
    assert _safe_next_url("settings") == "/"


# ---------------------------------------------------------------------------
# _settings_to_dict auth extension tests
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> SettingsModel:
    """Build a Settings object with sensible defaults for testing.

    Uses model_construct to bypass TOML file source and validators.
    """
    defaults = {
        "general": GeneralConfig(),
        "auth": AuthConfig(),
        "radarr": {},
        "sonarr": {},
        "lidarr": {},
    }
    defaults.update(overrides)
    return SettingsModel.model_construct(**defaults)


def test_settings_to_dict_includes_auth_section():
    """_settings_to_dict includes auth section with plain string values from SecretStr."""
    settings = _make_settings(
        auth=AuthConfig(
            method="Forms",
            username="admin",
            password_hash=SecretStr("$2b$12$hashvalue"),
            api_key=SecretStr("abc123"),
            session_secret=SecretStr("secret456"),
        )
    )
    result = _settings_to_dict(settings)
    assert "auth" in result
    auth = result["auth"]
    assert auth["method"] == "Forms"
    assert auth["username"] == "admin"
    assert auth["password_hash"] == "$2b$12$hashvalue"
    assert auth["api_key"] == "abc123"
    assert auth["session_secret"] == "secret456"
    # Ensure plain strings, not SecretStr objects
    assert isinstance(auth["password_hash"], str)
    assert isinstance(auth["api_key"], str)
    assert isinstance(auth["session_secret"], str)


def test_settings_to_dict_auth_default_unconfigured():
    """Default AuthConfig produces auth section with empty string secret values."""
    settings = _make_settings()
    result = _settings_to_dict(settings)
    assert "auth" in result
    auth = result["auth"]
    assert auth["method"] == "Forms"
    assert auth["username"] == ""
    assert auth["password_hash"] == ""
    assert auth["api_key"] == ""
    assert auth["session_secret"] == ""


def test_settings_to_dict_preserves_existing_behavior():
    """_settings_to_dict still correctly serializes radarr instances with plain-string api_key."""
    settings = _make_settings(
        radarr={
            "4K Radarr": InstanceConfig(
                url="http://localhost:7878",
                api_key=SecretStr("radarr-key-123"),
                enabled=True,
            )
        }
    )
    result = _settings_to_dict(settings)
    assert "radarr" in result
    assert "4K Radarr" in result["radarr"]
    inst = result["radarr"]["4K Radarr"]
    assert inst["api_key"] == "radarr-key-123"
    assert isinstance(inst["api_key"], str)
