---
phase: 25
slug: filter-foundation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-09
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_search.py tests/test_config.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_search.py tests/test_config.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 25-01-01 | 01 | 1 | CFG-02 | unit | `uv run pytest tests/test_config.py -x -q -k skip_unreleased` | Yes (3 tests) | ✅ green |
| 25-01-02 | 01 | 1 | FILT-01 | unit | `uv run pytest tests/test_search.py -x -q -k unreleased` | Yes (17 tests) | ✅ green |
| 25-01-03 | 01 | 1 | FILT-03 | unit | `uv run pytest tests/test_search.py -x -q -k null` | Yes (5 tests) | ✅ green |
| 25-01-04 | 01 | 1 | FILT-04 | unit | `uv run pytest tests/test_search.py -x -q -k unreleased` | Yes (17 tests) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Tests for `filter_unreleased_movies()` in `tests/test_search.py` -- covers FILT-01, FILT-03, FILT-04
- [x] Test for `skip_unreleased` config field persistence in `tests/test_config.py` -- covers CFG-02
- [x] No new framework or fixture needs -- existing `make_settings` and test infrastructure sufficient

*Existing infrastructure covers framework and fixtures.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (2026-03-09)

## Validation Audit 2026-03-09

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

All requirements have automated verification. Tests confirmed green.
