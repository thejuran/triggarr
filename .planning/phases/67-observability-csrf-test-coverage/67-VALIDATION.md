---
phase: 67
slug: observability-csrf-test-coverage
status: draft
nyquist_compliant: false
wave_0_complete: false
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

- **After every task commit:** Run `uv run pytest tests/test_<scope>.py -x -q` (scoped to the touched test file — `test_middleware.py` for TEST-01, `test_search.py`/`test_state.py` for RES-02/RES-03, `test_web.py` for the card render + cache invalidation)
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite green AND `uv run ruff check triggarr/ tests/` exits 0
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

The planner will fill this in completely. Below is the verification scaffolding — every plan must produce tasks that map to one of these requirement IDs and types. All three requirements are independently testable; the work is heavily test-first (TDD mode enabled).

| Plan (anticipated) | Requirement | Verification Type | Automated Command (illustrative) |
|--------------------|-------------|-------------------|----------------------------------|
| RES-02 last_success field + engine write | RES-02 | unit | `uv run pytest tests/test_search.py -k last_success -x -q` |
| RES-02 stale flag in _build_app_context + card render | RES-02 | unit + integration | `uv run pytest tests/test_web.py -k last_success_stale -x -q` |
| RES-03 tag_cache resolver + TTL | RES-03 | unit | `uv run pytest tests/test_scheduler.py -k tag_cache -x -q` |
| RES-03 invalidation on config save / remove instance | RES-03 | integration | `uv run pytest tests/test_web.py -k tag_cache_invalidat -x -q` |
| TEST-01 OriginCheck scenario coverage | TEST-01 | unit (TestClient) | `uv run pytest tests/test_middleware.py -k origin -x -q` |

---

## Wave 0 Requirements

No Wave 0 framework install needed — pytest + pytest-asyncio + httpx + loguru are all already in `pyproject.toml [dev]`. Existing test files cover all phase requirements with established patterns.

- [x] `tests/test_middleware.py` exists — TEST-01 adds OriginCheck scenario tests here (existing harness: `app.add_middleware(OriginCheckMiddleware)` + `TestClient`)
- [x] `tests/test_search.py` exists — RES-02 engine `last_success` write tests + RES-03 cache-hit-avoids-refetch tests go here
- [x] `tests/test_state.py` exists — RES-02 `_default_instance_state()` / `last_success` persistence tests
- [x] `tests/test_scheduler.py` exists — RES-03 `tag_cache` TTL + app.state init tests
- [x] `tests/test_web.py` exists — RES-02 card render (Last OK + stale flag) + RES-03 config-save invalidation integration tests

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard app card visually shows "Last OK" timestamp and amber stale treatment when a search has not succeeded within 2× the interval | RES-02 | `TestClient` asserts rendered HTML strings, but the amber visual treatment and at-a-glance staleness are a human visual confirmation | (1) Build local Docker image; (2) run container with a configured *arr instance; (3) open dashboard; (4) confirm each connected app card shows "Last OK HH:MM:SS"; (5) stop the *arr instance (or point at a bad URL) and wait > 2× the interval; (6) confirm the timestamp goes amber / stale-flagged while "Never" (null) does NOT render amber |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (N/A — all infrastructure exists)
- [ ] No watch-mode flags
- [ ] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter (set after plans complete)
- [ ] Manual dashboard staleness visual verification scheduled before milestone deploy

**Approval:** pending
