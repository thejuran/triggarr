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

Task IDs follow `{plan}-T{n}`. Threat refs point at each plan's `<threat_model>` register.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 87-01-T1 | 87-01 | 1 | CONSIST-01 | T-87-03, T-87-03b | Failed save during removal leaves live settings, scheduler job, client registry, state entry and tag-cache entry unchanged (full postcondition, D-03); settings read and existence re-check inside search_lock, so concurrent removals never resurrect each other (D-02) | unit (TestClient) + async concurrency (ASGITransport, lock held) + AST lock audit | `uv run pytest tests/test_web.py -k remove_instance -x -q && uv run python tests/audit_lock_coverage.py` | ✅ extend existing | ⬜ pending |
| 87-01-T2 | 87-01 | 1 | CONSIST-02 | T-87-01, T-87-02, T-87-04b | Exactly one error log entry for a failed removal through the real writer (writer's own line suppressed via `log_failure=False` for this caller only; default unchanged for all others, D-07); fixed D-05 wording; 200 for htmx / 500 plain; no file path, system error text or exception name; instance name escaped | unit (writer + TestClient) + AST lock audit | `uv run pytest tests/test_config.py -k atomic_toml_write -x -q && uv run pytest tests/test_web.py -k remove_instance -x -q && uv run python tests/audit_lock_coverage.py` | ✅ extend existing | ⬜ pending |
| 87-01-T3 | 87-01 | 1 | CONSIST-01 | T-87-04, T-87-05 | After a successful save, a failing scheduler-job removal or client close is logged and every other tidy-up step still runs; normal success response (D-15, D-16) | unit (TestClient) | `uv run pytest tests/test_web.py tests/test_state.py tests/test_config.py -x -q && uv run python tests/audit_lock_coverage.py && uv run ruff check triggarr/ tests/` | ✅ extend existing | ⬜ pending |
| 87-02-T1 | 87-02 | 2 | CONSIST-02 | T-87-07, T-87-08, T-87-10 | Remove button targets a row-local slot (no body swap); `test_no_new_body_swap_html_targets` updated to 0 in the same change, obsolete `matches[0]` assertion removed | unit (TestClient render + template scan) | `uv run pytest tests/test_web.py -k "remove_instance or body_swap or remove_button or settings" -x -q` | ✅ extend existing | ⬜ pending |
| 87-02-T2 | 87-02 | 2 | CONSIST-02 (D-13/D-14 records) | T-87-09, T-87-10b | Four MAINTENANCE.md records, each on its own line with its required evidence: D-13 audit (route list + routes.py lines), D-14 follow-up (raw server-error page, Add Instance, UI Redesign item), UTF-8 UnicodeDecodeError finding, pre-lock settings snapshot in add_instance/save_settings; no code change | doc check (per-record content pipeline) | Task 2 verify command in 87-02-PLAN.md (prints `RECORDS-OK` only when all four records and their evidence are present) | ✅ | ⬜ pending |
| 87-03-T1 | 87-03 | 1 | CONSIST-03 | T-87-11, T-87-12 | Valid-JSON non-object roots (`[]`, `42`, `null`, string, bool, float) start with default state and log a warning carrying no file contents | unit | `uv run pytest tests/test_state.py -x -q` | ✅ flip `test_state_wrong_structure_list_crashes`; add siblings | ⬜ pending |
| 87-03-T2 | 87-03 | 1 | CONSIST-03 | T-87-13, T-87-14, T-87-15, T-87-16 | Exactly one set-aside copy, permissions no wider than state.json; a failure at mkstemp, copy2 or os.replace never blocks recovery, leaves no temp file and leaks no descriptor; a failed rename keeps the previous copy (D-08, D-09, D-11) | unit | `uv run pytest tests/test_state.py -x -q && uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` | ✅ new tests in existing file | ⬜ pending |

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
