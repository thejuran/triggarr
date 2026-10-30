---
phase: 86
slug: pilot-reference-record
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-30
---

# Phase 86 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | Refresh-counts PR: `uv run pytest tests/test_refresh_counts.py tests/test_malformed_records_client_path.py -x -q`; card-template PR: `uv run pytest tests/test_outcome.py tests/test_app_cards.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~120 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command for the files touched (docs tasks: the task's grep/structure check)
- **After every plan wave:** Run the full suite command
- **Before `/bm:verify-work`:** Full suite must be green on each pilot PR's final head and on the Phase 86 PR
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

Filled in by the planner/executor per plan. Code tasks (Refresh-counts, card template) are TDD: the existing tests that pin the old behavior are rewritten first (red), then the fix (green). Docs tasks (pilot record, scorecards, PILOT-03 decision, adoption guide) are verified by grep for required sections and verbatim text (e.g. the D-15 bar present before the comparison results).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 86-xx-xx | — | — | PILOT-01..04 | — | malformed upstream record is skipped, not crashing/disconnecting | unit / grep | see plans | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The tests to change already exist (`tests/test_refresh_counts.py`, `tests/test_malformed_records_client_path.py`, `tests/test_outcome.py`, `tests/test_app_cards.py`).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Owner PILOT-03 decisions recorded | PILOT-03 | Owner decision | Owner answers the recommendation; decision quoted in the pilot record |
| Exact-commit owner acceptance of each new pilot PR | PILOT-01 | Owner-only gate | Per `docs/owner-cli-acceptance.md` |
| Proof-based tally approved | PILOT-02 | Owner approves tally (D-09) | Owner reviews the comparison tally |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
