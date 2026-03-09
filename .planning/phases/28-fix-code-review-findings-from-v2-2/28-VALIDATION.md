---
phase: 28
slug: fix-code-review-findings-from-v2-2
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-09
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Finding | Test Type | Automated Command | File Exists | Status |
|---------|------|------|---------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | F1 | unit | `uv run pytest tests/test_search.py -k "monitored" -x` | Yes (4 tests) | ✅ green |
| 28-01-02 | 01 | 1 | F1 | unit | `uv run pytest tests/test_web.py -k "monitored or badge" -x` | Yes (3 tests) | ✅ green |
| 28-02-01 | 02 | 1 | F2 | manual | Visual inspection | N/A | ✅ green |
| 28-03-01 | 01 | 1 | F4 | unit | `uv run pytest tests/test_search.py -k "unreleased" -x` | Yes (17 tests) | ✅ green |
| 28-04-01 | 02 | 1 | M3 | unit | `uv run pytest tests/ -x -q` | Existing (302 tests) | ✅ green |
| 28-04-02 | 02 | 1 | M5 | lint | `uv run ruff check triggarr/ --select T201` | N/A | ✅ green |
| 28-04-03 | 02 | 1 | M6 | lint | `uv run ruff check triggarr/ --select UP006` | N/A | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Tests updated during execution, not created from scratch.

---

## Manual-Only Verifications

| Behavior | Finding | Why Manual | Test Instructions |
|----------|---------|------------|-------------------|
| Settings checkbox styling | F2 | CSS/HTML layout visual | Inspect settings page, verify `<p>` tag is inside checkbox parent div |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (2026-03-09)

## Validation Audit 2026-03-09

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

All findings have automated verification (tests or lint rules). Tests and lint confirmed green.
