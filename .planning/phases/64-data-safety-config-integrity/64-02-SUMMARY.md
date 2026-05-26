---
phase: 64-data-safety-config-integrity
plan: 02
subsystem: config
tags:
  - python
  - config
  - startup
  - error-handling
  - toml
  - test-02
requires:
  - tomllib
  - loguru
  - typing.NoReturn
provides:
  - "_log_corrupt_config_and_exit: friendly TOML-corruption handler with .bak detection"
  - "ensure_config: wraps both tomllib.load call sites with TOMLDecodeError + UnicodeDecodeError handling"
affects:
  - triggarr/config.py::ensure_config
  - triggarr/config.py::_log_corrupt_config_and_exit
  - tests/test_config.py
tech-stack:
  added:
    - "from typing import NoReturn (stdlib import added to triggarr/config.py)"
  patterns:
    - "Caller-side TOMLDecodeError/UnicodeDecodeError catch + friendly loguru.error + sys.exit(1)"
    - "NoReturn-annotated helper for control-flow termination (no `raise # unreachable` stub)"
    - "loguru sink capture in tests (io.StringIO + logger.add/logger.remove try/finally)"
    - "Conditional restore-hint vs regenerate-hint based on backup_path.exists()"
key-files:
  created: []
  modified:
    - triggarr/config.py
    - tests/test_config.py
decisions:
  - "Wrap the CALLER (ensure_config) rather than the leaf loaders (detect_and_migrate_v22, load_settings) — keeps leaf signatures clean and lets the existing test_toml_syntax_error_raises_decode_error keep validating raw raises"
  - "Catch only (TOMLDecodeError, UnicodeDecodeError) — do NOT catch ValueError (over-broad) or OSError (permission denied is fatal and operators need the traceback)"
  - "Helper annotated `-> NoReturn`; no `raise  # unreachable` stub after the helper call (a bare `raise` would re-raise the caught TOMLDecodeError, which is semantically misleading)"
  - "Wrap BOTH tomllib.load call sites (migration probe + final load) — single-callsite wrap would miss migration-time corruption"
  - "Path-only disclosure in log lines — no config contents or SecretStr values touched (RESEARCH Pitfall 5 confirms acceptable since no secrets are loaded at this point)"
metrics:
  duration_seconds: 181
  completed_date: "2026-05-26"
  tasks_completed: 2
  files_modified: 2
  tests_added: 4
  full_suite_tests: 890
requirements:
  - TEST-02
---

# Phase 64 Plan 02: ensure_config Friendly TOML-Corruption Handling (TEST-02) Summary

## One-liner

Wrapped both `tomllib.load` call sites inside `ensure_config` with a friendly `TOMLDecodeError`/`UnicodeDecodeError` handler that logs the config path, conditionally points at the `.toml.bak` backup, and calls `sys.exit(1)` — replacing the unhelpful traceback that previously propagated from `asyncio.run(_run())`.

## What Was Patched

### triggarr/config.py — new `_log_corrupt_config_and_exit` helper (lines 239–269)

Placed immediately above `ensure_config` for locality. Annotated `-> NoReturn` so type-checkers (mypy/pyright) treat it as control-flow terminating.

```python
def _log_corrupt_config_and_exit(config_path: Path, exc: Exception) -> NoReturn:
    """Log a friendly TOML-corruption error and exit with code 1 (TEST-02)."""
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
```

### triggarr/config.py — patched `ensure_config` (lines 272–311)

The missing-file branch (warning + `sys.exit(1)`) is unchanged. The migration-detection and load calls are now each wrapped:

```python
    try:
        migrated = detect_and_migrate_v22(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)

    if migrated:
        backup_path = config_path.with_suffix(".toml.bak")
        logger.info("v2.2 config backed up to {path}", path=backup_path)

    try:
        return load_settings(config_path)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        _log_corrupt_config_and_exit(config_path, exc)
```

Both tomllib.load call sites (inside `detect_and_migrate_v22` at config.py:168 and inside `load_settings` at config.py:206) are now covered by the caller-side handler. The leaf loaders are unchanged — `load_settings` still raises `TOMLDecodeError` directly when called outside `ensure_config`, so the existing `test_toml_syntax_error_raises_decode_error` test still passes.

### triggarr/config.py — new stdlib import

