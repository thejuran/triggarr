"""Shared test fixtures and factory functions for Triggarr tests."""

from __future__ import annotations

from triggarr.models.config import ArrConfig, GeneralConfig, Settings
from triggarr.state import _default_state


def make_settings(
    radarr_url: str = "http://radarr:7878",
    radarr_enabled: bool = True,
    radarr_api_key: str = "radarr-test-key",
    sonarr_url: str = "http://sonarr:8989",
    sonarr_enabled: bool = True,
    sonarr_api_key: str = "sonarr-test-key",
    search_missing_count: int = 5,
    search_cutoff_count: int = 5,
    search_interval: int = 30,
    general: GeneralConfig | None = None,
) -> Settings:
    """Build a Settings instance with sensible test defaults.

    Accepts keyword overrides for any field.  Default: both apps enabled
    with service-name URLs and dummy API keys.
    """
    return Settings(
        general=general or GeneralConfig(),
        radarr=ArrConfig(
            url=radarr_url,
            api_key=radarr_api_key,
            enabled=radarr_enabled,
            search_missing_count=search_missing_count,
            search_cutoff_count=search_cutoff_count,
            search_interval=search_interval,
        ),
        sonarr=ArrConfig(
            url=sonarr_url,
            api_key=sonarr_api_key,
            enabled=sonarr_enabled,
            search_missing_count=search_missing_count,
            search_cutoff_count=search_cutoff_count,
            search_interval=search_interval,
        ),
    )


def default_state():
    """Return a fresh default application state.

    Re-exports ``_default_state()`` from ``triggarr.state`` so test files
    do not need to import internal helpers directly.
    """
    return _default_state()
