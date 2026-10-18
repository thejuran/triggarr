"""TOML configuration loading, default config generation, and v2.2 migration."""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import NoReturn

import tomli_w
import tomlkit
from loguru import logger
from pydantic import ValidationError

from triggarr.models.config import APP_TYPES, Settings

# Default commented config template written on first run.
# Instance configuration is managed through the web UI -- radarr/sonarr
# sections are empty by default.
DEFAULT_CONFIG = """\
# Triggarr Configuration

[general]
# Log level: debug, info, warning, error
log_level = "info"
# hard_max_per_cycle = 0
# max_history_rows = 1000
# request_timeout = 30.0
# page_size = 50
# tracking_window_minutes = 60
# tracking_delay_seconds = 90
# max_consecutive_failures = 5
# skip_unreleased = true

# Tag filtering: configure missing_tag and cutoff_tag per instance
# to limit searches to items bearing a specific tag.
# Example: missing_tag = "triggarr"

# Instance configuration is managed through the web UI.
# Add your first Radarr or Sonarr instance at: http://<host>:8484/settings

[radarr]

[sonarr]

[lidarr]
"""

# Keys that appear directly under [radarr] or [sonarr] in v2.2 flat format
_V22_FLAT_KEYS = {"url", "api_key", "enabled"}


def new_instance_id() -> str:
    """Return a fresh permanent instance ID (32 lowercase hex chars from a CSPRNG)."""
    return secrets.token_hex(16)


def _settings_to_dict(settings: Settings) -> dict:
    """Convert Settings to a plain dict suitable for TOML serialization.

    Lives in config.py so both the web routes and config helpers share it. This
    is still the sole extraction point for SecretStr -> plain string for TOML
    serialization outside of HTTP client init (see CLAUDE.md SecretStr convention).
    """
    result: dict = {"general": settings.general.model_dump()}
    for app_name in APP_TYPES:
        instances = getattr(settings, app_name)
        result[app_name] = {}
        for inst_name, cfg in instances.items():
            d = cfg.model_dump()
            d["api_key"] = cfg.api_key.get_secret_value()  # TOML serialization extraction
            result[app_name][inst_name] = d
    # Auth section: extract SecretStr values for TOML serialization
    auth = settings.auth
    result["auth"] = {
        "method": auth.method,
        "username": auth.username,
        "password_hash": auth.password_hash.get_secret_value(),
        "api_key": auth.api_key.get_secret_value(),
        "session_secret": auth.session_secret.get_secret_value(),
    }
    return result


def _is_v22_format(data: dict) -> bool:
    """Check if parsed TOML data uses the v2.2 flat config format.

    In v2.2, [radarr] and [sonarr] sections contain url/api_key/enabled
    directly. In v2.3, they contain named instance sub-tables.

    Args:
        data: Parsed TOML data dict.

    Returns:
        True if v2.2 flat format detected.
    """
    for section in ("radarr", "sonarr"):
        section_data = data.get(section, {})
        if section_data and _V22_FLAT_KEYS & section_data.keys():
            return True
    return False


def _migrate_v22_to_v23(data: dict) -> dict:
    """Transform v2.2 flat config data to v2.3 multi-instance format.

    Wraps flat [radarr] and [sonarr] sections into {"Default": {...}}.
    Preserves [general] section unchanged.

    Args:
        data: Parsed v2.2 TOML data dict.

    Returns:
        New dict with v2.3 multi-instance structure.
    """
    result = dict(data)
    for section in ("radarr", "sonarr"):
        section_data = result.get(section, {})
        if section_data and _V22_FLAT_KEYS & section_data.keys():
            result[section] = {"Default": section_data}
    return result


