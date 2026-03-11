"""Tests for config loading, default generation, validation, and SecretStr security."""

from __future__ import annotations

from pathlib import Path

import pytest

from triggarr.config import ensure_config, generate_default_config, load_settings
from triggarr.models.config import ArrConfig, GeneralConfig, InstanceConfig, Settings

VALID_TOML = """\
[general]
log_level = "debug"

[radarr."Default"]
url = "http://radarr:7878"
api_key = "radarr-secret-key-123"
enabled = true

[sonarr."Default"]
url = "http://sonarr:8989"
api_key = "sonarr-secret-key-456"
enabled = true
"""

RADARR_ONLY_TOML = """\
[general]
log_level = "info"

[radarr."Default"]
url = "http://radarr:7878"
api_key = "radarr-key"
enabled = true
"""

NO_APPS_TOML = """\
[general]
log_level = "info"
"""


def test_settings_loads_from_toml(tmp_path: Path) -> None:
    """Valid TOML config loads all sections correctly."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)

    settings = load_settings(config_file)

    assert settings.general.log_level == "debug"
    assert "Default" in settings.radarr
    assert settings.radarr["Default"].url == "http://radarr:7878"
    assert settings.radarr["Default"].api_key.get_secret_value() == "radarr-secret-key-123"
    assert settings.radarr["Default"].enabled is True
    assert "Default" in settings.sonarr
    assert settings.sonarr["Default"].url == "http://sonarr:8989"
    assert settings.sonarr["Default"].api_key.get_secret_value() == "sonarr-secret-key-456"
    assert settings.sonarr["Default"].enabled is True


def test_settings_allows_no_enabled_apps(tmp_path: Path) -> None:
    """Config with no enabled apps loads successfully (first-run scenario)."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(NO_APPS_TOML)

    settings = load_settings(config_file)

    assert settings.radarr == {}
    assert settings.sonarr == {}
    assert settings.has_enabled_app is False


def test_settings_allows_single_app(tmp_path: Path) -> None:
    """Config with only radarr enabled loads successfully."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(RADARR_ONLY_TOML)

    settings = load_settings(config_file)

    assert "Default" in settings.radarr
    assert settings.radarr["Default"].enabled is True
    assert settings.radarr["Default"].url == "http://radarr:7878"
    # sonarr should be empty dict (no instances configured)
    assert settings.sonarr == {}


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


def test_arr_config_rejects_both_counts_zero_when_enabled() -> None:
    """ArrConfig rejects both search counts = 0 when enabled."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one"):
        ArrConfig(
            url="http://radarr:7878",
            api_key="test-key",
            enabled=True,
            search_missing_count=0,
            search_cutoff_count=0,
        )


def test_arr_config_allows_both_counts_zero_when_disabled() -> None:
    """ArrConfig allows both counts = 0 when disabled (no validation error)."""
    config = ArrConfig(
        url="http://radarr:7878",
        api_key="test-key",
        enabled=False,
        search_missing_count=0,
        search_cutoff_count=0,
    )
    assert config.search_missing_count == 0


# ---------------------------------------------------------------------------
# skip_unreleased config field
# ---------------------------------------------------------------------------


def test_skip_unreleased_defaults_true() -> None:
    """GeneralConfig().skip_unreleased defaults to True."""
    assert GeneralConfig().skip_unreleased is True


def test_skip_unreleased_from_toml(tmp_path: Path) -> None:
    """skip_unreleased=false in TOML loads as False."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("""\
[general]
skip_unreleased = false
""")
    settings = load_settings(config_file)
    assert settings.general.skip_unreleased is False


def test_skip_unreleased_missing_defaults_true(tmp_path: Path) -> None:
    """TOML without skip_unreleased defaults to True."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("""\
[general]
log_level = "info"
""")
    settings = load_settings(config_file)
    assert settings.general.skip_unreleased is True


# ---------------------------------------------------------------------------
# Multi-instance model (InstanceConfig + dict-based Settings)
# ---------------------------------------------------------------------------


def test_instance_config_valid_fields() -> None:
    """InstanceConfig with valid fields creates successfully."""
    cfg = InstanceConfig(
        url="http://radarr:7878",
        api_key="test-key",
        enabled=True,
        search_interval=30,
        search_missing_count=5,
        search_cutoff_count=5,
    )
    assert cfg.url == "http://radarr:7878"
    assert cfg.api_key.get_secret_value() == "test-key"
    assert cfg.enabled is True
    assert cfg.search_interval == 30
    assert cfg.search_missing_count == 5
    assert cfg.search_cutoff_count == 5


def test_instance_config_rejects_both_counts_zero_when_enabled() -> None:
    """InstanceConfig rejects both search counts = 0 when enabled."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="At least one"):
        InstanceConfig(
            url="http://radarr:7878",
            api_key="test-key",
            enabled=True,
            search_missing_count=0,
            search_cutoff_count=0,
        )


