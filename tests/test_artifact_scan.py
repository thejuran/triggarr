"""Tests for tests/harness/artifact_scan.py -- the D-27 byte-scanning extra defence.

scrub() is an extra defence for text/binary CI artifacts only. It is not
proof that screenshots are safe -- pixels cannot be byte-searched; screenshot
safety for credential pages comes from the capture-policy guard in
tests/e2e/conftest.py (D-33), covered by Task 3.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tests.harness import artifact_scan

_SECRET = "s3cret-value"  # 12 chars, well above the 8-char floor


def test_scrub_removes_matching_files_keeps_clean_txt(tmp_path: Path):
    (tmp_path / "clean.txt").write_text("nothing sensitive here")
    (tmp_path / "shot.png").write_bytes(b"\x89PNG..." + _SECRET.encode() + b"...rest")
    zip_path = tmp_path / "trace.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("network.har", f"cookie={_SECRET}")

    report = artifact_scan.scrub(tmp_path, [_SECRET])

    assert sorted(report.withheld) == ["shot.png", "trace.zip"]
    assert (tmp_path / "clean.txt").exists()
    assert not (tmp_path / "shot.png").exists()
    assert not zip_path.exists()


def test_withheld_txt_lists_paths_with_reason_never_the_value(tmp_path: Path):
    (tmp_path / "shot.png").write_bytes(_SECRET.encode())

    artifact_scan.scrub(tmp_path, [_SECRET])

    withheld_text = (tmp_path / "withheld.txt").read_text()
    assert "shot.png" in withheld_text
    assert "contains sensitive value" in withheld_text
    assert _SECRET not in withheld_text


def test_scan_complete_written_last_with_counts(tmp_path: Path):
    (tmp_path / "clean.txt").write_text("fine")
    (tmp_path / "shot.png").write_bytes(_SECRET.encode())

    report = artifact_scan.scrub(tmp_path, [_SECRET])

    payload = json.loads((tmp_path / "scan-complete.json").read_text())
    assert payload["scanned"] == 2
    assert payload["withheld"] == ["shot.png"]
    assert report.scanned == 2
    assert report.withheld == ["shot.png"]


def test_scan_complete_not_written_if_scanning_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "good.txt").write_bytes(b"irrelevant content")

    def _boom(path: Path) -> bytes:
        raise OSError("simulated read failure")

    monkeypatch.setattr(artifact_scan, "_read_file", _boom)

    with pytest.raises(OSError):
        artifact_scan.scrub(tmp_path, [_SECRET])

    assert not (tmp_path / "scan-complete.json").exists()


def test_short_value_rejected_with_value_error(tmp_path: Path):
    with pytest.raises(ValueError):
        artifact_scan.scrub(tmp_path, ["short1"])  # 6 chars, below the 8-char floor
    assert not (tmp_path / "scan-complete.json").exists()


def test_matching_covers_url_encoded_and_base64_forms(tmp_path: Path):
    import base64
    import urllib.parse

    (tmp_path / "url-encoded.txt").write_text(f"value={urllib.parse.quote(_SECRET, safe='')}")
    (tmp_path / "base64-encoded.txt").write_text(base64.b64encode(_SECRET.encode()).decode())
    (tmp_path / "clean.txt").write_text("no match anywhere in here")

    report = artifact_scan.scrub(tmp_path, [_SECRET])

    assert sorted(report.withheld) == ["base64-encoded.txt", "url-encoded.txt"]
    assert (tmp_path / "clean.txt").exists()


def test_empty_dir_produces_scan_complete_with_scanned_zero(tmp_path: Path):
    report = artifact_scan.scrub(tmp_path, [_SECRET])

    assert report.scanned == 0
    assert report.withheld == []
    payload = json.loads((tmp_path / "scan-complete.json").read_text())
    assert payload["scanned"] == 0


def test_missing_dir_produces_scan_complete_with_scanned_zero(tmp_path: Path):
    missing = tmp_path / "does-not-exist-yet"

    report = artifact_scan.scrub(missing, [_SECRET])

    assert report.scanned == 0
    assert report.withheld == []
    payload = json.loads((missing / "scan-complete.json").read_text())
    assert payload["scanned"] == 0


def test_corrupt_zip_is_withheld_fail_closed(tmp_path: Path):
    corrupt = tmp_path / "corrupt.zip"
    corrupt.write_bytes(b"not actually a zip file at all")

    report = artifact_scan.scrub(tmp_path, [_SECRET])

    assert report.withheld == ["corrupt.zip"]
    assert not corrupt.exists()


def test_recursive_walk_withholds_match_in_nested_directory(tmp_path: Path):
    nested = tmp_path / "traces" / "failure-1"
    nested.mkdir(parents=True)
    (nested / "shot.png").write_bytes(_SECRET.encode())
    (tmp_path / "clean.txt").write_text("fine")

    report = artifact_scan.scrub(tmp_path, [_SECRET])

    assert report.withheld == ["traces/failure-1/shot.png"]
    assert not (nested / "shot.png").exists()
    assert (tmp_path / "clean.txt").exists()
