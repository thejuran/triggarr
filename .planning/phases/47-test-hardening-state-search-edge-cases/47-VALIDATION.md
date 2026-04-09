---
phase: 47
slug: test-hardening-state-search-edge-cases
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 47-01-01 | 01 | 1 | STATE-01 | — | N/A | unit | `uv run pytest tests/test_config.py -x -q -k "broken_toml or missing_field or wrong_type"` | ❌ W0 | ⬜ pending |
| 47-01-02 | 01 | 1 | STATE-02 | — | N/A | unit | `uv run pytest tests/test_db.py -x -q -k "corrupt or locked or schema_mismatch"` | ❌ W0 | ⬜ pending |
| 47-01-03 | 01 | 1 | STATE-03 | — | N/A | unit | `uv run pytest tests/test_state.py -x -q -k "truncated or wrong_structure or empty_file"` | Partial | ⬜ pending |
| 47-01-04 | 01 | 1 | STATE-04 | — | N/A | unit | `uv run pytest tests/test_config.py -x -q -k "migration or partial or unknown_field"` | ❌ W0 | ⬜ pending |
| 47-02-01 | 02 | 1 | SRCH-01 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "empty_queue or empty_wanted"` | Partial | ⬜ pending |
| 47-02-02 | 02 | 1 | SRCH-02 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "all_filtered or tag_filter_all"` | ❌ W0 | ⬜ pending |
| 47-02-03 | 02 | 1 | SRCH-03 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "nonexistent_tag or tag_resolution"` | Partial | ⬜ pending |
| 47-02-04 | 02 | 1 | SRCH-04, SRCH-05 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "batch_larger or cursor_past"` | ✅ | ⬜ pending |

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
