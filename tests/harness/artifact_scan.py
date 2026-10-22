"""Byte-scanning extra defence for browser-suite CI artifacts (D-27).

:func:`scrub` walks every file under a directory (including each member of
any ``.zip`` archive) looking for a registry of sensitive values --
disposable test credentials, session cookie values, a run's setup/stub API
keys -- in raw, URL-encoded and base64-encoded form (traces and HAR files
may store either). Any file that matches, or any ``.zip`` that cannot be
safely read, is deleted before ``scan-complete.json`` is written, so no
sensitive value can survive to be uploaded as a CI artifact.

This module is stdlib-only (``zipfile``, ``base64``, ``urllib.parse``,
``json``) plus loguru, per the module's own CISHIP-02 constraints.

This is an extra defence for text/binary artifacts only. It is **not**
proof that screenshots are safe: a credential rendered as pixels cannot be
found by byte-matching a string. Screenshot/trace/video safety for
credential-rendering pages comes from the capture-policy guard in
``tests/e2e/conftest.py`` (D-33), not from this scanner.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

MIN_SENSITIVE_VALUE_LENGTH = 8
WITHHELD_REASON = "contains sensitive value"


@dataclass
class ScanReport:
    """Outcome of one :func:`scrub` run."""

    scanned: int
    withheld: list[str] = field(default_factory=list)


def _encoded_forms(value: str) -> list[bytes]:
    """Return the raw, URL-encoded and base64-encoded byte forms of a sensitive value."""
    raw = value.encode("utf-8")
    forms = [raw, urllib.parse.quote(value, safe="").encode("ascii"), base64.b64encode(raw)]
    # De-duplicate while preserving order (short/simple values can coincide across forms).
    seen: set[bytes] = set()
    unique: list[bytes] = []
    for form in forms:
        if form not in seen:
            seen.add(form)
            unique.append(form)
    return unique


def _contains_any(data: bytes, needles: list[bytes]) -> bool:
    return any(needle in data for needle in needles)


def _read_file(path: Path) -> bytes:
    """Read a regular (non-zip) file's full contents. Isolated for test injection."""
    return path.read_bytes()


def _zip_contains(path: Path, needles: list[bytes]) -> bool:
    """Return True if any member of the zip matches a needle.

    Fails closed: a corrupt zip, or any member that cannot be read, counts
    as a match (withheld) rather than being silently skipped.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                try:
                    data = zf.read(name)
                except Exception:
                    return True
                if _contains_any(data, needles):
                    return True
    except zipfile.BadZipFile:
        return True
    return False


def _file_matches(path: Path, needles: list[bytes]) -> bool:
    if path.suffix == ".zip":
        return _zip_contains(path, needles)
    return _contains_any(_read_file(path), needles)


def scrub(output_dir: Path | str, sensitive_values: Iterable[str]) -> ScanReport:
    """Remove every file under ``output_dir`` that contains any ``sensitive_values``.

    Writes ``withheld.txt`` (withheld relative paths plus a fixed reason,
    never the value itself) and then ``scan-complete.json`` (scan counts),
    in that order. ``scan-complete.json`` is written only if the scan
    completes without raising -- a mid-scan exception (including a value
    under :data:`MIN_SENSITIVE_VALUE_LENGTH` chars) leaves no completion
    marker behind.

    Raises:
        ValueError: if any sensitive value is shorter than
            :data:`MIN_SENSITIVE_VALUE_LENGTH` characters -- a trivial value
            could wipe every artifact or give false confidence that a scan
            actually checked for something meaningful.
    """
    values = list(sensitive_values)
    for value in values:
        if len(value) < MIN_SENSITIVE_VALUE_LENGTH:
            raise ValueError(
                f"sensitive value is too short to scan safely (min {MIN_SENSITIVE_VALUE_LENGTH} chars)"
            )

    needles: list[bytes] = []
    for value in values:
        needles.extend(_encoded_forms(value))

    output_path = Path(output_dir)
    scanned = 0
    withheld: list[str] = []

    if output_path.is_dir():
        for path in sorted(output_path.rglob("*")):
            if not path.is_file():
                continue
            scanned += 1
            rel = path.relative_to(output_path).as_posix()
            if _file_matches(path, needles):
                withheld.append(rel)
                path.unlink()

    output_path.mkdir(parents=True, exist_ok=True)

    withheld_lines = [f"{rel}: {WITHHELD_REASON}" for rel in withheld]
    (output_path / "withheld.txt").write_text("\n".join(withheld_lines) + ("\n" if withheld_lines else ""))

    report = ScanReport(scanned=scanned, withheld=withheld)
    (output_path / "scan-complete.json").write_text(
        json.dumps({"scanned": report.scanned, "withheld": report.withheld}, indent=2) + "\n"
    )

    if withheld:
        logger.warning(
            "artifact_scan: withheld {count} artifact(s) containing a sensitive value: {paths}",
            count=len(withheld),
            paths=withheld,
        )
    else:
        logger.debug("artifact_scan: scanned {count} artifact(s), none withheld", count=scanned)

    return report
