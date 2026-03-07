"""Pydantic models for Triggarr TOML configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource

CONFIG_PATH = Path("/config/triggarr.toml")


class ArrConfig(BaseModel):
    """Connection configuration for a single *arr application."""

    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False

    # Search tuning (sensible defaults -- override in config to customize)
    search_interval: int = 30  # Minutes between search cycles
    search_missing_count: int = 5  # Missing items to search per cycle
    search_cutoff_count: int = 5  # Cutoff items to search per cycle

    @model_validator(mode="after")
    def at_least_one_search_count(self) -> ArrConfig:
        """Enforce that at least one search count is >= 1 when app is enabled."""
        if self.enabled and self.search_missing_count + self.search_cutoff_count < 1:
            msg = "At least one of search_missing_count or search_cutoff_count must be >= 1 when enabled"
            raise ValueError(msg)
        return self


class GeneralConfig(BaseModel):
    """Global application settings."""

    log_level: str = "info"
    hard_max_per_cycle: int = 0  # 0 = unlimited; caps total items per app per cycle


class Settings(BaseSettings):
    """Application settings loaded from TOML config file.

    Sections: [general], [radarr], [sonarr].
    """

    model_config = {
        "toml_file": CONFIG_PATH,
    }

    general: GeneralConfig = GeneralConfig()
    radarr: ArrConfig = ArrConfig()
    sonarr: ArrConfig = ArrConfig()

    @property
    def has_enabled_app(self) -> bool:
        """Check if at least one app is configured with a URL and enabled."""
        radarr_ok = self.radarr.enabled and self.radarr.url.strip()
        sonarr_ok = self.sonarr.enabled and self.sonarr.url.strip()
        return radarr_ok or sonarr_ok

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
