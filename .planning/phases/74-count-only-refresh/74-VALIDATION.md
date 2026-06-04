---
phase: 74
slug: count-only-refresh
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 74 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 74-RESEARCH.md "Validation Architecture". Planner refines the per-task map.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3+ with pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_refresh_counts.py tests/test_search.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~quick <10s / full ~60-90s |

---

## Sampling Rate

- **After every task commit:** Run the quick run command (new count tests + the cycle regression anchors).
- **After every plan wave:** Run the full suite command.
- **Before `/gsd:verify-work`:** Full suite must be green (984 baseline + new count tests).
- **Max feedback latency:** ~90 seconds (full suite).

---

## Per-Task Verification Map

> Requirement → behavior → automated command. The planner maps these onto concrete task IDs;
> all new tests live in `tests/test_refresh_counts.py`; `tests/test_search.py` is the
> behavior-preservation regression anchor (must stay green — CNT-01).

| Requirement | Behavior | Test Type | Automated Command | File |
|-------------|----------|-----------|-------------------|------|
| CNT-01 | Helper returns correct raw + eligible/searchable counts (Radarr/Sonarr/Lidarr) | unit | `uv run pytest tests/test_refresh_counts.py -k "returns_counts" -x` | W0 new |
| CNT-01 | Existing cycle behavior unchanged (cursor advance, last_run, search calls) | unit | `uv run pytest tests/test_search.py -x -q` | exists |
| CNT-02 | Cursor unchanged before/after helper call (structural) | unit | `uv run pytest tests/test_refresh_counts.py -k "cursor" -x` | W0 new |
| CNT-03 | Count path does NOT stamp `last_run`/`last_success` | unit | `uv run pytest tests/test_refresh_counts.py -k "last_run" -x` | W0 new |
| CNT-03 | Count path does NOT touch `app.state.search_failures` | integration | `uv run pytest tests/test_refresh_counts.py -k "failure_counter" -x` | W0 new |
| CNT-03 | Health updated (connected) on success | unit | `uv run pytest tests/test_refresh_counts.py -k "connected" -x` | W0 new |
| CNT-03 | Health flipped (disconnected) on fetch failure; scheduler NOT escalated | unit | `uv run pytest tests/test_refresh_counts.py -k "fetch_error" -x` | W0 new |
| CNT-04 | Endpoint happy path: 200 + app-card partial | integration | `uv run pytest tests/test_refresh_counts.py -k "happy_path" -x` | W0 new |
| CNT-04 | 400 on invalid app / instance name too long / not enabled | integration | `uv run pytest tests/test_refresh_counts.py -k "invalid" -x` | W0 new |
| CNT-04 | 429 on rate limit (sibling `last_refresh_time`) | integration | `uv run pytest tests/test_refresh_counts.py -k "rate_limited" -x` | W0 new |
| CNT-04 | DRSEC-03: in-lock re-check prevents concurrent bypass | integration | `uv run pytest tests/test_refresh_counts.py -k "concurrent" -x` | W0 new |
| CNT-05 | Connected card renders "Refresh counts" button | integration | `uv run pytest tests/test_refresh_counts.py -k "button" -x` | W0 new |
| CNT-05 | Disconnected card has NO "Refresh counts" button | integration | `uv run pytest tests/test_refresh_counts.py -k "disconnected" -x` | W0 new |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_refresh_counts.py` — new test module for the helpers + endpoint + UI button (CNT-01..05).
- [ ] Reuse existing fixtures in `tests/test_search.py` / `tests/test_web.py` (`test_app`, instance/state fixtures). The `test_app` fixture MUST gain `app.state.last_refresh_time = {}` alongside `last_search_time` or endpoint tests raise `AttributeError` (RESEARCH pitfall #4).
- [ ] No framework install needed — pytest + pytest-asyncio already configured.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| "Refresh counts" updates the card in place on a live deployed build without launching a search or advancing the cursor | CNT-05 / CNT-02 | Visual + live *arr interaction; covered by the milestone-end NAS walkthrough (design spec §5) | Click "Refresh counts" on an app card; confirm counts/health update, no search wave fires in *arr, and the next scheduled cycle resumes where it left off |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (new `tests/test_refresh_counts.py`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
