"""Shared test fixtures and factory functions for Triggarr tests."""

from __future__ import annotations

import pytest

from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
from triggarr.state import TriggarrState, _default_state
from triggarr.web.middleware import AuthMiddleware


@pytest.fixture(autouse=True)
def _reset_disabled_warned():
    """Reset AuthMiddleware._disabled_warned before each test to avoid order-dependent failures."""
    AuthMiddleware._disabled_warned = False
    yield
    AuthMiddleware._disabled_warned = False


def make_settings(
    radarr_url: str = "http://radarr:7878",
    radarr_enabled: bool = True,
    radarr_api_key: str = "radarr-test-key",
    sonarr_url: str = "http://sonarr:8989",
    sonarr_enabled: bool = True,
    sonarr_api_key: str = "sonarr-test-key",
    lidarr_url: str = "http://lidarr:8686",
    lidarr_enabled: bool = True,
    lidarr_api_key: str = "lidarr-test-key",
    search_missing_count: int = 5,
    search_cutoff_count: int = 5,
    search_interval: int = 30,
    general: GeneralConfig | None = None,
) -> Settings:
    """Build a Settings instance with sensible test defaults.

    Accepts keyword overrides for any field.  Default: all apps enabled
    with service-name URLs and dummy API keys.  Uses dict-based radarr/sonarr/lidarr
    with a "Default" instance name.
    """
    return Settings(
        general=general or GeneralConfig(),
        radarr={"Default": InstanceConfig(
            url=radarr_url,
            api_key=radarr_api_key,
            enabled=radarr_enabled,
            search_missing_count=search_missing_count,
            search_cutoff_count=search_cutoff_count,
            search_interval=search_interval,
        )},
        sonarr={"Default": InstanceConfig(
            url=sonarr_url,
            api_key=sonarr_api_key,
            enabled=sonarr_enabled,
            search_missing_count=search_missing_count,
            search_cutoff_count=search_cutoff_count,
            search_interval=search_interval,
        )},
        lidarr={"Default": InstanceConfig(
            url=lidarr_url,
            api_key=lidarr_api_key,
            enabled=lidarr_enabled,
            search_missing_count=search_missing_count,
            search_cutoff_count=search_cutoff_count,
            search_interval=search_interval,
        )},
    )


def default_state(settings: Settings | None = None) -> TriggarrState:
    """Return a fresh default application state.

    Re-exports ``_default_state()`` from ``triggarr.state`` so test files
    do not need to import internal helpers directly.

    Args:
        settings: Optional Settings instance.  When provided, the returned
            state contains per-instance entries for every configured instance.
    """
    return _default_state(settings)
