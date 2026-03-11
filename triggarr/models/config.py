"""Pydantic models for Triggarr TOML configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource


def get_config_dir() -> Path:
    """Return the config directory, respecting TRIGGARR_CONFIG_DIR env var.

    Defaults to /config when the env var is not set (backward compatible).

    Raises:
        ValueError: If TRIGGARR_CONFIG_DIR is set to a relative path.
    """
    raw = os.environ.get("TRIGGARR_CONFIG_DIR", "/config")
    path = Path(raw)
    if not path.is_absolute():
        msg = f"TRIGGARR_CONFIG_DIR must be an absolute path, got: {raw}"
        raise ValueError(msg)
    return path.resolve()


CONFIG_DIR = get_config_dir()
CONFIG_PATH = CONFIG_DIR / "triggarr.toml"
# NOTE: CONFIG_DIR and CONFIG_PATH are evaluated once at first import.
# Changing TRIGGARR_CONFIG_DIR after import has no effect on these constants.
# Functions accept path parameters to allow testing without module reload.


class InstanceConfig(BaseModel):
    """Configuration for a single *arr instance.

    Each named instance holds its own URL, API key, schedule, and batch sizes.
    Multiple instances can be configured per app type (radarr, sonarr).
    """

    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False

    # Search tuning (sensible defaults -- override in config to customize)
    search_interval: int = 30  # Minutes between search cycles
    search_missing_count: int = 5  # Missing items to search per cycle
    search_cutoff_count: int = 5  # Cutoff items to search per cycle

    @model_validator(mode="after")
    def at_least_one_search_count(self) -> InstanceConfig:
        """Ensure at least one search count is positive when instance is enabled."""
        if self.enabled and self.search_missing_count <= 0 and self.search_cutoff_count <= 0:
            msg = "At least one of search_missing_count or search_cutoff_count must be > 0 when enabled"
            raise ValueError(msg)
        return self


# Backward-compat alias for transition period (Plan 02+ will update consumers)
ArrConfig = InstanceConfig


class GeneralConfig(BaseModel):
    """Global application settings."""

    log_level: str = "info"
    hard_max_per_cycle: int = 0  # 0 = unlimited; caps total items per app per cycle
    # v2.0 additions
    max_history_rows: int = 1000  # DEBT-03: max resolved rows kept in search_history
    request_timeout: float = 30.0  # DEBT-07: outbound HTTP timeout in seconds
    page_size: int = 50  # DEBT-08: *arr API pagination size
    tracking_window_minutes: int = 60  # TRACK-07: how long to wait for grabs after search
    tracking_delay_seconds: int = 90  # Delay before tracking check (unused)
    # v2.2: skip Radarr movies without past digital/physical release date
    skip_unreleased: bool = True


class Settings(BaseSettings):
    """Application settings loaded from TOML config file.

    Sections: [general], [radarr], [sonarr].
    Radarr and sonarr hold dict[str, InstanceConfig] mapping instance names
    to their configurations (e.g., {"4K Radarr": InstanceConfig(...)}).
    """

    model_config = {
        "toml_file": CONFIG_PATH,
    }

    general: GeneralConfig = GeneralConfig()
    radarr: dict[str, InstanceConfig] = {}
    sonarr: dict[str, InstanceConfig] = {}

    @model_validator(mode="after")
    def validate_instances(self) -> Settings:
        """Enforce maximum 5 instances per app type."""
        for app_type in ("radarr", "sonarr"):
            instances = getattr(self, app_type)
            if len(instances) > 5:
                msg = f"Maximum 5 {app_type} instances allowed"
                raise ValueError(msg)
        return self

    @property
    def has_enabled_app(self) -> bool:
        """Check if at least one instance across any app type is enabled with a URL."""
        for app_type in ("radarr", "sonarr"):
            for cfg in getattr(self, app_type).values():
                if cfg.enabled and cfg.url.strip():
                    return True
        return False

    def get_enabled_instances(self, app_type: str) -> dict[str, InstanceConfig]:
        """Return only enabled instances with non-empty URLs for an app type."""
        return {name: cfg for name, cfg in getattr(self, app_type).items() if cfg.enabled and cfg.url.strip()}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls),
        )
