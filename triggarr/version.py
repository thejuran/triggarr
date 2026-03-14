"""Version display logic.

Provides a human-readable version string for the UI:
- Tagged releases (via Docker/pip): use __version__ e.g. "v2.3.0"
- Dev builds (running from git): use "dev (abc1234)" with git short hash
"""

from __future__ import annotations

import subprocess

from triggarr import __version__


def get_display_version() -> str:
    """Return the version string shown in the nav bar.

    For dev versions (containing 'dev'), returns 'dev (<short-hash>)'.
    For release versions, returns 'v<version>'.
    Falls back to 'v<__version__>' if git is unavailable.
    """
    if "dev" not in __version__:
        return f"v{__version__}"

    try:
        short_hash = (
            subprocess.check_output(  # noqa: S603, S607
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
        return f"dev ({short_hash})"
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return f"v{__version__}"
