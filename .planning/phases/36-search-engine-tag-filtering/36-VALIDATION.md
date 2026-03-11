---
phase: 36
slug: search-engine-tag-filtering
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 36-01-01 | 01 | 1 | TAG-01, TAG-02, TAG-03 | unit | `uv run pytest tests/test_config.py -x -q -k "tag"` | ✅ | ⬜ pending |
| 36-01-02 | 01 | 1 | TAG-01, TAG-02, TAG-03 | unit | `uv run pytest tests/test_search.py -x -q -k "filter_by_tag"` | ❌ W0 | ⬜ pending |
| 36-02-01 | 02 | 1 | TAG-01, TAG-02 | unit | `uv run pytest tests/test_search.py -x -q -k "radarr_cycle" and "tag"` | ❌ W0 | ⬜ pending |
| 36-02-02 | 02 | 1 | TAG-01, TAG-02, TAG-03 | unit | `uv run pytest tests/test_search.py -x -q -k "sonarr_cycle" and "tag"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_search.py` — stubs for filter_by_tag, tag accessor, cycle integration tests
- [ ] `tests/test_config.py` — stubs for missing_tag/cutoff_tag field tests

*Existing infrastructure covers framework and fixture needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Default config template includes tag field comments | TAG-03 | Template formatting | Generate default config, verify commented-out tag examples present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