def _atomic_toml_write(path: Path, data: dict) -> None:
    """Write TOML data to a file atomically using tempfile + fsync + rename.

    On failure (e.g. serialization error), the temp file is cleaned up
    so no orphaned files remain on disk. OSError during the write
    (os.replace / fsync) is logged with the config path before re-raise.
    Non-FileNotFoundError OSError during temp cleanup is also logged so
    permission / read-only / no-space failures are observable (SAFETY-04).

    Args:
        path: Destination file path.
        data: TOML-serializable dict.
    """
    dir_fd = None
    renamed = False
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        renamed = True
        # fsync the directory to ensure rename is durable
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as exc:
        if renamed:
            # os.replace already committed the new contents; only the durability
            # fsync on the parent directory failed. Surface as a warning so the
            # caller does not treat a succeeded write as a failure.
            logger.warning(
                "Config written but directory fsync failed: {path} - {exc}",
                path=path,
                exc=exc,
            )
            return
        logger.error("Config write failed: {path} - {exc}", path=path, exc=exc)
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    except Exception as exc:
        logger.error(
            "Config write failed (unexpected error): {path} - {exc}",
            path=path,
            exc=exc,
        )
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    finally:
        if dir_fd is not None:
            os.close(dir_fd)


def _atomic_text_write(path: Path, text: str) -> None:
    """Write pre-rendered text to a file atomically using tempfile + fsync + rename.

    Mirrors _atomic_toml_write's write-then-rename shape, with one deliberate
    difference copied from triggarr/web/routes.py::_write_reset_token_file:
    the mkstemp fd's permission is set to 0600 BEFORE writing, so the file
    is already 0600 when os.replace makes it live -- there is no post-replace
    chmod window. Used by the instance-id backfill, whose tomlkit-rendered
    text must reach disk byte-for-byte (tomli_w would re-serialize and drop
    comments).

    Failure before or at os.replace (temp write, fsync, fchmod, replace
    itself): logs an error naming the path and the exception type, removes
    the temp file, and re-raises -- the destination file is untouched.
    Failure only on the post-replace directory fsync: the new contents are
    already committed, so this logs a warning and returns normally.

    Args:
        path: Destination file path.
        text: Text content to write (encoded as UTF-8).
    """
    dir_fd = None
    renamed = False
    fd_owned = False
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.fchmod(fd, 0o600)
        fd_owned = True
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        renamed = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as exc:
        if renamed:
            logger.warning(
                "Config written but the directory sync failed: {path} - {exc}",
                path=path,
                exc=exc,
            )
            return
        logger.error(
            "Config write failed: {path} - {exc_type}",
            path=path,
            exc_type=type(exc).__name__,
        )
        if not fd_owned:
            # os.fdopen never took ownership -- close the raw fd to avoid a leak.
            with contextlib.suppress(OSError):
                os.close(fd)
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    finally:
        if dir_fd is not None:
            os.close(dir_fd)


