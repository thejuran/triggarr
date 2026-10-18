"""Tests for config loading, default generation, validation, and SecretStr security."""

from __future__ import annotations

import io
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w
from loguru import logger
from pydantic import SecretStr, ValidationError

from triggarr.config import (
    _atomic_toml_write,
    _is_v22_format,
    _migrate_v22_to_v23,
    detect_and_migrate_v22,
    ensure_config,
    generate_default_config,
    load_settings,
)
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings

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
    config = InstanceConfig(url="http://localhost:7878", api_key=secret, enabled=True)

    assert secret not in str(config)
    assert secret not in repr(config)
    assert secret not in config.model_dump_json()


def test_instance_config_rejects_both_counts_zero_when_enabled_legacy() -> None:
    """InstanceConfig rejects both search counts = 0 when enabled."""

    with pytest.raises(ValidationError, match="At least one"):
        InstanceConfig(
            url="http://radarr:7878",
            api_key="test-key",
            enabled=True,
            search_missing_count=0,
            search_cutoff_count=0,
        )


def test_instance_config_allows_both_counts_zero_when_disabled_legacy() -> None:
    """InstanceConfig allows both counts = 0 when disabled (no validation error)."""
    config = InstanceConfig(
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


def test_general_config_default_max_consecutive_failures() -> None:
    """SAFETY-03: GeneralConfig().max_consecutive_failures defaults to 5, bounded 1..100.

    The bound is enforced via pydantic Field(ge=1, le=100) (or an equivalent
    field validator) so out-of-bounds values raise pydantic.ValidationError at
    model construction time. Defense in depth: the route handler also clamps
    via safe_int(..., 5, 1, 100) before the form value reaches the model.
    """
    assert GeneralConfig().max_consecutive_failures == 5

    with pytest.raises(ValidationError):
        GeneralConfig(max_consecutive_failures=0)

    with pytest.raises(ValidationError):
        GeneralConfig(max_consecutive_failures=101)


def test_general_config_default_shutdown_drain_timeout() -> None:
    """DEBT-06/D-01: GeneralConfig().shutdown_drain_timeout defaults to 60.0, bounded ge=1.0.

    The bound is enforced via Field(ge=1.0, allow_inf_nan=False) so out-of-bounds and
    non-finite values raise pydantic.ValidationError at model construction time.
    allow_inf_nan=False is load-bearing: ge=1.0 alone ACCEPTS +inf (pydantic v2 default
    allow_inf_nan=True), which would allow asyncio.timeout(inf) to never bound the drain.
    """
    assert GeneralConfig().shutdown_drain_timeout == 60.0

    # Below ge=1.0 → rejected
    with pytest.raises(ValidationError):
        GeneralConfig(shutdown_drain_timeout=0.0)

    # Valid fractional value accepted and preserved
    assert GeneralConfig(shutdown_drain_timeout=120.5).shutdown_drain_timeout == 120.5

    # Non-finite values rejected (allow_inf_nan=False is the load-bearing guard)
    with pytest.raises(ValidationError):
        GeneralConfig(shutdown_drain_timeout=float("inf"))

    with pytest.raises(ValidationError):
        GeneralConfig(shutdown_drain_timeout=float("nan"))


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


# ---------------------------------------------------------------------------
# SEC-02: InstanceConfig.url rejects apikey= query parameter (D-06/D-07/D-08)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://radarr:7878?apikey=secret",
        "http://radarr:7878/?apikey=secret",
        "http://radarr:7878?APIKEY=secret",
        "http://radarr:7878?apiKey=secret",
        "http://radarr:7878?other=ok&apikey=secret",
        "http://radarr:7878?apikey=",
        "http://radarr:7878?apikey%3Dsecret",
        "http://radarr:7878?apikey%3D%73ecret",
    ],
)
def test_instance_url_rejects_apikey(url: str) -> None:
    """SEC-02: InstanceConfig rejects URLs whose query contains apikey= (any case, including
    empty value and URL-encoded variants). The validator raises ValidationError carrying the
    D-08 message before any TOML write happens (D-06/D-07/D-08 + codex M2 finding 2026-05-26)."""
    with pytest.raises(ValidationError, match="apikey="):
        InstanceConfig(url=url, api_key=SecretStr("k"), enabled=True)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://radarr:7878",
        "http://radarr:7878/",
        "http://radarr:7878/sonarr/",
        "http://radarr:7878?base=/sonarr",
        "http://radarr:7878?token=foo",
    ],
)
def test_instance_url_accepts_without_apikey(url: str) -> None:
    """SEC-02 D-07 narrow rule: legitimate URLs without an apikey= query parameter
    continue to construct successfully (empty default, subpath, non-apikey queries)."""
    cfg = InstanceConfig(url=url, api_key=SecretStr("k"), enabled=True)
    assert cfg.url == url


# ---------------------------------------------------------------------------
# D-01/D-02/D-03: InstanceConfig config-load SSRF validation (relaxed variant)
# ---------------------------------------------------------------------------


def test_instance_config_loopback_url_valid() -> None:
    """D-02: InstanceConfig accepts loopback URL (same-host *arr is a legitimate homelab pattern)."""
    cfg = InstanceConfig(url="http://127.0.0.1:7878", api_key=SecretStr("k"), enabled=True)
    assert cfg.url == "http://127.0.0.1:7878"


def test_instance_config_localhost_url_valid() -> None:
    """D-02: InstanceConfig accepts localhost hostname (falls through DNS branch)."""
    cfg = InstanceConfig(url="http://localhost:7878", api_key=SecretStr("k"), enabled=True)
    assert cfg.url == "http://localhost:7878"


def test_instance_config_metadata_url_raises() -> None:
    """D-01: InstanceConfig rejects cloud-metadata URL at config-load time."""
    with pytest.raises(ValidationError):
        InstanceConfig(url="http://169.254.169.254/latest/meta-data", api_key=SecretStr("k"), enabled=True)


