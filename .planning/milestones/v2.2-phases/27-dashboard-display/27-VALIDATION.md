---
phase: 27
slug: dashboard-display
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-09
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_web.py tests/test_search.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_web.py tests/test_search.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 01 | 1 | DASH-01 | unit | `uv run pytest tests/test_search.py -k "eligible" -x` | Yes (3 tests) | ✅ green |
| 27-01-02 | 01 | 1 | DASH-01 | unit | `uv run pytest tests/test_web.py -k "eligible" -x` | Yes (3 tests) | ✅ green |
| 27-01-03 | 01 | 1 | DASH-02 | unit | `uv run pytest tests/test_web.py -k "skip" -x` | Yes (8 tests) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_search.py` — eligible count tracking tests
- [x] `tests/test_web.py` — eligible/total display and skip badge tests

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual appearance of amber skip badge | DASH-02 | CSS rendering | Run with Radarr instance with unreleased movies, verify badge styling |
| Real-time HTMX update after first cycle | DASH-01 | Live timing | Start fresh, watch dashboard through first cycle |

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

Reconstructed from SUMMARY.md and VERIFICATION.md artifacts. All requirements have automated verification. Tests confirmed green.
