"""Tests for the image/lockfile consistency checker (CIMAINT-01).

``.github/scripts/image_lock_consistency.py`` intentionally lives outside
any Python package -- CI invokes it directly (``python
image_lock_consistency.py --dump-environment`` runs *inside* the bare
production image, where only the stdlib is available), so this test
module imports it by file path via ``importlib`` rather than a normal
package import.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "image_lock_consistency.py"

_spec = importlib.util.spec_from_file_location("image_lock_consistency", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
image_lock_consistency = importlib.util.module_from_spec(_spec)
sys.modules["image_lock_consistency"] = image_lock_consistency
_spec.loader.exec_module(image_lock_consistency)

normalize_name = image_lock_consistency.normalize_name
parse_locked = image_lock_consistency.parse_locked
parse_freeze = image_lock_consistency.parse_freeze
dump_environment = image_lock_consistency.dump_environment
compare = image_lock_consistency.compare
main = image_lock_consistency.main

# A full, deliberately Linux-flavored marker environment so tests never
# depend on the host this suite happens to run on (CI is Linux; local dev
# may be macOS).
LINUX_ENV = {
    "implementation_name": "cpython",
    "implementation_version": "3.13.0",
    "os_name": "posix",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "platform_release": "6.1.0",
    "platform_system": "Linux",
    "platform_version": "#1 SMP",
    "python_full_version": "3.13.0",
    "python_version": "3.13",
    "sys_platform": "linux",
}


def test_match_with_marker_skip_and_pip_allowlisted():
    locked = [("a", "1", None), ("b", "2", None), ("colorama", "0.4.6", "sys_platform == 'win32'")]
    freeze = {"a": "1", "b": "2", "pip": "25"}
    assert compare(locked, freeze, LINUX_ENV) == []


def test_missing_from_image():
    locked = [("a", "1", None), ("b", "2", None)]
    freeze = {"a": "1", "pip": "25"}
    assert compare(locked, freeze, LINUX_ENV) == ["missing from image: b==2"]


def test_version_mismatch():
    locked = [("a", "1", None), ("b", "2", None)]
    freeze = {"a": "1", "b": "3", "pip": "25"}
    assert compare(locked, freeze, LINUX_ENV) == ["version mismatch: b lock 2 image 3"]


def test_extra_in_image():
    locked = [("a", "1", None)]
    freeze = {"a": "1", "c": "1", "pip": "25"}
    assert compare(locked, freeze, LINUX_ENV) == ["extra in image: c==1"]


def test_name_normalization_matches_across_separator_and_case_styles():
    locked = [("Typing_Extensions", "4", None)]
    freeze = {"typing-extensions": "4"}
    assert compare(locked, freeze, LINUX_ENV) == []
    assert normalize_name("Typing_Extensions") == normalize_name("typing-extensions")


def test_parse_locked_joins_hash_continuations_and_ignores_via_comments():
    text = (
        "anyio==4.11.0 \\\n"
        "    --hash=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \\\n"
        "    --hash=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
        "    # via\n"
        "    #   httpx\n"
        "    #   starlette\n"
    )
    assert parse_locked(text) == [("anyio", "4.11.0", None)]


def test_parse_locked_preserves_marker_without_hashes():
    text = "colorama==0.4.6 ; sys_platform == 'win32'\n    # via loguru\n"
    assert parse_locked(text) == [("colorama", "0.4.6", "sys_platform == 'win32'")]


def test_parse_locked_rejects_non_exact_pin():
    with pytest.raises(ValueError, match="not an exact pin"):
        parse_locked("a>=1\n")


def test_parse_freeze_parses_simple_lines():
    assert parse_freeze("a==1\nb==2\n# a comment\n\n") == {"a": "1", "b": "2"}


def test_parse_freeze_rejects_unsupported_line():
    with pytest.raises(ValueError, match="unsupported freeze line"):
        parse_freeze("a @ file:///x\n")


def test_dump_environment_keys_are_stdlib_only():
    env = dump_environment()
    expected_keys = {
        "implementation_name",
        "implementation_version",
        "os_name",
        "platform_machine",
        "platform_python_implementation",
        "platform_release",
        "platform_system",
        "platform_version",
        "python_full_version",
        "python_version",
        "sys_platform",
    }
    assert set(env.keys()) == expected_keys
    assert all(isinstance(value, str) for value in env.values())


def test_compare_never_imports_packaging_at_module_level():
    """--dump-environment must run inside the bare image (stdlib only)."""
    source = SCRIPT_PATH.read_text()
    for line in source.splitlines():
        assert not line.startswith("import packaging")
        assert not line.startswith("from packaging")


def test_main_cli_reports_mismatch_then_match(tmp_path):
    locked_path = tmp_path / "locked.txt"
    locked_path.write_text("a==1\nb==2\n")
    env_path = tmp_path / "env.json"
    env_path.write_text(json.dumps(LINUX_ENV))

    freeze_mismatch = tmp_path / "freeze_mismatch.txt"
    freeze_mismatch.write_text("a==1\nb==3\npip==25\n")
    exit_code = main(
        ["--locked", str(locked_path), "--freeze", str(freeze_mismatch), "--environment", str(env_path)]
    )
    assert exit_code == 1

    freeze_match = tmp_path / "freeze_match.txt"
    freeze_match.write_text("a==1\nb==2\npip==25\n")
    exit_code = main(["--locked", str(locked_path), "--freeze", str(freeze_match), "--environment", str(env_path)])
    assert exit_code == 0


def test_main_cli_prints_problems_and_match_message(tmp_path, capsys):
    locked_path = tmp_path / "locked.txt"
    locked_path.write_text("a==1\nb==2\n")
    env_path = tmp_path / "env.json"
    env_path.write_text(json.dumps(LINUX_ENV))

    freeze_mismatch = tmp_path / "freeze_mismatch.txt"
    freeze_mismatch.write_text("a==1\nb==3\npip==25\n")
    main(["--locked", str(locked_path), "--freeze", str(freeze_mismatch), "--environment", str(env_path)])
    out = capsys.readouterr().out
    assert "version mismatch: b lock 2 image 3" in out

    freeze_match = tmp_path / "freeze_match.txt"
    freeze_match.write_text("a==1\nb==2\npip==25\n")
    main(["--locked", str(locked_path), "--freeze", str(freeze_match), "--environment", str(env_path)])
    out = capsys.readouterr().out
    assert "Image dependencies match uv.lock" in out


def test_main_dump_environment_prints_json(capsys):
    exit_code = main(["--dump-environment"])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "sys_platform" in parsed
