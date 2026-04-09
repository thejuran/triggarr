---
phase: 47
slug: test-hardening-state-search-edge-cases
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-09
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | pyproject.toml (asyncio_mode = "auto") |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | STATE-01 | — | N/A | unit | `uv run pytest tests/test_config.py -x -q -k "syntax_error or both_search_counts_zero or wrong_type"` | ✅ | ✅ green |
| 47-01-02 | 01 | 1 | STATE-02 | — | N/A | unit | `uv run pytest tests/test_db.py -x -q -k "corrupt_file or locked_database or schema_version_on_empty"` | ✅ | ✅ green |
| 47-01-03 | 01 | 1 | STATE-03 | — | N/A | unit | `uv run pytest tests/test_state.py -x -q -k "truncated or wrong_structure or empty_file or wrong_nested"` | ✅ | ✅ green |
| 47-01-04 | 01 | 1 | STATE-04 | — | N/A | unit | `uv run pytest tests/test_config.py -x -q -k "partial_radarr_only or unknown_extra_fields or missing_general or mixed_nested"` | ✅ | ✅ green |
| 47-02-01 | 02 | 1 | SRCH-01 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "empty_queues"` | ✅ | ✅ green |
| 47-02-02 | 02 | 1 | SRCH-02 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "all_filtered_by_tag"` | ✅ | ✅ green |
| 47-02-03 | 02 | 1 | SRCH-03 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "lidarr_tag_resolution_failure"` | ✅ | ✅ green |
| 47-02-04 | 02 | 1 | SRCH-04, SRCH-05 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "batch_larger or cursor_past"` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

- No new test frameworks needed
- No new fixtures needed (conftest helpers, tmp_path all available)
- No new config needed

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-09

---

## Validation Audit 2026-04-09

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

All 8 task requirements verified against 21 implemented tests (14 in Plan 01, 7 in Plan 02). Full suite: 606 passed in 3.30s.