def test_instance_config_link_local_url_raises() -> None:
    """D-01: InstanceConfig rejects link-local IP at config-load time."""
    with pytest.raises(ValidationError):
        InstanceConfig(url="http://169.254.42.42", api_key=SecretStr("k"), enabled=True)


def test_instance_config_disabled_instance_metadata_url_still_raises() -> None:
    """D-01/D-02: Config-load URL validation runs independent of `enabled`.

    A disabled instance with a genuinely-unsafe URL is still rejected at startup —
    the validate_url_ssrf field_validator fires on the url field regardless of enabled.
    """
    with pytest.raises(ValidationError):
        InstanceConfig(url="http://169.254.169.254/latest/meta-data", api_key=SecretStr("k"), enabled=False)


def test_instance_config_metadata_url_with_apikey_rejects_apikey_first() -> None:
    """D-01/D-02/D-03: reject_apikey_in_url fires before/independently of validate_url_ssrf.

    When the URL is both a metadata host AND contains an apikey= parameter,
    the apikey= rejection surfaces — proving validator ordering is stable.
    """
    with pytest.raises(ValidationError, match="apikey="):
        InstanceConfig(url="http://169.254.169.254?apikey=secret", api_key=SecretStr("k"), enabled=True)


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

    instances = {
        f"Instance {i}": InstanceConfig(url=f"http://radarr{i}:7878", api_key=f"key{i}", enabled=False)
        for i in range(6)
    }
    with pytest.raises(ValidationError, match="Maximum 5 radarr instances"):
        Settings(radarr=instances)


def test_max_instances_sonarr() -> None:
    """Settings rejects more than 5 sonarr instances."""

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


# ---------------------------------------------------------------------------
# Tag fields on InstanceConfig (Phase 36)
# ---------------------------------------------------------------------------


def test_instance_config_missing_tag_default() -> None:
    """InstanceConfig().missing_tag defaults to empty string."""
    cfg = InstanceConfig()
    assert cfg.missing_tag == ""


def test_instance_config_cutoff_tag_default() -> None:
    """InstanceConfig().cutoff_tag defaults to empty string."""
    cfg = InstanceConfig()
    assert cfg.cutoff_tag == ""


def test_instance_config_tag_fields_from_toml(tmp_path: Path) -> None:
    """Tag fields load correctly from TOML config."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("""\
[radarr."Default"]
url = "http://radarr:7878"
api_key = "key"
enabled = true
missing_tag = "triggarr"
cutoff_tag = "upgrade"
""")
    settings = load_settings(config_file)
    assert settings.radarr["Default"].missing_tag == "triggarr"
    assert settings.radarr["Default"].cutoff_tag == "upgrade"


def test_instance_config_toml_without_tag_fields(tmp_path: Path) -> None:
    """TOML without tag fields parses cleanly (backward compat)."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)
    settings = load_settings(config_file)
    assert settings.radarr["Default"].missing_tag == ""
    assert settings.radarr["Default"].cutoff_tag == ""


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
    # New default config should have web UI comment and empty instance sections
    assert "web UI" in content or "settings" in content.lower()


def test_ensure_config_exits_cleanly_on_invalid_url(tmp_path: Path) -> None:
    """ensure_config translates a ValidationError into sys.exit(1), not a traceback.

    A config that parses as TOML but fails a model rule (here: a placeholder
    instance url of ``http://`` with no hostname, which the config-load SSRF
    validator rejects) must produce a clean operator-facing exit rather than an
    uncaught pydantic.ValidationError propagating out of asyncio.run() at startup.
    Regression guard for the IMP-001 deep-review finding (phase 71).
    """
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(
        '[general]\nlog_level = "info"\n\n'
        '[radarr.main]\nurl = "http://"\napi_key = "x"\nenabled = false\n'
    )

    with pytest.raises(SystemExit) as exc_info:
        ensure_config(config_file)

    assert exc_info.value.code == 1


def test_ensure_config_exits_cleanly_on_blocked_metadata_url(tmp_path: Path) -> None:
    """A cloud-metadata url in triggarr.toml exits cleanly via sys.exit(1).

    Complements the placeholder-url case: a genuinely-unsafe url (link-local /
    cloud-metadata) rejected by the config-load SSRF validator must also surface
    as a friendly exit, not a bare traceback. Regression guard for IMP-001.
    """
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(
        '[general]\nlog_level = "info"\n\n'
        '[radarr.main]\nurl = "http://169.254.169.254/latest/meta-data"\n'
        'api_key = "x"\nenabled = true\n'
    )

    with pytest.raises(SystemExit) as exc_info:
        ensure_config(config_file)

    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# v2.2 detection and migration
# ---------------------------------------------------------------------------

V22_RADARR_SONARR_TOML = """\
[general]
log_level = "info"

[radarr]
url = "http://radarr:7878"
api_key = "radarr-key-123"
enabled = true
search_interval = 30
search_missing_count = 5
search_cutoff_count = 5

[sonarr]
url = "http://sonarr:8989"
api_key = "sonarr-key-456"
enabled = true
search_interval = 30
search_missing_count = 5
search_cutoff_count = 5
"""

V22_RADARR_ONLY_TOML = """\
[general]
log_level = "info"

[radarr]
url = "http://radarr:7878"
api_key = "radarr-key-123"
enabled = true
"""

V22_DISABLED_TOML = """\
[general]
log_level = "info"

[radarr]
url = "http://radarr:7878"
api_key = "radarr-key-disabled"
enabled = false

[sonarr]
url = ""
api_key = ""
enabled = false
"""


def test_is_v22_format_radarr_flat() -> None:
    """_is_v22_format returns True for flat radarr section with url/api_key/enabled keys."""
    data = {"radarr": {"url": "http://radarr:7878", "api_key": "key", "enabled": True}}
    assert _is_v22_format(data) is True


