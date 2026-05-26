"""Pydantic models for Triggarr TOML configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource

APP_TYPES: tuple[str, ...] = ("radarr", "sonarr", "lidarr")
"""Supported *arr application types. Used across config, state, scheduler, and routes."""


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


def get_config_path() -> Path:
    """Return the config file path derived from the current config directory."""
    return get_config_dir() / "triggarr.toml"


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

    # Tag filtering (empty = search all items, no filtering)
    missing_tag: str = ""  # Tag name for missing queue filter
    cutoff_tag: str = ""  # Tag name for cutoff queue filter

    @field_validator("url")
    @classmethod
    def reject_apikey_in_url(cls, v: str) -> str:
        """SEC-02 D-06/D-07/D-08: Reject URLs whose query string contains an apikey= parameter
        (any case, including the empty-value variant and URL-encoded forms like apikey%3D...).

        The validator runs at model construction time -- BEFORE the settings POST handler
        acquires search_lock and BEFORE _atomic_toml_write runs -- so a URL carrying an
        embedded API key never reaches the filesystem. Per D-07 the rule is narrow: only
        apikey= keys (any case) are rejected; legitimate non-apikey query parameters
        (?base=/sonarr, ?token=foo) remain valid for reverse-proxy/subpath setups.
        """
        if not v:
            return v
        parsed = urlparse(v)
        if not parsed.query:
            return v
        # keep_blank_values=True so ?apikey= (empty value) is still parsed (Pitfall 6).
        # startswith("apikey") catches the URL-encoded variant ?apikey%3Dsecret which
        # parse_qsl decodes to key=`apikey=secret` (codex M2 finding 2026-05-26).
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower().startswith("apikey"):
                msg = "URL must not contain an apikey= query parameter. Use the API Key field instead."
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def at_least_one_search_count(self) -> InstanceConfig:
        """Ensure at least one search count is positive when instance is enabled."""
        if self.enabled and self.search_missing_count <= 0 and self.search_cutoff_count <= 0:
            msg = "At least one of search_missing_count or search_cutoff_count must be > 0 when enabled"
            raise ValueError(msg)
        return self


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
    # SAFETY-03: bounded 1..100 to defend against typos at config edit time
    max_consecutive_failures: int = Field(default=5, ge=1, le=100)
    # v2.2: skip Radarr movies without past digital/physical release date
    skip_unreleased: bool = True


class AuthConfig(BaseModel):
    """Authentication configuration for Triggarr.

    When username is empty, the app is in 'needs setup' state.
    When method is 'Disabled', all endpoints are accessible without auth.
    """

    method: Literal["Forms", "Basic", "External", "Disabled"] = "Forms"
    username: str = ""
    password_hash: SecretStr = SecretStr("")
    api_key: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")

    @property
    def needs_setup(self) -> bool:
        """True when credentials have not been configured yet."""
        return not self.username

    @property
    def is_disabled(self) -> bool:
        """True when auth is explicitly disabled via config."""
        return self.method == "Disabled"


class Settings(BaseSettings):
    """Application settings loaded from TOML config file.

    Sections: [general], [auth], [radarr], [sonarr].
    Radarr and sonarr hold dict[str, InstanceConfig] mapping instance names
    to their configurations (e.g., {"4K Radarr": InstanceConfig(...)}).
    """

    model_config = {
        "toml_file": CONFIG_PATH,
    }

    general: GeneralConfig = GeneralConfig()
    auth: AuthConfig = AuthConfig()
    radarr: dict[str, InstanceConfig] = {}
    sonarr: dict[str, InstanceConfig] = {}
    lidarr: dict[str, InstanceConfig] = {}

    @model_validator(mode="after")
    def validate_instances(self) -> Settings:
        """Enforce maximum 5 instances per app type."""
        for app_type in APP_TYPES:
            instances = getattr(self, app_type)
            if len(instances) > 5:
                msg = f"Maximum 5 {app_type} instances allowed"
                raise ValueError(msg)
        return self

    @property
    def has_enabled_app(self) -> bool:
        """Check if at least one instance across any app type is enabled with a URL."""
        for app_type in APP_TYPES:
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
