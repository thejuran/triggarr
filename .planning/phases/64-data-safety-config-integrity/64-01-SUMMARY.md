---
phase: 64-data-safety-config-integrity
plan: 01
subsystem: config
tags:
  - python
  - config
  - atomic-write
  - error-handling
  - observability
  - safety-04
requires:
  - tomli_w
  - loguru
provides:
  - "_atomic_toml_write: discriminating OSError handler with observability"
affects:
  - triggarr/config.py::_atomic_toml_write
  - tests/test_config.py
tech-stack:
  added: []
  patterns:
    - "loguru kwargs idiom (logger.error('{name}', name=value))"
    - "try/except FileNotFoundError + except OSError as cleanup_exc cleanup pattern"
    - "loguru sink capture in tests (io.StringIO + logger.add/logger.remove try/finally)"
key-files:
  created: []
  modified:
    - triggarr/config.py
    - tests/test_config.py
decisions:
  - "Keep `import contextlib` — still used by generate_default_config (per plan: leave that function alone)"
  - "Do not extract `_cleanup_temp` helper — two short except branches are clearer than one helper plus two calls for code this size (per plan refactor guidance)"
  - "Test 2 (FileNotFoundError silent suppress) passes in RED phase already, because pre-patch code uses broad contextlib.suppress(OSError) which silences FNF the same way; the test now serves as a regression guard for the patched discriminating handler"
metrics:
  duration_seconds: 193
  completed_date: "2026-05-26"
  tasks_completed: 3
  files_modified: 2
  tests_added: 3
  full_suite_tests: 882
requirements:
  - SAFETY-04
---

# Phase 64 Plan 01: _atomic_toml_write OSError Observability (SAFETY-04) Summary

## One-liner

Hardened `_atomic_toml_write` so `os.replace` failures and non-`FileNotFoundError` cleanup failures emit structured loguru lines with the config path, while `FileNotFoundError` during temp cleanup remains silently suppressed.

## What Was Patched

### triggarr/config.py — `_atomic_toml_write` except region

**Before (config.py:113-115):**

```python
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
```

**After (config.py:116-141):**

```python
    except OSError as exc:
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
    except Exception:
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
```

- The `try:` body (lines 103-115 in the patched file: mkstemp + fdopen + tomli_w.dump + os.fsync + os.replace + dir fsync) is unchanged.
- The `finally: if dir_fd is not None: os.close(dir_fd)` block is unchanged.
- Docstring extended to mention SAFETY-04 invariants.
- `import contextlib` retained — still used by `generate_default_config` (line 229), which the plan explicitly excluded from this patch.

## Tests Added (tests/test_config.py)

All three appended after `test_atomic_toml_write_cleans_temp_on_failure` (line 680), under a new
`SAFETY-04: _atomic_toml_write OSError observability` section header.

| Test                                                  | Proves                                                                                                                 |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `test_atomic_toml_write_logs_cleanup_oserror`         | Non-`FileNotFoundError` `OSError` raised by `os.unlink` during cleanup is logged via `logger.error` with the exc text. |
| `test_atomic_toml_write_suppresses_filenotfound_silently` | `FileNotFoundError` during temp cleanup produces NO log line — regression guard for the discriminating handler.       |
| `test_atomic_toml_write_logs_os_replace_failure`      | `OSError` raised by `os.replace` is logged via `logger.error` with the config path and exc text, then re-raised.       |

All three use the loguru-sink capture pattern from `tests/test_startup.py:261-267` (io.StringIO sink, `logger.add` at level `ERROR`, `try/finally: logger.remove(handler_id)`).

New module imports added at the top of `tests/test_config.py`:
- `import io` (stdlib block)
- `from loguru import logger` (third-party block)

## Confirmation: Suite Green

| Check                                                                       | Result                  |
| --------------------------------------------------------------------------- | ----------------------- |
| `uv run pytest tests/test_config.py -k "test_atomic_toml_write" -x`         | 5 passed (1 succeeds-write + 1 existing cleanup + 3 new SAFETY-04) |
| `uv run pytest tests/test_web.py::test_save_settings_propagates_write_failure -x` | 1 passed (route still sees OSError → 500) |
| `uv run pytest tests/ -x -q`                                                | 882 passed, 27 warnings (~18.6s) |
| `uv run ruff check triggarr/ tests/`                                        | All checks passed       |
| Test idempotency (run config tests twice)                                   | Identical 57-passed output — no loguru sink leakage |

No pre-existing unrelated failures encountered.

## Deviations from Plan

None — plan executed exactly as written.

### Notes on acceptance criteria interpretation

- Task 2 acceptance criterion `grep -v '^#' triggarr/config.py | grep -c "contextlib.suppress(OSError)"` returns `1`, not `0`. The remaining occurrence is at config.py:229 inside `generate_default_config`, which the plan explicitly excluded from this patch ("Do not touch `generate_default_config`"). The patched `_atomic_toml_write` no longer contains the broad suppress — that intent is preserved.
- Task 3 (REFACTOR) made no code changes: the patched function already uses idiomatic loguru kwargs, the two-branch duplication is shorter than a helper would be, and `import contextlib` is still needed for the untouched `generate_default_config`. Per the TDD execution rule ("commit only if changes"), no Task 3 commit was created.

## Authentication Gates

None — no auth-protected paths touched.

## Known Stubs

None.

## TDD Gate Compliance

| Gate     | Commit  | Type     | Subject                                                                  |
| -------- | ------- | -------- | ------------------------------------------------------------------------ |
| RED      | 2943fb8 | test     | add failing SAFETY-04 tests for _atomic_toml_write OSError observability |
| GREEN    | 48ee522 | feat     | log OSError in _atomic_toml_write before re-raise (SAFETY-04)            |
| REFACTOR | —       | (no-op)  | verification only; no behavior change required                           |

RED and GREEN gate commits both present in git log on the agent branch.

## Self-Check: PASSED

Verification:

- `[ -f triggarr/config.py ]` → FOUND
- `[ -f tests/test_config.py ]` → FOUND
- `[ -f .planning/phases/64-data-safety-config-integrity/64-01-SUMMARY.md ]` → FOUND (this file)
- `git log --oneline | grep 2943fb8` → FOUND (Task 1 RED)
- `git log --oneline | grep 48ee522` → FOUND (Task 2 GREEN)
- `grep -c "Config write failed" triggarr/config.py` → 1
- `grep -c "Failed to clean up temp file" triggarr/config.py` → 2
- `grep -c "except FileNotFoundError:" triggarr/config.py` → 2 (one per except branch)
- `grep -c "^import io" tests/test_config.py` → 1
- `grep -c "^from loguru import logger" tests/test_config.py` → 1
- Full suite: 882 passed, 0 failed
- Ruff over `triggarr/` and `tests/`: clean

## Threat Flags

None — no new network endpoints, auth paths, file-access patterns, or schema changes were introduced. Logged values are the config path (operator-relevant per CLAUDE.md, no secret content) and the OSError message; no config dict or SecretStr value is passed to any logger call.
