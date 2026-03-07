"""Tests for config loading, default generation, validation, and SecretStr security."""

from __future__ import annotations

from pathlib import Path

import pytest

from triggarr.config import ensure_config, generate_default_config, load_settings
from triggarr.models.config import ArrConfig

VALID_TOML = """\
[general]
log_level = "debug"

[radarr]
url = "http://radarr:7878"
api_key = "radarr-secret-key-123"
enabled = true

[sonarr]
url = "http://sonarr:8989"
api_key = "sonarr-secret-key-456"
enabled = true
"""

RADARR_ONLY_TOML = """\
[general]
log_level = "info"

[radarr]
url = "http://radarr:7878"
api_key = "radarr-key"
enabled = true
"""

NO_APPS_TOML = """\
[general]
log_level = "info"

[radarr]
url = ""
api_key = ""
enabled = false

[sonarr]
url = ""
api_key = ""
enabled = false
"""


def test_settings_loads_from_toml(tmp_path: Path) -> None:
    """Valid TOML config loads all sections correctly."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)

    settings = load_settings(config_file)

    assert settings.general.log_level == "debug"
    assert settings.radarr.url == "http://radarr:7878"
    assert settings.radarr.api_key.get_secret_value() == "radarr-secret-key-123"
    assert settings.radarr.enabled is True
    assert settings.sonarr.url == "http://sonarr:8989"
    assert settings.sonarr.api_key.get_secret_value() == "sonarr-secret-key-456"
    assert settings.sonarr.enabled is True


def test_settings_allows_no_enabled_apps(tmp_path: Path) -> None:
    """Config with no enabled apps loads successfully (first-run scenario)."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(NO_APPS_TOML)

    settings = load_settings(config_file)

    assert settings.radarr.enabled is False
    assert settings.sonarr.enabled is False
    assert settings.has_enabled_app is False


def test_settings_allows_single_app(tmp_path: Path) -> None:
    """Config with only radarr enabled loads successfully."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(RADARR_ONLY_TOML)

    settings = load_settings(config_file)

    assert settings.radarr.enabled is True
    assert settings.radarr.url == "http://radarr:7878"
    # sonarr should have defaults (disabled)
    assert settings.sonarr.enabled is False


def test_default_config_generation(tmp_path: Path) -> None:
    """generate_default_config creates a file with [radarr] and [sonarr] sections."""
    config_file = tmp_path / "triggarr.toml"

    generate_default_config(config_file)

    assert config_file.exists()
    content = config_file.read_text()
    assert "[radarr]" in content
    assert "[sonarr]" in content


def test_api_key_never_in_str() -> None:
    """API key value must not appear in str(), repr(), or model_dump_json()."""
    secret = "super-secret-api-key-value"
    config = ArrConfig(url="http://localhost:7878", api_key=secret, enabled=True)

    assert secret not in str(config)
    assert secret not in repr(config)
    assert secret not in config.model_dump_json()


def test_ensure_config_exits_on_missing(tmp_path: Path) -> None:
    """ensure_config generates default config and exits when file is missing."""
    config_file = tmp_path / "triggarr.toml"

    with pytest.raises(SystemExit) as exc_info:
        ensure_config(config_file)

    assert exc_info.value.code == 1
    # Default config should have been generated
    assert config_file.exists()
    content = config_file.read_text()
    assert "[radarr]" in content
    assert "[sonarr]" in content
