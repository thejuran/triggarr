---
phase: 87
slug: settings-state-file-safety
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-11-15
audited: 2026-11-15
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
| **Estimated runtime** | Quick run under 3s; full suite about 127s (3331 passed, 1 skipped, audit 2026-11-15) |

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
| 87-01-T1 | 87-01 | 1 | CONSIST-01 | T-87-03, T-87-03b | Failed save during removal leaves live settings, scheduler job, client registry, state entry and tag-cache entry unchanged (full postcondition, D-03); settings read and existence re-check inside search_lock, so concurrent removals never resurrect each other (D-02) | unit (TestClient) + async concurrency (ASGITransport, lock held) + AST lock audit | `uv run pytest tests/test_web.py -k remove_instance -x -q && uv run python tests/audit_lock_coverage.py` | ✅ extend existing | ✅ green |
| 87-01-T2 | 87-01 | 1 | CONSIST-02 | T-87-01, T-87-02, T-87-04b | Exactly one error log entry for a failed removal through the real writer (writer's own line suppressed via `log_failure=False` for this caller only; default unchanged for all others, D-07); fixed D-05 wording; 200 for htmx / 500 plain; no file path, system error text or exception name; instance name escaped | unit (writer + TestClient) + AST lock audit | `uv run pytest tests/test_config.py -k atomic_toml_write -x -q && uv run pytest tests/test_web.py -k remove_instance -x -q && uv run python tests/audit_lock_coverage.py` | ✅ extend existing | ✅ green |
| 87-01-T3 | 87-01 | 1 | CONSIST-01 | T-87-04, T-87-05 | After a successful save, a failing scheduler-job removal or client close is logged and every other tidy-up step still runs; normal success response (D-15, D-16) | unit (TestClient) | `uv run pytest tests/test_web.py tests/test_state.py tests/test_config.py -x -q && uv run python tests/audit_lock_coverage.py && uv run ruff check triggarr/ tests/` | ✅ extend existing | ✅ green |
| 87-02-T1 | 87-02 | 2 | CONSIST-02 | T-87-07, T-87-08, T-87-10 | Remove button targets a row-local slot (no body swap); `test_no_new_body_swap_html_targets` updated to 0 in the same change, obsolete `matches[0]` assertion removed | unit (TestClient render + template scan) | `uv run pytest tests/test_web.py -k "remove_instance or body_swap or remove_button or settings" -x -q` | ✅ extend existing | ✅ green |
| 87-02-T2 | 87-02 | 2 | CONSIST-02 (D-13/D-14 records) | T-87-09, T-87-10b | Four MAINTENANCE.md records, each on its own line with its required evidence: D-13 audit (route list + routes.py lines), D-14 follow-up (raw server-error page, Add Instance, UI Redesign item), UTF-8 UnicodeDecodeError finding, pre-lock settings snapshot in add_instance/save_settings; no code change | doc check (per-record content pipeline) | Task 2 verify command in 87-02-PLAN.md (prints `RECORDS-OK` only when all four records and their evidence are present) | ✅ | ✅ green |
| 87-03-T1 | 87-03 | 1 | CONSIST-03 | T-87-11, T-87-12 | Valid-JSON non-object roots (`[]`, `42`, `null`, string, bool, float) start with default state and log a warning carrying no file contents | unit | `uv run pytest tests/test_state.py -x -q` | ✅ flip `test_state_wrong_structure_list_crashes`; add siblings | ✅ green |
| 87-03-T2 | 87-03 | 1 | CONSIST-03 | T-87-13, T-87-14, T-87-15, T-87-16 | Exactly one set-aside copy, permissions no wider than state.json; a failure at mkstemp, copy2 or os.replace never blocks recovery, leaves no temp file and leaks no descriptor; a failed rename keeps the previous copy (D-08, D-09, D-11) | unit | `uv run pytest tests/test_state.py -x -q && uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` | ✅ new tests in existing file | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Post-plan fix coverage (review rounds 1-3 and the deep-review pass)

| Fix | Requirement | Behavior | Test(s) | Status |
|-----|-------------|----------|---------|--------|
| WR-02 (79f0f9e2) | CONSIST-02 | Every removal failure, not only OSError, shows on the row; stale messages cleared; plain not-found keeps 400 with escaped name | `test_remove_instance_not_found_plain_keeps_400_and_escapes_name` + `-k remove_instance` set | ✅ green |
| WR-01 (0bd66a85, d5aa50c7) | CONSIST-03 | Unreadable state file gets an accurate warning, no set-aside, no replacement promise | `test_state_unreadable_warning_does_not_promise_replacement` + `tests/test_state.py` | ✅ green |
| IN-01 (92ddc3a1) | CONSIST-02 | Clicking the error slot does not collapse the instance (template wiring) | `-k remove_error` render tests | ✅ green |
| IN-02 | CONSIST-03 | Set-aside permission test can actually fail | `test_state_set_aside_permissions_not_wider` (0o640 source) | ✅ green |
| F001 (bef326b9) | CONSIST-01 | Add Instance during a removal's write does not resurrect the removed instance; duplicate check uses settings read under the lock | `test_add_instance_during_removal_write_does_not_resurrect_removed`, `test_add_instance_duplicate_check_uses_settings_current_under_lock` | ✅ green |
| WR-01/SA-01 fix2 (a6043c37) | CONSIST-02 | One contextual error for every failed removal write, including a write that never starts | `test_remove_instance_write_never_starts_logs_one_error`, `test_atomic_toml_write_log_failure_false_suppresses_unexpected_error_line` | ✅ green |
| WR-01 fix3 (beff1f34) | CONSIST-01 | A removal write the route gave up on never runs later; a write already running is reported truthfully | `test_remove_instance_refused_thread_start_does_not_write_later`, `test_remove_instance_refused_thread_start_with_write_already_running_reports_the_write` | ✅ green |
| Deep review (7a92e735) | CONSIST-01 | General-only Save overlapping a removal does not resurrect the removed instance | `test_general_settings_save_during_removal_write_does_not_resurrect_removed` | ✅ green |

Out of scope by owner decision, not a coverage gap: the full-form stale-page Save Settings case (AR-87-02) stays in `.planning/backlog/MAINTENANCE.md`.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (pytest, the `multi_instance_app`
fixture, `tmp_path`-based state tests, the loguru sink-capture pattern). No new fixtures
and no framework install.

---

## Manual-Only Verifications

All CONSIST-01/02/03 behaviors have automated verification. These browser-only checks sit outside what pytest can sample and are tracked in `87-HUMAN-UAT.md`:

| Behavior | Why manual | UAT item | Status |
|----------|-----------|----------|--------|
| Failed-removal message appears on the clicked row in a real browser, no reload, unsaved edits kept | htmx swap behavior in a live browser | 87-HUMAN-UAT #1 | passed 2026-11-15 |
| Clicking the error message leaves the instance open | `<summary>` toggle is browser behavior | 87-HUMAN-UAT #2 | passed 2026-11-15 |
| Screen reader announces the failed-removal message | needs assistive technology | 87-HUMAN-UAT #3 | pending |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency: one quick run per task commit
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-11-15 (Nyquist audit)

---

## Validation Audit 2026-11-15

Audited at `bba1274a`. Every task verify command was re-run: remove_instance set 29 passed, lock audit 8/8 covered, atomic_toml_write 8 passed, settings/remove-button set 72 passed, `tests/test_state.py` 54 passed, `RECORDS-OK` printed, full suite 3331 passed / 1 skipped, ruff clean.

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