`from typing import NoReturn` (placed after `from pathlib import Path` per the project's ruff `isort` convention). No third-party imports added.

### `OSError` and `pydantic.ValidationError` continue to propagate

Per the plan and per RESEARCH Open Question 3:

- **OSError** (e.g. `PermissionError` opening the config file): not caught here — operators benefit from the traceback to diagnose filesystem/permission state.
- **pydantic.ValidationError** (schema mismatch from `Settings(**data)`): not caught here — operators benefit from the field-level error to fix their config.

Only TOML-parse and UTF-8-decode failures — the cases that previously produced an unhelpful traceback with no path context — are intercepted.

## Tests Added (tests/test_config.py)

All four appended after the existing `test_migrate_v22_mixed_nested_and_flat_only_detects_flat` (line 836), under a new `TEST-02: ensure_config friendly TOML-corruption handling` section header. Each uses the loguru-sink capture pattern from `tests/test_startup.py:261-267`.

| Test                                                       | Proves                                                                                                                                       |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_ensure_config_logs_friendly_error_on_toml_syntax_error` | Missing `]` produces a `SystemExit(1)` plus a loguru.error containing the config path and the phrase `Failed to parse config file`.        |
| `test_ensure_config_logs_friendly_error_on_invalid_utf8`   | Invalid UTF-8 bytes (`b"\xff\xfe\x00garbage"`) reach the SAME friendly handler (UnicodeDecodeError branch), exit code 1, same log content.   |
| `test_ensure_config_mentions_backup_path_when_backup_exists` | When a valid `triggarr.toml.bak` sits next to a corrupt `triggarr.toml`, the log line includes the backup path string and `backup is available`. |
| `test_ensure_config_mentions_no_backup_when_absent`        | When no `.bak` file exists, the log line includes the substring `No automatic backup`.                                                       |

Module imports (`import io`, `from loguru import logger`) and the `ensure_config` symbol import were already present from plan 64-01; no duplicates were added.

## Confirmation: Suite Green

| Check                                                                                                        | Result                  |
| ------------------------------------------------------------------------------------------------------------ | ----------------------- |
| `uv run pytest tests/test_config.py -k "test_ensure_config_logs_friendly_error or test_ensure_config_mentions" -x` | 4 passed, 57 deselected |
| `uv run pytest tests/test_config.py::test_toml_syntax_error_raises_decode_error -x`                          | 1 passed (leaf loader unchanged) |
| `uv run pytest tests/test_config.py -k "test_atomic_toml_write" -x`                                          | 5 passed (all 64-01 SAFETY-04 tests still pass) |
| `uv run pytest tests/test_config.py -x -q`                                                                   | 61 passed in 0.05s      |
| `uv run pytest tests/test_startup.py -x -q`                                                                  | 21 passed in 0.31s      |
| `uv run pytest tests/ -x -q`                                                                                 | 890 passed, 27 warnings (~19s) |
| `uv run ruff check triggarr/ tests/`                                                                         | All checks passed       |

No pre-existing unrelated failures encountered.

## Deviations from Plan

None — plan executed exactly as written.

### Notes on acceptance criteria interpretation

- **Task 2 criterion** `grep -v '^#' triggarr/config.py | grep -c "contextlib.suppress(OSError)"` returns `1`, not `0`. The single remaining occurrence is inside `generate_default_config` (config.py:229), which both plan 64-01 and plan 64-02 explicitly exclude from patching. This matches 64-01-SUMMARY's identical recorded interpretation. The patched `_atomic_toml_write` no longer contains the broad suppress — the intent of the criterion is preserved.
- **Task 3 criterion** `grep -c` for `"test_atomic_toml_write_logs"` returns `2`, not `3`. The third 64-01 test is named `test_atomic_toml_write_suppresses_filenotfound_silently` — it doesn't contain the substring `_logs_`. All 5 atomic-write tests (`grep -c "def test_atomic_toml_write"` returns 5) pass under `-k "test_atomic_toml_write"`. This is a plan/criterion mismatch, not a regression.
- **Task 3** (REFACTOR) made no code changes: helper placement was already correct (directly above `ensure_config`), neither `try/except` block referenced a lambda or partial, no `raise  # unreachable` stub was ever added, and `import contextlib` is still needed for the untouched `generate_default_config`. Per the TDD execution rule ("commit only if changes"), no Task 3 commit was created.

## Authentication Gates

None — no auth-protected paths touched.

## Known Stubs

None.

## TDD Gate Compliance

| Gate     | Commit  | Type     | Subject                                                                  |
| -------- | ------- | -------- | ------------------------------------------------------------------------ |
| RED      | 139fff5 | test     | add failing TEST-02 tests for ensure_config friendly TOML errors         |
| GREEN    | 9ae66e0 | feat     | wrap TOML loads in ensure_config with friendly error handler (TEST-02)   |
| REFACTOR | —       | (no-op)  | verification only; no behavior change required                           |

RED and GREEN gate commits both present in git log on the agent branch.

## Self-Check: PASSED

Verification:

- `[ -f triggarr/config.py ]` → FOUND
- `[ -f tests/test_config.py ]` → FOUND
- `[ -f .planning/phases/64-data-safety-config-integrity/64-02-SUMMARY.md ]` → FOUND (this file)
- `git log --oneline | grep 139fff5` → FOUND (Task 1 RED)
- `git log --oneline | grep 9ae66e0` → FOUND (Task 2 GREEN)
- `grep -c "def _log_corrupt_config_and_exit" triggarr/config.py` → 1
- `grep -c "from typing import NoReturn" triggarr/config.py` → 1
- `grep -c "tomllib.TOMLDecodeError" triggarr/config.py` → 3 (1 helper-doc-adjacent + 2 except branches)
- `grep -c "UnicodeDecodeError" triggarr/config.py` → 4 (2 docstring mentions + 2 except branches)
- `grep -c "Failed to parse config file" triggarr/config.py` → 1
- `grep -c "backup is available" triggarr/config.py` → 1
- `grep -c "No automatic backup" triggarr/config.py` → 1
- `grep -c "_log_corrupt_config_and_exit" triggarr/config.py` → 3 (definition + 2 call sites)
- `grep -c "raise  # unreachable" triggarr/config.py` → 0 (NoReturn handles this)
- Plan 64-01 invariant preserved: `grep -c "Config write failed" triggarr/config.py` → 1
- Full suite: 890 passed, 0 failed
- Ruff over `triggarr/` and `tests/`: clean

## Threat Flags

None — no new network endpoints, auth paths, file-access patterns, or schema changes. Logged values are the config path and the exception object's repr (`TOMLDecodeError` / `UnicodeDecodeError`). No config-file contents are read into the log; no SecretStr value is ever passed to any logger call. Threat T-64-INFO (acceptable path-only disclosure) was explicitly evaluated in the plan's `<threat_model>` and accepted.