def test_is_v22_format_sonarr_flat() -> None:
    """_is_v22_format returns True for flat sonarr section with url/api_key/enabled keys."""
    data = {"sonarr": {"url": "http://sonarr:8989", "api_key": "key", "enabled": True}}
    assert _is_v22_format(data) is True


def test_is_v22_format_false_for_v23() -> None:
    """_is_v22_format returns False for v2.3 format (nested instance names)."""
    data = {
        "radarr": {"Default": {"url": "http://radarr:7878", "api_key": "key", "enabled": True}},
        "sonarr": {"Default": {"url": "http://sonarr:8989", "api_key": "key", "enabled": True}},
    }
    assert _is_v22_format(data) is False


def test_is_v22_format_false_for_empty() -> None:
    """_is_v22_format returns False for empty radarr/sonarr sections."""
    data = {"radarr": {}, "sonarr": {}}
    assert _is_v22_format(data) is False


def test_migrate_v22_to_v23_wraps_radarr() -> None:
    """_migrate_v22_to_v23 wraps flat radarr section into {'Default': {...}}."""
    data = {
        "general": {"log_level": "info"},
        "radarr": {"url": "http://radarr:7878", "api_key": "key", "enabled": True},
        "sonarr": {"url": "http://sonarr:8989", "api_key": "key2", "enabled": False},
    }
    result = _migrate_v22_to_v23(data)
    assert "Default" in result["radarr"]
    assert result["radarr"]["Default"]["url"] == "http://radarr:7878"


def test_migrate_v22_to_v23_wraps_sonarr() -> None:
    """_migrate_v22_to_v23 wraps flat sonarr section into {'Default': {...}}."""
    data = {
        "general": {"log_level": "info"},
        "radarr": {"url": "http://radarr:7878", "api_key": "key", "enabled": True},
        "sonarr": {"url": "http://sonarr:8989", "api_key": "key2", "enabled": False},
    }
    result = _migrate_v22_to_v23(data)
    assert "Default" in result["sonarr"]
    assert result["sonarr"]["Default"]["url"] == "http://sonarr:8989"


def test_migrate_v22_to_v23_preserves_general() -> None:
    """_migrate_v22_to_v23 preserves general section unchanged."""
    data = {
        "general": {"log_level": "debug", "skip_unreleased": False},
        "radarr": {"url": "http://radarr:7878", "api_key": "key", "enabled": True},
    }
    result = _migrate_v22_to_v23(data)
    assert result["general"]["log_level"] == "debug"
    assert result["general"]["skip_unreleased"] is False


def test_migrate_v22_to_v23_handles_missing_sonarr() -> None:
    """_migrate_v22_to_v23 handles radarr present but sonarr missing."""
    data = {
        "general": {"log_level": "info"},
        "radarr": {"url": "http://radarr:7878", "api_key": "key", "enabled": True},
    }
    result = _migrate_v22_to_v23(data)
    assert "Default" in result["radarr"]
    assert result.get("sonarr", {}) == {}


def test_detect_and_migrate_v22_creates_backup(tmp_path: Path) -> None:
    """detect_and_migrate_v22 creates backup file triggarr.toml.bak."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    detect_and_migrate_v22(config_file)

    backup = config_file.with_suffix(".toml.bak")
    assert backup.exists()
    assert backup.read_text() == V22_RADARR_SONARR_TOML


def test_detect_and_migrate_v22_writes_valid_settings(tmp_path: Path) -> None:
    """detect_and_migrate_v22 writes migrated config that loads as valid Settings."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    detect_and_migrate_v22(config_file)

    settings = load_settings(config_file)
    assert "Default" in settings.radarr
    assert settings.radarr["Default"].url == "http://radarr:7878"
    assert "Default" in settings.sonarr
    assert settings.sonarr["Default"].url == "http://sonarr:8989"


def test_detect_and_migrate_v22_returns_true(tmp_path: Path) -> None:
    """detect_and_migrate_v22 returns True when migration performed."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    result = detect_and_migrate_v22(config_file)

    assert result is True


def test_detect_and_migrate_v22_returns_false_for_v23(tmp_path: Path) -> None:
    """detect_and_migrate_v22 returns False for already-migrated config (no backup created)."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)

    result = detect_and_migrate_v22(config_file)

    assert result is False
    backup = config_file.with_suffix(".toml.bak")
    assert not backup.exists()


def test_detect_and_migrate_v22_creates_marker(tmp_path: Path) -> None:
    """detect_and_migrate_v22 creates .migrated marker file in config dir."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    detect_and_migrate_v22(config_file)

    marker = config_file.parent / ".migrated"
    assert marker.exists()


def test_detect_and_migrate_v22_preserves_disabled(tmp_path: Path) -> None:
    """detect_and_migrate_v22 preserves disabled app as disabled 'Default' instance."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_DISABLED_TOML)

    detect_and_migrate_v22(config_file)

    settings = load_settings(config_file)
    assert "Default" in settings.radarr
    assert settings.radarr["Default"].enabled is False
    assert settings.radarr["Default"].url == "http://radarr:7878"
    assert settings.radarr["Default"].api_key.get_secret_value() == "radarr-key-disabled"


def test_detect_and_migrate_v22_preserves_api_key_plaintext(tmp_path: Path) -> None:
    """detect_and_migrate_v22 preserves API key values (not SecretStr-masked) in written TOML."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    detect_and_migrate_v22(config_file)

    content = config_file.read_text()
    assert "radarr-key-123" in content
    assert "sonarr-key-456" in content
    # Must NOT contain SecretStr masked representation
    assert "**********" not in content


def test_generate_default_config_web_ui_comment(tmp_path: Path) -> None:
    """generate_default_config produces new template with web UI comment, empty radarr/sonarr sections."""
    config_file = tmp_path / "triggarr.toml"

    generate_default_config(config_file)

    content = config_file.read_text()
    assert "web UI" in content or "settings" in content.lower()
    assert "[radarr]" in content
    assert "[sonarr]" in content
    # Should NOT have url/api_key/enabled under radarr/sonarr (empty sections)
    # Parse and verify
    with open(config_file, "rb") as f:
        data = tomllib.load(f)
    assert data.get("radarr", {}) == {}
    assert data.get("sonarr", {}) == {}


def test_ensure_config_calls_migration(tmp_path: Path) -> None:
    """ensure_config calls detect_and_migrate_v22 before load_settings for existing configs."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    settings = ensure_config(config_file)

    # Should have migrated and loaded successfully
    assert "Default" in settings.radarr
    assert settings.radarr["Default"].url == "http://radarr:7878"
    # Backup should exist
    backup = config_file.with_suffix(".toml.bak")
    assert backup.exists()


