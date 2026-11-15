---
phase: 87
slug: settings-state-file-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-11-15
---

# Phase 87 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_web.py tests/test_state.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | Not measured at planning time — executor records the observed runtime on first run |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_web.py tests/test_state.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/`
- **Before `/bm:verify-work`:** Full suite must be green
- **Max feedback latency:** one quick run (two test files) per task commit

---

## Per-Task Verification Map

Task IDs are assigned by the planner; the rows below are the requirement-level contract
each plan's tasks must map onto. The planner/executor replaces the Task ID, Plan and Wave
placeholders once the plans exist.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | CONSIST-01 | — | Failed save during removal leaves live settings, scheduler job, client registry and state entry unchanged (full postcondition asserted, D-03) | unit (TestClient) | `uv run pytest tests/test_web.py -k remove_instance -x -q` | ✅ extend existing | ⬜ pending |
| TBD | TBD | TBD | CONSIST-02 | TBD | Fixed-wording error (D-05) on the instance row; no file path, system error text or exception name in the response; instance name escaped | unit (TestClient) | `uv run pytest tests/test_web.py -k remove_instance -x -q` | ✅ extend existing; `test_no_new_body_swap_html_targets` updated in the same change | ⬜ pending |
| TBD | TBD | TBD | CONSIST-03 | TBD | Valid-JSON non-object state root (`[]`, `42`, `null`) starts with default state and logs a warning that carries no file contents | unit | `uv run pytest tests/test_state.py -k "wrong_structure or state_corrupt" -x -q` | ✅ flip `test_state_wrong_structure_list_crashes`; add siblings | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (pytest, the `multi_instance_app`
fixture, `tmp_path`-based state tests, the loguru sink-capture pattern). No new fixtures
and no framework install.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency: one quick run per task commit
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
