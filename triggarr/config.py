"""TOML configuration loading and default config generation."""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

from triggarr.models.config import Settings

# Default commented config template written on first run.
DEFAULT_CONFIG = """\
# Triggarr Configuration
# Edit this file and restart Triggarr.

[general]
# Log level: debug, info, warning, error
log_level = "info"
# hard_max_per_cycle = 0   # 0 = unlimited; caps total items searched per app per cycle

[radarr]
# Radarr connection settings
url = ""           # e.g. "http://radarr:7878"
api_key = ""       # From Radarr > Settings > General > API Key
enabled = false
# search_interval = 30       # Minutes between search cycles
# search_missing_count = 5   # Missing items to search per cycle
# search_cutoff_count = 5    # Cutoff items to search per cycle

[sonarr]
# Sonarr connection settings
url = ""           # e.g. "http://sonarr:8989"
api_key = ""       # From Sonarr > Settings > General > API Key
enabled = false
# search_interval = 30       # Minutes between search cycles
# search_missing_count = 5   # Missing items to search per cycle
# search_cutoff_count = 5    # Cutoff items to search per cycle
"""


def load_settings(config_path: Path) -> Settings:
    """Load and return Settings from a TOML config file.

    Reads the TOML file directly and passes parsed data to Settings,
    bypassing the class-level toml_file config so any path can be used.

    Args:
        config_path: Path to the TOML configuration file.

    Returns:
        Validated Settings instance.
    """
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    return Settings(**data)


def generate_default_config(config_path: Path) -> None:
    """Write a commented default TOML config template to disk.

    Args:
        config_path: Destination path for the config file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG)
    os.chmod(config_path, 0o600)


def ensure_config(config_path: Path) -> Settings:
    """Ensure config file exists and load settings.

    If the config file is missing, generates a default template,
    prints a message to stderr, and exits with code 1.

    Args:
        config_path: Path to the TOML configuration file.

    Returns:
        Validated Settings instance.
    """
    if not config_path.exists():
        generate_default_config(config_path)
        print(
            f"Default config written to {config_path}\n"
            "Edit the config file and restart Triggarr.",
            file=sys.stderr,
        )
        sys.exit(1)

    return load_settings(config_path)
