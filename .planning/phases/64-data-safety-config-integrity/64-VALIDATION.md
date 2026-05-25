---
phase: 64
slug: data-safety-config-integrity
status: opted-out
nyquist_compliant: n/a
wave_0_complete: true
created: 2026-05-25
---

# Phase 64 — Validation Strategy

> **Nyquist opt-out:** This phase is correctness/safety hardening, not behavioral validation.
> See RESEARCH.md §Validation Architecture (lines 692-696) for rationale.

---

## Nyquist Applicability — N/A

All five success criteria are **deterministic invariants**, not sampled behaviors:

| Criterion | Invariant | Why Nyquist doesn't apply |
|-----------|-----------|---------------------------|
| SAFETY-01 | Resolved-row count ≤ `max_history_rows` after every insert | Single-shot pytest assertion (count rows after 2× max inserts). No timing/sampling. |
| SAFETY-04 | OSError on `os.replace` is logged before re-raise | Single-shot mock + log capture. No sampling rate. |
| SAFETY-05 | Two concurrent PUTs serialize via `search_lock` | `asyncio.gather` + spy on lock acquire order. Boolean pass/fail. |
| TEST-02 | Corrupted TOML at startup produces a friendly log line + exit code 1 | Subprocess + stderr/log assertion. Single-shot. |
| TEST-03 | Concurrent config-save test passes under pytest | Test exists or doesn't. Boolean. |

There is no "behavior at frequency F that must be sampled at 2F" because nothing in this phase is time-varying or stochastic. Standard pytest assertions cover every success criterion deterministically.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (pytest-asyncio with `asyncio_mode = auto`) |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Per-Plan Verification Map

| Plan | Wave | Reqs | Test File | Test Name(s) | Status |
|------|------|------|-----------|--------------|--------|
| 64-01 | 1 | SAFETY-04 | `tests/test_config.py` | `test_atomic_write_logs_oserror_on_replace_failure`, `test_atomic_write_suppresses_filenotfound_on_cleanup`, `test_atomic_write_logs_oserror_on_cleanup_other` | ⬜ pending |
| 64-02 | 2 | TEST-02 | `tests/test_config.py`, `tests/test_startup.py` | `test_corrupt_toml_friendly_error_syntax`, `test_corrupt_toml_friendly_error_utf8`, `test_corrupt_toml_mentions_backup_path_when_present` | ⬜ pending |
| 64-03 | 1 | SAFETY-05, TEST-03 | `tests/test_web.py` | `test_concurrent_config_save_lock_serializes` | ⬜ pending |
| 64-04 | 1 | SAFETY-01 | `tests/test_db.py` | `test_insert_prunes_old_entries` (existing, verify), `test_history_bounded_under_soak` (new) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None — existing test infrastructure (`tests/conftest.py`, `tests/test_web.py` fixture, `tests/test_config.py` patterns, `tests/test_startup.py` loguru-capture pattern) covers all phase requirements.

---

## Manual-Only Verifications

None — all phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] Nyquist opt-out documented and justified (correctness invariants, not behavioral sampling)
- [x] All tasks have `<acceptance_criteria>` with concrete pytest invocations or source/behavior assertions
- [x] Wave 0 covers all MISSING references (none required)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (full suite)
- [x] `nyquist_compliant: n/a` set in frontmatter with rationale above

**Approval:** approved 2026-05-25 (opt-out per RESEARCH.md §Validation Architecture)