def test_toml_round_trip(tmp_path: Path) -> None:
    """TOML round-trip: load migrated config, serialize back, reload -- same values."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    detect_and_migrate_v22(config_file)

    # Load migrated config
    with open(config_file, "rb") as f:
        data1 = tomllib.load(f)

    # Serialize back and reload
    round_trip_file = tmp_path / "round_trip.toml"
    with open(round_trip_file, "wb") as f:
        tomli_w.dump(data1, f)

    with open(round_trip_file, "rb") as f:
        data2 = tomllib.load(f)

    # Values should be identical
    assert data1["radarr"]["Default"]["url"] == data2["radarr"]["Default"]["url"]
    assert data1["radarr"]["Default"]["api_key"] == data2["radarr"]["Default"]["api_key"]
    assert data1["sonarr"]["Default"]["url"] == data2["sonarr"]["Default"]["url"]
    assert data1["sonarr"]["Default"]["api_key"] == data2["sonarr"]["Default"]["api_key"]


# ---------------------------------------------------------------------------
# BUG-06: _atomic_toml_write temp file cleanup on failure
# ---------------------------------------------------------------------------


def test_atomic_toml_write_succeeds(tmp_path: Path) -> None:
    """_atomic_toml_write writes valid TOML data to disk (no regression)."""
    config_file = tmp_path / "test.toml"
    data = {"general": {"log_level": "info"}, "radarr": {"Default": {"url": "http://radarr:7878"}}}
    _atomic_toml_write(config_file, data)

    assert config_file.exists()
    with open(config_file, "rb") as f:
        written = tomllib.load(f)
    assert written["general"]["log_level"] == "info"
    assert written["radarr"]["Default"]["url"] == "http://radarr:7878"


def test_atomic_toml_write_cleans_temp_on_failure(tmp_path: Path) -> None:
    """_atomic_toml_write removes temp file when tomli_w.dump raises (BUG-06)."""
    config_file = tmp_path / "test.toml"

    with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("bad data")), \
         pytest.raises(TypeError):
        _atomic_toml_write(config_file, {"key": "value"})

    # No temp files should remain in the directory
    remaining = list(tmp_path.glob("*.tmp"))
    assert remaining == [], f"Temp files should be cleaned up, found: {remaining}"


# ---------------------------------------------------------------------------
# SAFETY-04: _atomic_toml_write OSError observability
# ---------------------------------------------------------------------------


def test_atomic_toml_write_logs_cleanup_oserror(tmp_path: Path) -> None:
    """Non-FileNotFoundError OSError during temp cleanup is logged via loguru (SAFETY-04)."""
    config_file = tmp_path / "test.toml"

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("bad data")), \
             patch("triggarr.config.os.unlink", side_effect=PermissionError("denied")), \
             pytest.raises(TypeError):
            _atomic_toml_write(config_file, {"k": "v"})

        text = sink.getvalue()
        assert "Failed to clean up temp file" in text
        assert "denied" in text
    finally:
        logger.remove(handler_id)


def test_atomic_toml_write_suppresses_filenotfound_silently(tmp_path: Path) -> None:
    """FileNotFoundError during temp cleanup remains silently suppressed (SAFETY-04)."""
    config_file = tmp_path / "test.toml"

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with patch("triggarr.config.tomli_w.dump", side_effect=TypeError("bad data")), \
             patch("triggarr.config.os.unlink", side_effect=FileNotFoundError), \
             pytest.raises(TypeError):
            _atomic_toml_write(config_file, {"k": "v"})

        assert "Failed to clean up" not in sink.getvalue()
    finally:
        logger.remove(handler_id)


def test_atomic_toml_write_logs_os_replace_failure(tmp_path: Path) -> None:
    """OSError raised by os.replace is logged with the config path before re-raise (SAFETY-04)."""
    config_file = tmp_path / "test.toml"

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with patch("triggarr.config.os.replace", side_effect=OSError("EROFS")), \
             pytest.raises(OSError):
            _atomic_toml_write(config_file, {"k": "v"})

        text = sink.getvalue()
        assert "Config write failed" in text
        assert "EROFS" in text
        assert str(config_file) in text
    finally:
        logger.remove(handler_id)


# ---------------------------------------------------------------------------
# Broken TOML config tests (STATE-01)
# ---------------------------------------------------------------------------


def test_toml_syntax_error_raises_decode_error(tmp_path: Path) -> None:
    """Broken TOML syntax (missing closing bracket) raises TOMLDecodeError."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general\nlog_level = "info"')

    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings(config_file)


def test_toml_both_search_counts_zero_raises_validation_error(tmp_path: Path) -> None:
    """TOML with both search counts at 0 when enabled raises ValidationError."""

    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("""\
[radarr."Default"]
url = "http://radarr:7878"
api_key = "key"
enabled = true
search_missing_count = 0
search_cutoff_count = 0
""")

    with pytest.raises(ValidationError):
        load_settings(config_file)


def test_toml_wrong_type_raises_validation_error(tmp_path: Path) -> None:
    """TOML with wrong field type (array instead of string for url) raises ValidationError."""

    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("""\
[radarr."Default"]
url = [1, 2, 3]
api_key = "key"
enabled = true
""")

    with pytest.raises(ValidationError):
        load_settings(config_file)


