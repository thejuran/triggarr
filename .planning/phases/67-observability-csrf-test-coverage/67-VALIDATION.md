---
phase: 67
slug: observability-csrf-test-coverage
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-31
---

# Phase 67 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~25–35 seconds for full suite (934 tests + ruff) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<scope>.py -x -q` (scoped to the touched test file — `test_middleware.py` for TEST-01, `test_search.py`/`test_state.py`/`test_scheduler.py` for RES-02/RES-03, `test_web.py` for the card render + cache invalidation)
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite green AND `uv run ruff check triggarr/ tests/` exits 0
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

Every task across the three plans maps to a requirement ID and an automated command. TDD tasks carry `<behavior>` blocks (RED→GREEN gate); the one execute task with a code-producing change (card render) asserts rendered HTML strings via TestClient.

| Plan | Task | Requirement | Type | Automated Command |
|------|------|-------------|------|-------------------|
| 67-01 | T1 — last_success field + engine write | RES-02 | tdd (unit) | `uv run pytest tests/test_state.py tests/test_search.py -k "last_success or round_trip or happy_path or network_failure" -x -q` |
| 67-01 | T2 — last_success_stale in _build_app_context | RES-02 | tdd (unit) | `uv run pytest tests/test_web.py -k "last_success or stale" -x -q` |
| 67-01 | T3 — "Last OK" + amber stale flag on card | RES-02 | execute (integration) | `uv run pytest tests/test_web.py -k "card or last_ok or last_success" -x -q` |
| 67-02 | T1 — TTL constant + tag_cache + resolver + get_tags_fn | RES-03 | tdd (unit) | `uv run pytest tests/test_scheduler.py tests/test_search.py -k "tag_cache or get_tags_fn or cache or happy_path or make_search_job" -x -q` |
| 67-02 | T2 — invalidation on config save + remove instance | RES-03 | tdd (integration) | `uv run pytest tests/test_web.py -k "tag_cache or invalidat or remove_instance" -x -q` |
| 67-03 | T1 — OriginCheck CSRF scenario tests | TEST-01 | execute (unit, TestClient) | `uv run pytest tests/test_middleware.py -k "missing_origin or missing_referer or scheme_mismatch or suffix_spoof or port_mismatch or no_origin_no_referer" -x -q` |

**Nyquist check:** every task has an `<automated>` verify command (no MISSING gates; all infrastructure pre-exists). No 3 consecutive tasks lack automated verify — all six tasks carry one.

---

## Wave 0 Requirements

No Wave 0 framework install needed — pytest + pytest-asyncio + httpx + loguru are all already in `pyproject.toml [dev]`. Existing test files cover all phase requirements with established patterns.

- [x] `tests/test_middleware.py` exists — TEST-01 adds OriginCheck scenario tests here (existing harness: `app.add_middleware(OriginCheckMiddleware)` + `TestClient`)
- [x] `tests/test_search.py` exists — RES-02 engine `last_success` write tests + RES-03 cache-resolver tests go here
- [x] `tests/test_state.py` exists — RES-02 `_default_instance_state()` / `last_success` persistence tests
- [x] `tests/test_scheduler.py` exists — RES-03 `tag_cache` TTL + app.state init tests (fixtures gain `app.state.tag_cache = {}` per Pitfall 8)
- [x] `tests/test_web.py` exists — RES-02 card render (Last OK + stale flag) + RES-03 config-save/remove invalidation integration tests

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard app card visually shows "Last OK" timestamp and amber stale treatment when a search has not succeeded within 2× the interval | RES-02 | `TestClient` asserts rendered HTML strings, but the amber visual treatment and at-a-glance staleness are a human visual confirmation | (1) Build local Docker image; (2) run container with a configured *arr instance; (3) open dashboard; (4) confirm each connected app card shows "Last OK HH:MM:SS"; (5) stop the *arr instance (or point at a bad URL) and wait > 2× the interval; (6) confirm the timestamp goes amber / stale-flagged while "Never" (null) does NOT render amber |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (N/A — all infrastructure exists)
- [x] No watch-mode flags
- [x] Feedback latency < 35s
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] Manual dashboard staleness visual verification scheduled before milestone deploy

**Approval:** validated — all six tasks map to automated commands; manual visual check deferred to pre-deploy.