def test_instance_config_allows_both_counts_zero_when_disabled() -> None:
    """InstanceConfig allows both counts = 0 when disabled."""
    cfg = InstanceConfig(
        url="http://radarr:7878",
        api_key="test-key",
        enabled=False,
        search_missing_count=0,
        search_cutoff_count=0,
    )
    assert cfg.search_missing_count == 0


def test_multi_instance_radarr() -> None:
    """Settings accepts radarr as dict[str, InstanceConfig] with multiple named instances."""
    settings = Settings(
        radarr={
            "4K Radarr": InstanceConfig(url="http://radarr4k:7878", api_key="key1", enabled=True),
            "Default": InstanceConfig(url="http://radarr:7878", api_key="key2", enabled=True),
        },
    )
    assert len(settings.radarr) == 2
    assert "4K Radarr" in settings.radarr
    assert "Default" in settings.radarr
    assert settings.radarr["4K Radarr"].url == "http://radarr4k:7878"


def test_multi_instance_sonarr() -> None:
    """Settings accepts sonarr as dict[str, InstanceConfig] with multiple named instances."""
    settings = Settings(
        sonarr={
            "Anime Sonarr": InstanceConfig(url="http://sonarr-anime:8989", api_key="key1", enabled=True),
            "Default": InstanceConfig(url="http://sonarr:8989", api_key="key2", enabled=True),
        },
    )
    assert len(settings.sonarr) == 2
    assert "Anime Sonarr" in settings.sonarr


def test_settings_empty_dicts() -> None:
    """Settings accepts empty dicts for radarr and sonarr (fresh install scenario)."""
    settings = Settings(radarr={}, sonarr={})
    assert settings.radarr == {}
    assert settings.sonarr == {}


def test_max_instances_radarr() -> None:
    """Settings rejects more than 5 radarr instances."""
    from pydantic import ValidationError

    instances = {
        f"Instance {i}": InstanceConfig(url=f"http://radarr{i}:7878", api_key=f"key{i}", enabled=False)
        for i in range(6)
    }
    with pytest.raises(ValidationError, match="Maximum 5 radarr instances"):
        Settings(radarr=instances)


def test_max_instances_sonarr() -> None:
    """Settings rejects more than 5 sonarr instances."""
    from pydantic import ValidationError

    instances = {
        f"Instance {i}": InstanceConfig(url=f"http://sonarr{i}:8989", api_key=f"key{i}", enabled=False)
        for i in range(6)
    }
    with pytest.raises(ValidationError, match="Maximum 5 sonarr instances"):
        Settings(sonarr=instances)


def test_has_enabled_app_radarr_instance() -> None:
    """has_enabled_app returns True when one instance in radarr dict is enabled with a URL."""
    settings = Settings(
        radarr={
            "Default": InstanceConfig(url="http://radarr:7878", api_key="key", enabled=True),
        },
    )
    assert settings.has_enabled_app is True


def test_has_enabled_app_sonarr_instance() -> None:
    """has_enabled_app returns True when one instance in sonarr dict is enabled with a URL."""
    settings = Settings(
        sonarr={
            "Default": InstanceConfig(url="http://sonarr:8989", api_key="key", enabled=True),
        },
    )
    assert settings.has_enabled_app is True


def test_has_enabled_app_all_disabled() -> None:
    """has_enabled_app returns False when all instances are disabled or have empty URLs."""
    settings = Settings(
        radarr={
            "Default": InstanceConfig(url="http://radarr:7878", api_key="key", enabled=False),
        },
        sonarr={
            "Default": InstanceConfig(url="", api_key="key", enabled=True),
        },
    )
    assert settings.has_enabled_app is False


def test_instance_config_secret_str_hidden() -> None:
    """SecretStr api_key value does not appear in str(), repr(), or model_dump_json() of InstanceConfig."""
    secret = "super-secret-instance-key"
    cfg = InstanceConfig(url="http://localhost:7878", api_key=secret, enabled=True)
    assert secret not in str(cfg)
    assert secret not in repr(cfg)
    assert secret not in cfg.model_dump_json()


def test_arr_config_alias_backward_compat() -> None:
    """ArrConfig alias still works (backward compatibility for transition)."""
    cfg = ArrConfig(url="http://radarr:7878", api_key="key", enabled=True)
    assert isinstance(cfg, InstanceConfig)
    assert cfg.url == "http://radarr:7878"


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