# ---------------------------------------------------------------------------
# Config migration edge cases (STATE-04)
# ---------------------------------------------------------------------------


def test_migrate_v22_partial_radarr_only() -> None:
    """_migrate_v22_to_v23 with radarr only (no sonarr key) wraps radarr, sonarr stays absent."""
    data = {
        "general": {"log_level": "info"},
        "radarr": {"url": "http://r:7878", "api_key": "k", "enabled": True},
    }
    result = _migrate_v22_to_v23(data)

    assert "Default" in result["radarr"]
    assert result["radarr"]["Default"]["url"] == "http://r:7878"
    assert result["radarr"]["Default"]["api_key"] == "k"
    assert result["radarr"]["Default"]["enabled"] is True
    # sonarr was never in data, so it stays absent
    assert result.get("sonarr") is None


def test_migrate_v22_unknown_extra_fields_preserved() -> None:
    """_migrate_v22_to_v23 preserves unknown fields by wrapping, not filtering."""
    data = {
        "general": {"log_level": "info", "unknown_field": 42},
        "radarr": {"url": "http://r:7878", "api_key": "k", "enabled": True, "custom": "val"},
    }
    result = _migrate_v22_to_v23(data)

    assert result["general"]["unknown_field"] == 42
    assert result["radarr"]["Default"]["custom"] == "val"


def test_is_v22_format_missing_general() -> None:
    """_is_v22_format returns True for flat radarr even without [general] section."""
    data = {"radarr": {"url": "http://r:7878"}}
    assert _is_v22_format(data) is True


def test_migrate_v22_mixed_nested_and_flat_only_detects_flat() -> None:
    """_is_v22_format returns True when sonarr has flat keys even if radarr is v2.3 nested."""
    data = {
        "radarr": {"Default": {"url": "http://r:7878", "api_key": "k"}},
        "sonarr": {"url": "http://s:8989"},
    }
    assert _is_v22_format(data) is True


# ---------------------------------------------------------------------------
# TEST-02: ensure_config friendly TOML-corruption handling
# ---------------------------------------------------------------------------


def test_ensure_config_logs_friendly_error_on_toml_syntax_error(tmp_path: Path) -> None:
    """Corrupt TOML syntax produces friendly loguru.error mentioning the config path; sys.exit(1)."""
    config_path = tmp_path / "triggarr.toml"
    config_path.write_text('[general\nlog_level = "info"')

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with pytest.raises(SystemExit) as exc_info:
            ensure_config(config_path)
    finally:
        logger.remove(handler_id)

    assert exc_info.value.code == 1
    text = sink.getvalue()
    assert str(config_path) in text
    assert "Failed to parse config file" in text


def test_ensure_config_logs_friendly_error_on_invalid_utf8(tmp_path: Path) -> None:
    """Invalid UTF-8 bytes in config produce friendly loguru.error and sys.exit(1)."""
    config_path = tmp_path / "triggarr.toml"
    config_path.write_bytes(b"\xff\xfe\x00garbage")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with pytest.raises(SystemExit) as exc_info:
            ensure_config(config_path)
    finally:
        logger.remove(handler_id)

    assert exc_info.value.code == 1
    text = sink.getvalue()
    assert str(config_path) in text
    assert "Failed to parse config file" in text


def test_ensure_config_mentions_backup_path_when_backup_exists(tmp_path: Path) -> None:
    """When triggarr.toml.bak exists alongside corrupt config, the log mentions the backup path."""
    config_path = tmp_path / "triggarr.toml"
    backup_path = tmp_path / "triggarr.toml.bak"
    backup_path.write_text('log_level = "info"\n')
    config_path.write_text('[general\nlog_level = "info"')

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with pytest.raises(SystemExit) as exc_info:
            ensure_config(config_path)
    finally:
        logger.remove(handler_id)

    assert exc_info.value.code == 1
    text = sink.getvalue()
    assert str(backup_path) in text
    assert "backup is available" in text


def test_ensure_config_mentions_no_backup_when_absent(tmp_path: Path) -> None:
    """When no .bak exists alongside corrupt config, the log states no automatic backup exists."""
    config_path = tmp_path / "triggarr.toml"
    config_path.write_text('[general\nlog_level = "info"')

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with pytest.raises(SystemExit) as exc_info:
            ensure_config(config_path)
    finally:
        logger.remove(handler_id)

    assert exc_info.value.code == 1
    text = sink.getvalue()
    assert "No automatic backup" in text


# ---------------------------------------------------------------------------
# Stable instance id (ATTR-03)
# ---------------------------------------------------------------------------


def test_instance_id_default_empty() -> None:
    """An InstanceConfig built without an id has the empty "needs backfill" value."""
    assert InstanceConfig().id == ""
    assert InstanceConfig(id="a1b2").id == "a1b2"


@pytest.mark.parametrize("bad", ["bad id!", "x" * 65, "a/b", "ü"])
def test_instance_id_rejects_invalid(bad: str) -> None:
    """id accepts only "" or 1-64 chars of [A-Za-z0-9_-]."""
    with pytest.raises(ValidationError):
        InstanceConfig(id=bad)


def test_instance_id_accepts_max_length_and_strips() -> None:
    """A 64-char id is valid and surrounding whitespace is stripped."""
    assert InstanceConfig(id="a" * 64).id == "a" * 64
    assert InstanceConfig(id="  abc-1_2  ").id == "abc-1_2"


def test_new_instance_id_is_32_hex() -> None:
    """new_instance_id returns 32 lowercase hex chars and never repeats."""
    import re

    from triggarr.config import new_instance_id

    first = new_instance_id()
    second = new_instance_id()
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert re.fullmatch(r"[0-9a-f]{32}", second)
    assert first != second