def backfill_instance_ids(config_path: Path, settings: Settings) -> Settings:
    """Backfill missing or duplicate instance ids, preserving every TOML comment.

    Walks APP_TYPES and each app's instances in dict (TOML) order. An
    instance is a backfill target when its id is "" (missing or empty) or
    duplicates an earlier instance's id within the same app (a hand-edited
    collision; duplicates across different apps are not a collision -- the
    composite ownership key includes the app). If there are no targets,
    returns settings unchanged without reading the file for writing.

    Otherwise the file is re-parsed with tomlkit (comment-preserving) and
    each target's id is set in place. The result is validated BEFORE
    writing: re-parsed with tomllib, re-validated with Settings(**parsed),
    and checked that the only difference from the original parse is the
    planned id values -- tomlkit must never silently touch anything else.
    Only after all three checks pass does the write happen, via
    _atomic_text_write.

    Failure rules:
    - A failure before or at _atomic_text_write's os.replace leaves the
      original file intact (the temp file is removed by _atomic_text_write).
      Running on ids that were never saved would mint different ids next
      time, and ensure_config runs before the database is opened, so nothing
      references the unsaved ids -- this function logs the failure and exits
      the process; the next startup re-mints from the unchanged file.
    - A failure only on the post-replace directory fsync means the new ids
      are already committed to disk and match the returned Settings, so this
      function logs a warning and returns normally. The next startup finds
      every id already valid and unique, so there are no targets: no
      re-mint, no rewrite.

    Args:
        config_path: Path to the TOML configuration file.
        settings: Already-loaded, validated Settings for this file.

    Returns:
        Settings with every instance id present and unique per app --
        identical in content to the input when no backfill was needed.
    """
    targets: list[tuple[str, str, str]] = []
    for app in APP_TYPES:
        seen_ids: dict[str, str] = {}
        for name, cfg in getattr(settings, app).items():
            if not cfg.id:
                targets.append((app, name, new_instance_id()))
                continue
            if cfg.id in seen_ids:
                logger.warning(
                    "{app} instance '{name}' shares instance '{other}'s id -- assigning a new id",
                    app=app,
                    name=name,
                    other=seen_ids[cfg.id],
                )
                targets.append((app, name, new_instance_id()))
                continue
            seen_ids[cfg.id] = name

    if not targets:
        return settings

    # read_bytes + manual decode (not read_text/open-in-text-mode) so CRLF line
    # endings in the operator's file are not translated to LF before parsing.
    original_text = config_path.read_bytes().decode("utf-8")
    doc = tomlkit.parse(original_text)
    for app, name, new_id in targets:
        doc[app][name]["id"] = new_id
    new_text = tomlkit.dumps(doc)

    parsed = tomllib.loads(new_text)
    try:
        validated = Settings(**parsed)
    except ValidationError as exc:
        _log_invalid_config_and_exit(config_path, exc)

    expected = tomllib.loads(original_text)
    for app, name, new_id in targets:
        expected[app][name]["id"] = new_id
    if parsed != expected:
        logger.error(
            "Instance id backfill would change more than id values -- aborting without writing: {path}",
            path=config_path,
        )
        sys.exit(1)

    try:
        _atomic_text_write(config_path, new_text)
    except OSError:
        sys.exit(1)

    logger.info(
        "Backfilled {count} instance id(s) in {path}",
        count=len(targets),
        path=config_path,
    )
    return validated


