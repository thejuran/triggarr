---
phase: 90
slug: removed-instance-pending-search-lifecycle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-18
---

# Phase 90 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode=auto`), ruff |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_db.py tests/test_tracking.py tests/test_scheduler.py tests/test_activity_rail.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~5 seconds (quick), full suite longer |

TDD mode is on: each regression test is written first and must fail on the unfixed code (D-00a).

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_db.py tests/test_tracking.py tests/test_scheduler.py tests/test_activity_rail.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Before `/bm:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

Filled in by the planner/executor per task. Requirement-to-test map from research:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| RMINST-01 | Close-out turns pending rows of a stable ID into `instance_removed`; other IDs, resolved and Legacy rows untouched | unit (db) | `uv run pytest tests/test_db.py -k instance_removed -x` | new tests in existing file | ⬜ pending |
| RMINST-01 | `remove_instance` closes rows for all three apps; failing close-out still returns success and runs remaining tidy-up | integration | `uv run pytest tests/test_web.py -k remove_instance -x` | new tests | ⬜ pending |
| RMINST-01 | History badge/tooltip distinct from Legacy; filter option; activity rail pill | template/route | `uv run pytest tests/test_web.py tests/test_activity_rail.py -k instance_removed -x` | new tests | ⬜ pending |
| RMINST-02 | Closed rows excluded from cap, tracking, grab rate, historical flag | unit | `uv run pytest tests/test_db.py -k instance_removed -x` | new tests | ⬜ pending |
| RMINST-02 | Shared pending predicate with tested NULL handling; closed rows age out (D-08) | unit | `uv run pytest tests/test_db.py -k pending_predicate -x` | new tests | ⬜ pending |
| RMINST-03 | Sonarr/Radarr/Lidarr same-name reuse never selects or credits old rows | unit/integration | `uv run pytest tests/test_tracking.py -k name_reuse -x` | rewrite 5 existing + new | ⬜ pending |
| RMINST-03 | Radarr/Lidarr empty stable ID refuses to track | unit | `uv run pytest tests/test_tracking.py -k empty_stable_id -x` | new tests | ⬜ pending |
| RMINST-03 / D-09 | New same-name instance shows none of old stats | unit | `uv run pytest tests/test_db.py -k name_reuse_stats -x` | new tests | ⬜ pending |
| RMINST-04 | Startup sweep closes orphans; configured (incl. disabled) and Legacy rows untouched; idempotent | unit | `uv run pytest tests/test_db.py -k orphan_sweep -x` | new tests | ⬜ pending |
| RMINST-04 | Lifespan runs sweep after cutover, before scheduler; failure non-fatal | integration | `uv run pytest tests/test_scheduler.py -k "sweep or lifespan" -x` | new tests | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Helpers to reuse: `_insert_cutover` (`tests/test_db.py`), `_insert_entry` (`tests/test_tracking.py`), `multi_instance_app` fixture (`tests/test_web.py`), lifespan pattern `test_lifespan_records_attribution_cutover_once`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Badge reads clearly next to Legacy in a real browser | RMINST-01 | Visual judgment | Remove an instance with pending searches, open History, confirm "Instance removed" badge and tooltip |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