def test_instance_id_survives_rename(tmp_path: Path) -> None:
    """Renaming an instance's table key keeps its id (D-08)."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(
        '[general]\nlog_level = "info"\n\n'
        '[sonarr.Primary]\nurl = "http://sonarr:8989"\napi_key = "k"\nid = "abc123"\n'
    )
    settings = load_settings(config_file)
    assert settings.sonarr["Primary"].id == "abc123"


def test_settings_to_dict_carries_instance_id() -> None:
    """_settings_to_dict is importable from config and routes and carries id."""
    from triggarr.config import _settings_to_dict
    from triggarr.web.routes import _settings_to_dict as routes_settings_to_dict

    assert routes_settings_to_dict is _settings_to_dict
    settings = Settings(
        radarr={"Default": InstanceConfig(url="http://radarr:7878", api_key=SecretStr("k"), id="abc")},
    )
    result = _settings_to_dict(settings)
    assert result["radarr"]["Default"]["id"] == "abc"
    assert result["radarr"]["Default"]["api_key"] == "k"


# ---------------------------------------------------------------------------
# Comment-preserving startup backfill of instance ids (ATTR-03)
# ---------------------------------------------------------------------------

_HEX32 = r"[0-9a-f]{32}"
_ID_LINE_RE = re.compile(rb'^id = "' + _HEX32.encode() + rb'"\r?\n$')

STANDARD_SHAPE_TOML = b"""\
# Triggarr configuration
# Hand-edited by the operator

[general]
log_level = "info"  # verbose enough

[radarr.main]
url = "http://radarr:7878"
api_key = "radarr-key"
# the main radarr box
enabled = true

[sonarr."Main"]
url = "http://sonarr:8989"
api_key = "sonarr-key"

[sonarr."My Show Box"]  # 4K box
url = "http://sonarr4k:8989"
api_key = "sonarr4k-key"

[lidarr . "Music"]
url = "http://lidarr:8686"
api_key = "lidarr-key"
"""

INLINE_SHAPE_TOML = b"""\
[general]
log_level = "info"

[sonarr]
# the inline-table instance
Main = { url = "http://sonarr:8989", api_key = "sonarr-key" }  # trailing
"""

DOTTED_SHAPE_TOML = b"""\
[general]
log_level = "info"

[sonarr]
# dotted-key instance
Main.url = "http://sonarr:8989"  # u
Main.api_key = "sonarr-key"
"""

THREE_INSTANCES_TOML = b"""\
[general]
log_level = "info"

[sonarr."Main"]
url = "http://sonarr:8989"
api_key = "sonarr-key"

[sonarr."4K"]
url = "http://sonarr4k:8989"
api_key = "sonarr4k-key"

[radarr."Default"]
url = "http://radarr:7878"
api_key = "radarr-key"
"""


def _write(tmp_path: Path, content: bytes) -> Path:
    config_file = tmp_path / "triggarr.toml"
    config_file.write_bytes(content)
    return config_file


def _all_ids(settings: Settings) -> dict[tuple[str, str], str]:
    return {
        (app, name): cfg.id
        for app in ("radarr", "sonarr", "lidarr")
        for name, cfg in getattr(settings, app).items()
    }


def _file_ids(config_file: Path) -> dict[tuple[str, str], str]:
    data = tomllib.loads(config_file.read_text())
    return {
        (app, name): inst.get("id", "")
        for app in ("radarr", "sonarr", "lidarr")
        for name, inst in data.get(app, {}).items()
    }


def _assert_only_ids_changed(original: bytes, new: bytes, ids: dict[tuple[str, str], str]) -> None:
    """tomllib(new) equals tomllib(original) with exactly the given ids set."""
    expected = tomllib.loads(original.decode())
    for (app, name), inst_id in ids.items():
        expected[app][name]["id"] = inst_id
    assert tomllib.loads(new.decode()) == expected


def _capture(level: str) -> tuple[io.StringIO, int]:
    sink = io.StringIO()
    return sink, logger.add(sink, format="{level} {message}", level=level)


def test_ensure_config_backfills_instance_id(tmp_path: Path) -> None:
    """Instances without an id get distinct 32-hex ids, persisted to the file."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    settings = ensure_config(config_file)

    ids = _all_ids(settings)
    assert set(ids) == {("sonarr", "Main"), ("sonarr", "4K"), ("radarr", "Default")}
    assert all(re.fullmatch(_HEX32, v) for v in ids.values())
    assert len(set(ids.values())) == 3
    assert _file_ids(config_file) == ids


def test_backfill_preserves_comments_standard_table(tmp_path: Path) -> None:
    """Standard tables: removing the added id lines yields the original bytes exactly."""
    config_file = _write(tmp_path, STANDARD_SHAPE_TOML)
    settings = ensure_config(config_file)
    new = config_file.read_bytes()

    new_lines = new.splitlines(keepends=True)
    added = [line for line in new_lines if _ID_LINE_RE.match(line)]
    assert len(added) == 4
    stripped = b"".join(line for line in new_lines if not _ID_LINE_RE.match(line))
    assert stripped == STANDARD_SHAPE_TOML

    # Normalization 1: each id line is the last key line of its own table.
    text = new.decode()
    for name, last_key in [
        ('[radarr.main]', "enabled = true"),
        ('[sonarr."Main"]', 'api_key = "sonarr-key"'),
        ('[sonarr."My Show Box"]  # 4K box', 'api_key = "sonarr4k-key"'),
        ('[lidarr . "Music"]', 'api_key = "lidarr-key"'),
    ]:
        block = text.split(name, 1)[1]
        assert re.search(re.escape(last_key) + r'\nid = "' + _HEX32 + '"\n', block.split("[", 1)[0])
    for comment in ("# Triggarr configuration", "# verbose enough", "# the main radarr box", "# 4K box"):
        assert comment in text
    _assert_only_ids_changed(STANDARD_SHAPE_TOML, new, _all_ids(settings))


