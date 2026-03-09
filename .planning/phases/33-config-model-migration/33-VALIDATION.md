---
phase: 33
slug: config-model-migration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_config.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_config.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 01 | 1 | INST-01 | unit | `uv run pytest tests/test_config.py -x -q -k "multi_instance_radarr"` | ❌ W0 | ⬜ pending |
| 33-01-02 | 01 | 1 | INST-02 | unit | `uv run pytest tests/test_config.py -x -q -k "multi_instance_sonarr"` | ❌ W0 | ⬜ pending |
| 33-01-03 | 01 | 1 | INST-01/02 | unit | `uv run pytest tests/test_config.py -x -q -k "max_instances"` | ❌ W0 | ⬜ pending |
| 33-01-04 | 01 | 1 | INST-01/02 | unit | `uv run pytest tests/test_config.py -x -q -k "duplicate_name"` | ❌ W0 | ⬜ pending |
| 33-02-01 | 02 | 1 | INST-04 | unit | `uv run pytest tests/test_config.py -x -q -k "detect_v22"` | ❌ W0 | ⬜ pending |
| 33-02-02 | 02 | 1 | INST-04 | unit | `uv run pytest tests/test_config.py -x -q -k "migrate_v22"` | ❌ W0 | ⬜ pending |
| 33-02-03 | 02 | 1 | INST-04 | unit | `uv run pytest tests/test_config.py -x -q -k "backup"` | ❌ W0 | ⬜ pending |
| 33-02-04 | 02 | 1 | INST-04 | unit | `uv run pytest tests/test_config.py -x -q -k "no_remigrate"` | ❌ W0 | ⬜ pending |
| 33-03-01 | 03 | 1 | INST-01/02 | unit | `uv run pytest tests/test_config.py -x -q -k "toml_roundtrip"` | ❌ W0 | ⬜ pending |
| 33-03-02 | 03 | 1 | INST-01/02 | unit | `uv run pytest tests/test_config.py -x -q -k "secret"` | ✅ partial | ⬜ pending |
| 33-03-03 | 03 | 1 | INST-01/02 | unit | `uv run pytest tests/test_config.py -x -q -k "has_enabled"` | ✅ needs update | ⬜ pending |
| 33-03-04 | 03 | 1 | INST-01/02 | unit | `uv run pytest tests/test_config.py -x -q -k "default_config"` | ✅ needs update | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — new test functions for multi-instance model validation (INST-01, INST-02)
- [ ] `tests/test_config.py` — new test functions for v2.2 detection and migration (INST-04)
- [ ] `tests/test_config.py` — update existing tests for new model shape
- [ ] `tests/conftest.py` — update `make_settings()` for new model shape

*Existing infrastructure covers framework needs; only new test stubs required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| v2.2 config backup file created on disk | INST-04 | Filesystem side-effect in real startup | 1. Place v2.2 config.toml 2. Start app 3. Verify .bak file exists |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
