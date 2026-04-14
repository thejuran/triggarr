"""Tests for AuthConfig model, Settings integration, and auth secret collection."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from triggarr.models.config import AuthConfig, Settings
from triggarr.startup import collect_secrets

# ---------------------------------------------------------------------------
# AuthConfig defaults
# ---------------------------------------------------------------------------


def test_auth_config_default_method() -> None:
    """AuthConfig defaults to Forms method."""
    assert AuthConfig().method == "Forms"


def test_auth_config_default_needs_setup() -> None:
    """AuthConfig with empty username signals needs-setup state."""
    assert AuthConfig().needs_setup is True


def test_auth_config_configured_not_needs_setup() -> None:
    """AuthConfig with username set is not in needs-setup state."""
    cfg = AuthConfig(username="admin")
    assert cfg.needs_setup is False


def test_auth_config_disabled() -> None:
    """AuthConfig with method Disabled reports is_disabled True."""
    cfg = AuthConfig(method="Disabled")
    assert cfg.is_disabled is True


def test_auth_config_forms_not_disabled() -> None:
    """AuthConfig with default Forms method is not disabled."""
    assert AuthConfig().is_disabled is False


# ---------------------------------------------------------------------------
# Auth method validation
# ---------------------------------------------------------------------------


def test_auth_config_accepts_all_methods() -> None:
    """AuthConfig accepts all four valid auth methods."""
    for method in ("Forms", "Basic", "External", "Disabled"):
        cfg = AuthConfig(method=method)
        assert cfg.method == method


def test_auth_config_rejects_invalid_method() -> None:
    """AuthConfig rejects an invalid auth method."""
    with pytest.raises(ValidationError, match="method"):
        AuthConfig(method="InvalidMethod")


# ---------------------------------------------------------------------------
# SecretStr masking
# ---------------------------------------------------------------------------


def test_auth_config_secretstr_masking() -> None:
    """SecretStr fields do not leak values in str/repr/json."""
    secret = "super-secret-test-value-12345"
    cfg = AuthConfig(
        password_hash=secret,
        api_key=secret,
        session_secret=secret,
    )
    assert secret not in str(cfg)
    assert secret not in repr(cfg)
    assert secret not in cfg.model_dump_json()


# ---------------------------------------------------------------------------
# Settings integration
# ---------------------------------------------------------------------------


def test_settings_has_auth_field() -> None:
    """Settings includes an auth field with AuthConfig defaults."""
    settings = Settings()
    assert hasattr(settings, "auth")
    assert isinstance(settings.auth, AuthConfig)
    assert settings.auth.needs_setup is True


# ---------------------------------------------------------------------------
# collect_secrets extension (D-07)
# ---------------------------------------------------------------------------


def test_collect_secrets_includes_auth_secrets() -> None:
    """collect_secrets gathers auth password_hash, api_key, and session_secret."""
    settings = Settings()
    # Override auth with known secret values
    settings.auth = AuthConfig(
        password_hash="hash123",
        api_key="apikey456",
        session_secret="secret789",
    )
    secrets = collect_secrets(settings)
    assert "hash123" in secrets
    assert "apikey456" in secrets
    assert "secret789" in secrets


def test_collect_secrets_skips_empty_auth_secrets() -> None:
    """collect_secrets does not include empty auth secret values."""
    settings = Settings()
    # Default AuthConfig has all empty secrets
    secrets = collect_secrets(settings)
    # No auth secrets should be present (all empty)
    assert len([s for s in secrets if s in ("",)]) == 0