def test_backfill_preserves_comments_inline_table(tmp_path: Path) -> None:
    """Inline tables are backfilled in place inside the braces; comments survive."""
    config_file = _write(tmp_path, INLINE_SHAPE_TOML)
    settings = ensure_config(config_file)
    new_id = settings.sonarr["Main"].id
    assert re.fullmatch(_HEX32, new_id)

    expected = INLINE_SHAPE_TOML.replace(
        b'api_key = "sonarr-key" }  # trailing',
        b'api_key = "sonarr-key", id = "' + new_id.encode() + b'"}  # trailing',
    )
    assert config_file.read_bytes() == expected
    assert _file_ids(config_file) == {("sonarr", "Main"): new_id}


def test_backfill_preserves_comments_dotted_keys(tmp_path: Path) -> None:
    """Dotted keys gain one Main.id line after the first Main.* line; all else identical."""
    config_file = _write(tmp_path, DOTTED_SHAPE_TOML)
    settings = ensure_config(config_file)
    new_id = settings.sonarr["Main"].id
    assert re.fullmatch(_HEX32, new_id)

    expected = DOTTED_SHAPE_TOML.replace(
        b'Main.url = "http://sonarr:8989"  # u\n',
        b'Main.url = "http://sonarr:8989"  # u\nMain.id = "' + new_id.encode() + b'"\n',
    )
    assert config_file.read_bytes() == expected
    assert _file_ids(config_file) == {("sonarr", "Main"): new_id}


def test_backfill_preserves_crlf(tmp_path: Path) -> None:
    """Every original CRLF line keeps CRLF; the added line may end with LF."""
    original = THREE_INSTANCES_TOML.replace(b"\n", b"\r\n")
    config_file = _write(tmp_path, original)
    settings = ensure_config(config_file)
    new = config_file.read_bytes()

    new_lines = new.splitlines(keepends=True)
    kept = [line for line in new_lines if not _ID_LINE_RE.match(line)]
    assert b"".join(kept) == original
    assert len(new_lines) - len(kept) == 3
    _assert_only_ids_changed(original, new, _all_ids(settings))
    assert load_settings(config_file).sonarr["Main"].id == settings.sonarr["Main"].id


def test_backfill_header_last_line_without_newline(tmp_path: Path) -> None:
    """A final instance header with no trailing newline still yields valid TOML."""
    config_file = _write(tmp_path, b'[general]\nlog_level = "info"\n\n[sonarr.Main]')
    settings = ensure_config(config_file)
    new_id = settings.sonarr["Main"].id
    assert re.fullmatch(_HEX32, new_id)
    assert load_settings(config_file).sonarr["Main"].id == new_id


def test_ensure_config_instance_id_stable_second_load(tmp_path: Path) -> None:
    """A second startup returns the same ids and does not rewrite the file."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    first = _all_ids(ensure_config(config_file))
    before_bytes = config_file.read_bytes()
    before_mtime = config_file.stat().st_mtime_ns

    second = _all_ids(ensure_config(config_file))
    assert second == first
    assert config_file.read_bytes() == before_bytes
    assert config_file.stat().st_mtime_ns == before_mtime


def test_ensure_config_no_rewrite_when_ids_present(tmp_path: Path) -> None:
    """All ids present and valid: file untouched and tomlkit never used."""
    config_file = _write(
        tmp_path,
        b'[general]\nlog_level = "info"\n\n[sonarr.Main]\nurl = "http://sonarr:8989"\nid = "abc"\n\n'
        b'[radarr.Main]\nurl = "http://radarr:7878"\nid = "abc"\n',
    )
    before_bytes = config_file.read_bytes()
    before_mtime = config_file.stat().st_mtime_ns

    with patch("triggarr.config.tomlkit.parse", side_effect=AssertionError("tomlkit used")), \
         patch("triggarr.config._atomic_text_write", side_effect=AssertionError("written")):
        settings = ensure_config(config_file)

    assert settings.sonarr["Main"].id == "abc"
    assert settings.radarr["Main"].id == "abc"  # same id in a different app is not a duplicate
    assert config_file.read_bytes() == before_bytes
    assert config_file.stat().st_mtime_ns == before_mtime


def test_instance_id_duplicate_regenerated(tmp_path: Path) -> None:
    """The later duplicate within an app is replaced in place, with a warning."""
    original = (
        b'[general]\nlog_level = "info"\n\n'
        b'[sonarr.Main]\nurl = "http://sonarr:8989"\nid = "dup"  # keep me\n\n'
        b'[sonarr]\nCopy = { url = "http://sonarr2:8989", id = "dup" }\n'
    )
    config_file = _write(tmp_path, original)
    sink, handler_id = _capture("WARNING")
    try:
        settings = ensure_config(config_file)
    finally:
        logger.remove(handler_id)

    assert settings.sonarr["Main"].id == "dup"
    new_id = settings.sonarr["Copy"].id
    assert re.fullmatch(_HEX32, new_id)
    new = config_file.read_bytes()
    assert b'id = "dup"  # keep me\n' in new
    assert new.count(b"id = ") == 2
    assert new == original.replace(b'id = "dup" }', b'id = "' + new_id.encode() + b'" }')
    warning = sink.getvalue()
    assert "sonarr" in warning
    assert "Main" in warning
    assert "Copy" in warning
    assert "dup" not in warning


def test_backfill_empty_id_replaced_in_place(tmp_path: Path) -> None:
    """id = "" has its value replaced on the same line, not a second id key."""
    original = b'[sonarr.Main]\nurl = "http://sonarr:8989"\nid = ""  # filled later\napi_key = "k"\n'
    config_file = _write(tmp_path, original)
    new_id = ensure_config(config_file).sonarr["Main"].id
    assert re.fullmatch(_HEX32, new_id)
    assert config_file.read_bytes() == original.replace(b'id = ""', b'id = "' + new_id.encode() + b'"')


@pytest.mark.parametrize(
    "content",
    [STANDARD_SHAPE_TOML, INLINE_SHAPE_TOML, DOTTED_SHAPE_TOML, THREE_INSTANCES_TOML],
    ids=["standard", "inline", "dotted", "three"],
)
def test_backfill_only_ids_change(tmp_path: Path, content: bytes) -> None:
    """For every shape, the parsed result differs from the original only by the new ids."""
    config_file = _write(tmp_path, content)
    settings = ensure_config(config_file)
    _assert_only_ids_changed(content, config_file.read_bytes(), _all_ids(settings))


def test_backfill_mismatch_exits_without_write(tmp_path: Path) -> None:
    """If the edited document changes anything besides ids, startup exits and the file is untouched."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    tampered = THREE_INSTANCES_TOML.decode().replace("radarr-key", "changed") + '\n[sonarr."X"]\nid = "zz"\n'
    sink, handler_id = _capture("ERROR")
    try:
        with patch("triggarr.config.tomlkit.dumps", return_value=tampered), \
             pytest.raises(SystemExit) as exc_info:
            ensure_config(config_file)
    finally:
        logger.remove(handler_id)
    assert exc_info.value.code == 1
    assert config_file.read_bytes() == THREE_INSTANCES_TOML
    assert str(config_file) in sink.getvalue()
    assert "changed" not in sink.getvalue()


