"""Image/lockfile consistency checker (CIMAINT-01).

Proves the exact set of packages installed in the shipped image matches
`uv.lock`, so the production image can never silently diverge from the
dependency set `pip-audit` and CI's tests already covered.

This script runs in two distinct modes, deliberately kept independent of
each other's import requirements:

1. ``--dump-environment`` -- runs *inside* the bare production image
   (``docker run --entrypoint python <image> image_lock_consistency.py
   --dump-environment``), where only the Python stdlib is available. It
   prints a JSON object of PEP 508 marker-environment values built from
   ``os``/``platform``/``sys`` alone.
2. ``--locked``/``--freeze``/``--environment`` -- runs on the CI runner
   (or a developer's machine) where the project's dev dependencies,
   including ``packaging`` (a transitive dependency of ``pytest``), are
   installed. It compares a `uv export`'d lockfile against a `pip freeze`
   of the image and reports every discrepancy.

Because mode 1 must stay importable with zero third-party packages,
``packaging`` is imported lazily inside ``compare()``, never at module
scope.

This is CI tooling, not the Triggarr application, so it prints directly to
stdout/stderr via the builtin ``print`` -- CLAUDE.md's loguru-only logging
rule applies to the application, not to standalone build/CI scripts that
must also run inside a bare image with no application dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from pathlib import Path

_HASH_FLAG_RE = re.compile(r"\s*--hash=\S+")
_NAME_SEPARATOR_RE = re.compile(r"[-_.]+")

_DEFAULT_ALLOWED_EXTRA = frozenset({"pip"})


def normalize_name(name: str) -> str:
    """Normalize a package name per PEP 503 (lowercase, runs of -_. to '-')."""
    return _NAME_SEPARATOR_RE.sub("-", name).lower()


def _join_continuations(text: str) -> list[str]:
    """Join backslash-continued physical lines into logical lines.

    Comment lines (``# via`` and its indented continuations) are never
    backslash-continued in `uv export`'s output, so each is returned as
    its own logical line and never absorbed into a requirement's buffer.
    """
    logical_lines: list[str] = []
    buffer: list[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            logical_lines.append(stripped)
            continue
        if stripped.endswith("\\"):
            buffer.append(stripped[:-1].strip())
            continue
        buffer.append(stripped)
        logical_lines.append(" ".join(part for part in buffer if part))
        buffer = []
    if buffer:
        logical_lines.append(" ".join(part for part in buffer if part))
    return logical_lines


def parse_locked(text: str) -> list[tuple[str, str, str | None]]:
    """Parse a `uv export --locked` requirements-txt into (name, version, marker).

    Fails closed: a requirement without an exact `==` pin raises ValueError,
    because this checker's entire purpose is proving the image matches an
    *exact* locked set.
    """
    requirements: list[tuple[str, str, str | None]] = []
    for line in _join_continuations(text):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        without_hashes = _HASH_FLAG_RE.sub("", stripped).strip()
        name_version, _, marker = without_hashes.partition(";")
        name_version = name_version.strip()
        marker = marker.strip() or None
        if "==" not in name_version:
            raise ValueError(f"not an exact pin: {stripped!r}")
        name, _, version = name_version.partition("==")
        name = name.strip()
        version = version.strip()
        if not name or not version or any(ch in version for ch in "<>=!~, "):
            raise ValueError(f"not an exact pin: {stripped!r}")
        requirements.append((name, version, marker))
    return requirements


def parse_freeze(text: str) -> dict[str, str]:
    """Parse `pip freeze --all --exclude triggarr` output into {name: version}.

    Fails closed: any line that isn't a plain `name==version` pin (e.g. a
    direct URL/editable reference such as `name @ file:///x`) raises
    ValueError rather than being silently skipped.
    """
    freeze: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"unsupported freeze line: {line!r}")
        name, _, version = line.partition("==")
        name = name.strip()
        version = version.strip()
        if not name or not version or " " in version:
            raise ValueError(f"unsupported freeze line: {line!r}")
        freeze[name] = version
    return freeze


def _format_full_version(info) -> str:
    """Reproduce `packaging.markers.default_environment`'s version formatting
    (`sys.implementation.version`'s named tuple) using the stdlib only."""
    version = f"{info.major}.{info.minor}.{info.micro}"
    kind = info.releaselevel
    if kind != "final":
        version += kind[0] + str(info.serial)
    return version


def dump_environment() -> dict[str, str]:
    """Build the PEP 508 marker environment for the current interpreter,
    using only `os`/`platform`/`sys` so this runs inside the bare image."""
    return {
        "implementation_name": sys.implementation.name,
        "implementation_version": _format_full_version(sys.implementation.version),
        "os_name": os.name,
        "platform_machine": platform.machine(),
        "platform_python_implementation": platform.python_implementation(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "platform_version": platform.version(),
        "python_full_version": platform.python_version(),
        "python_version": ".".join(platform.python_version_tuple()[:2]),
        "sys_platform": sys.platform,
    }


def compare(
    locked: list[tuple[str, str, str | None]],
    freeze: dict[str, str],
    environment: dict[str, str],
    allowed_extra: frozenset[str] = _DEFAULT_ALLOWED_EXTRA,
) -> list[str]:
    """Compare a parsed lockfile export against a parsed image freeze.

    Markers are evaluated against *environment* (the image's own dump, not
    this process's host) so a Windows-only dependency never produces a
    "missing from image" false positive on a Linux-built image. Only
    *allowed_extra* names (base-image tooling such as pip) may appear in
    the image without being locked. Returns a sorted list of human-readable
    problem strings; an empty list means the image matches the lockfile.
    """
    from packaging.markers import Marker

    freeze_by_normalized: dict[str, tuple[str, str]] = {
        normalize_name(name): (name, version) for name, version in freeze.items()
    }
    allowed_extra_normalized = {normalize_name(name) for name in allowed_extra}

    problems: list[str] = []
    accounted_for: set[str] = set()

    for name, version, marker in locked:
        if marker is not None and not Marker(marker).evaluate(environment):
            continue
        normalized = normalize_name(name)
        accounted_for.add(normalized)
        if normalized not in freeze_by_normalized:
            problems.append(f"missing from image: {name}=={version}")
            continue
        _, image_version = freeze_by_normalized[normalized]
        if image_version != version:
            problems.append(f"version mismatch: {name} lock {version} image {image_version}")

    for normalized, (name, version) in freeze_by_normalized.items():
        if normalized in accounted_for or normalized in allowed_extra_normalized:
            continue
        problems.append(f"extra in image: {name}=={version}")

    return sorted(problems)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image_lock_consistency",
        description="Verify the shipped image's installed packages match uv.lock.",
    )
    parser.add_argument(
        "--dump-environment",
        action="store_true",
        help="Print the PEP 508 marker environment as JSON (stdlib only; run inside the image).",
    )
    parser.add_argument("--locked", help="Path to a `uv export --locked` requirements-txt file.")
    parser.add_argument("--freeze", help="Path to a `pip freeze --all --exclude triggarr` output file.")
    parser.add_argument("--environment", help="Path to a JSON file produced by --dump-environment.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.dump_environment:
        print(json.dumps(dump_environment(), sort_keys=True))
        return 0

    missing = [
        flag
        for flag, value in (("--locked", args.locked), ("--freeze", args.freeze), ("--environment", args.environment))
        if not value
    ]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")

    locked = parse_locked(Path(args.locked).read_text())
    freeze = parse_freeze(Path(args.freeze).read_text())
    environment = json.loads(Path(args.environment).read_text())

    problems = compare(locked, freeze, environment)
    if problems:
        for problem in problems:
            print(problem)
        return 1

    print("Image dependencies match uv.lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
