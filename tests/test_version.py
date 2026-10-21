"""The app's displayed version must match the packaged release version.

The nav-bar badge and the update check read ``triggarr.__version__``, while
the package version comes from ``pyproject.toml`` (mirrored in ``uv.lock``).
v2.11.1 bumped only ``pyproject.toml``, so every v2.11.1 and later build
called itself v2.11.0 and offered "v2.11.1 available" as an update.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from triggarr import __version__
from triggarr.version import get_display_version

_ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    with (_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _uv_lock_version() -> str:
    with (_ROOT / "uv.lock").open("rb") as fh:
        lock = tomllib.load(fh)
    return next(p["version"] for p in lock["package"] if p["name"] == "triggarr")


def test_package_version_matches_pyproject():
    assert __version__ == _pyproject_version()


def test_uv_lock_records_the_same_version():
    assert _uv_lock_version() == _pyproject_version()


def test_release_badge_shows_the_package_version():
    assert get_display_version() == f"v{_pyproject_version()}"