def detect_and_migrate_v22(config_path: Path) -> bool:
    """Detect v2.2 config format and migrate to v2.3 multi-instance format.

    If the config file uses the v2.2 flat format (url/api_key/enabled directly
    under [radarr] or [sonarr]), it is migrated to the v2.3 nested format
    with instance name "Default".

    Steps:
    1. Read and parse existing config
    2. If not v2.2 format, return False
    3. Backup original to triggarr.toml.bak
    4. Migrate data structure
    5. Write migrated config atomically
    6. Create .migrated marker for web UI banner
    7. Return True

    Args:
        config_path: Path to the TOML configuration file.

    Returns:
        True if migration was performed, False if already v2.3 format.
    """
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    if not _is_v22_format(data):
        return False

    # Backup original config
    backup_path = config_path.with_suffix(".toml.bak")
    shutil.copy2(config_path, backup_path)

    # Migrate data structure
    migrated = _migrate_v22_to_v23(data)

    # Write migrated config atomically
    _atomic_toml_write(config_path, migrated)

    # Create marker file for web UI banner
    marker = config_path.parent / ".migrated"
    marker.touch()

    logger.info("Config migrated from v2.2 to v2.3 multi-instance format")
    logger.info("Original config backed up to {path}", path=backup_path)

    return True


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
    """Write a commented default TOML config template to disk atomically.

    Args:
        config_path: Destination path for the config file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    dir_fd = None
    renamed = False
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, config_path)
        renamed = True
        dir_fd = os.open(config_path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as exc:
        if renamed:
            logger.warning(
                "Default config written but directory fsync failed: {path} - {exc}",
                path=config_path,
                exc=exc,
            )
            # Still chmod -- the file exists on disk and must be 0o600
            # regardless of the durability-fsync outcome.
            with contextlib.suppress(OSError):
                os.chmod(config_path, 0o600)
            return
        logger.error(
            "Default config write failed: {path} - {exc}",
            path=config_path,
            exc=exc,
        )
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during default config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    except Exception as exc:
        logger.error(
            "Default config write failed (unexpected error): {path} - {exc}",
            path=config_path,
            exc=exc,
        )
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during default config write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
    os.chmod(config_path, 0o600)


def _log_corrupt_config_and_exit(config_path: Path, exc: Exception) -> NoReturn:
    """Log a friendly TOML-corruption error and exit with code 1 (TEST-02).

    Emits structured loguru.error lines that name the config path and either
    point at the `.toml.bak` backup with a `cp` restore hint (when present)
    or tell the operator how to regenerate the default template (when absent).
    Path-only disclosure — no config contents or secrets are logged.

    Args:
        config_path: Path to the corrupt TOML configuration file.
        exc: The TOMLDecodeError or UnicodeDecodeError that triggered this.
    """
    backup_path = config_path.with_suffix(".toml.bak")
    logger.error(
        "Failed to parse config file {path}: {exc}",
        path=config_path,
        exc=exc,
    )
    if backup_path.exists():
        logger.error(
            "A backup is available at {backup} -- to restore: cp {backup} {path}",
            backup=backup_path,
            path=config_path,
        )
    else:
        logger.error(
            "No automatic backup exists. Restore from your own backup or "
            "delete {path} to regenerate the default template.",
            path=config_path,
        )
    sys.exit(1)


def _log_invalid_config_and_exit(config_path: Path, exc: ValidationError) -> NoReturn:
    """Log a friendly schema-validation error and exit with code 1.

    A `pydantic.ValidationError` at load time means the config parsed as TOML
    but failed a model rule -- e.g. an instance ``url`` that is a placeholder
    (``http://``), a non-http scheme, or a blocked SSRF target (cloud-metadata /
    link-local). Without this handler the error propagates uncaught out of
    ``asyncio.run(_run())`` as a bare traceback; here it becomes a path-scoped
    operator message naming the offending field(s). Pydantic's ``errors()`` only
    exposes field locations and rule messages -- never the submitted values --
    so no config contents or secrets are logged.

    Args:
        config_path: Path to the config file that failed validation.
        exc: The ValidationError raised while constructing Settings.
    """
    logger.error("Config file {path} failed validation:", path=config_path)
    for err in exc.errors():
        location = ".".join(str(part) for part in err["loc"]) or "(root)"
        logger.error("  {loc}: {msg}", loc=location, msg=err["msg"])
    logger.error(
        "Edit {path} to correct the field(s) above and restart Triggarr.",
        path=config_path,
    )
    sys.exit(1)


def ensure_config(config_path: Path) -> Settings:
    """Ensure config file exists and load settings.

    If the config file is missing, generates a default template,
    prints a message to stderr, and exits with code 1.

    For existing configs, runs v2.2 migration detection before loading.
    A `tomllib.TOMLDecodeError` or `UnicodeDecodeError` from either the
    migration probe or the final load is translated into a friendly
    loguru.error line (mentioning the `.toml.bak` backup when present)
    and `sys.exit(1)` — instead of an uncaught traceback from
    `asyncio.run(_run())` (TEST-02). A `pydantic.ValidationError` (e.g. a
    placeholder/blocked instance `url` rejected at load) is likewise
    translated into a path-scoped, field-level loguru.error and `sys.exit(1)`.
    `OSError` (permission denied) continues to propagate uncaught.

    Args:
        config_path: Path to the TOML configuration file.

    Returns:
        Validated Settings instance.
    """
    if not config_path.exists():
        generate_default_config(config_path)
        logger.warning(
            "Default config written to {path} -- edit the config file and restart Triggarr",
            path=config_path,
        )
        sys.exit(1)

    try:
        migrated = detect_and_migrate_v22(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)

    if migrated:
        backup_path = config_path.with_suffix(".toml.bak")
        logger.info("v2.2 config backed up to {path}", path=backup_path)

    try:
        settings = load_settings(config_path)
        return backfill_instance_ids(config_path, settings)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)
    except ValidationError as exc:
        _log_invalid_config_and_exit(config_path, exc)