@pytest.mark.parametrize("target", ["os.replace", "os.fsync", "os.fchmod"])
def test_backfill_fails_before_replace_leaves_original(tmp_path: Path, target: str) -> None:
    """Case (a): a failure before or at os.replace leaves the original, removes the temp, exits 1."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    sink, handler_id = _capture("ERROR")
    try:
        with patch(f"triggarr.config.{target}", side_effect=OSError("EROFS")), \
             pytest.raises(SystemExit) as exc_info:
            ensure_config(config_file)
    finally:
        logger.remove(handler_id)

    assert exc_info.value.code == 1
    assert config_file.read_bytes() == THREE_INSTANCES_TOML
    assert list(tmp_path.glob("*.tmp")) == []
    text = sink.getvalue()
    assert str(config_file) in text
    assert "OSError" in text


def test_backfill_retry_after_pre_replace_failure(tmp_path: Path) -> None:
    """After a case (a) failure, the next startup mints ids and succeeds; a third changes nothing."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    with patch("triggarr.config.os.replace", side_effect=OSError("EROFS")), pytest.raises(SystemExit):
        ensure_config(config_file)

    ids = _all_ids(ensure_config(config_file))
    assert all(re.fullmatch(_HEX32, v) for v in ids.values())
    assert _file_ids(config_file) == ids
    assert config_file.read_text().count("\nid = ") == 3

    before = config_file.read_bytes()
    before_mtime = config_file.stat().st_mtime_ns
    assert _all_ids(ensure_config(config_file)) == ids
    assert config_file.read_bytes() == before
    assert config_file.stat().st_mtime_ns == before_mtime


def test_backfill_temp_file_is_0600_before_replace(tmp_path: Path) -> None:
    """The temp file is already 0600 when it replaces the config; no chmod on the config path."""
    import os

    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    config_file.chmod(0o644)
    real_replace = os.replace
    real_chmod = os.chmod
    recorded: list[int] = []
    chmod_paths: list[str] = []

    def _spy_replace(src, dst):  # noqa: ANN001, ANN202
        recorded.append(os.stat(src).st_mode & 0o777)
        return real_replace(src, dst)

    def _spy_chmod(path, mode, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        chmod_paths.append(str(path))
        return real_chmod(path, mode, *args, **kwargs)

    with patch("triggarr.config.os.replace", side_effect=_spy_replace), \
         patch("triggarr.config.os.chmod", side_effect=_spy_chmod):
        ensure_config(config_file)

    assert recorded == [0o600]
    assert config_file.stat().st_mode & 0o777 == 0o600
    assert str(config_file) not in chmod_paths


def _fail_second_fsync():  # noqa: ANN202
    """Return an os.fsync stand-in whose second call (the directory fsync) fails."""
    import os

    real_fsync = os.fsync
    calls = {"n": 0}

    def _fsync(fd):  # noqa: ANN001, ANN202
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("EIO")
        return real_fsync(fd)

    return _fsync


def test_backfill_post_replace_fsync_failure_continues(tmp_path: Path) -> None:
    """Case (b): only the directory fsync fails, so startup continues on the committed ids."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    sink, handler_id = _capture("WARNING")
    try:
        with patch("triggarr.config.os.fsync", side_effect=_fail_second_fsync()):
            settings = ensure_config(config_file)
    finally:
        logger.remove(handler_id)

    ids = _all_ids(settings)
    assert all(re.fullmatch(_HEX32, v) for v in ids.values())
    assert _file_ids(config_file) == ids
    assert "directory sync failed" in sink.getvalue()


def test_backfill_retry_after_post_replace_failure_keeps_ids(tmp_path: Path) -> None:
    """After case (b), the next startup reads the same ids without re-minting or rewriting."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    with patch("triggarr.config.os.fsync", side_effect=_fail_second_fsync()):
        ids = _all_ids(ensure_config(config_file))

    before = config_file.read_bytes()
    before_mtime = config_file.stat().st_mtime_ns
    assert _all_ids(ensure_config(config_file)) == ids
    assert config_file.read_bytes() == before
    assert config_file.stat().st_mtime_ns == before_mtime


def test_backfill_preserves_api_key_and_mode(tmp_path: Path) -> None:
    """API key strings are unchanged and the file is 0600 after a backfill write."""
    config_file = _write(tmp_path, THREE_INSTANCES_TOML)
    ensure_config(config_file)
    data = tomllib.loads(config_file.read_text())
    assert data["sonarr"]["Main"]["api_key"] == "sonarr-key"
    assert data["sonarr"]["4K"]["api_key"] == "sonarr4k-key"
    assert data["radarr"]["Default"]["api_key"] == "radarr-key"
    assert config_file.stat().st_mode & 0o777 == 0o600
