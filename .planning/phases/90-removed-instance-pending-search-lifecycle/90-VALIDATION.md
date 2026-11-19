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
> Revised 2026-11-18 to match the planned test paths, selectors, tasks and the serialized schedule (8 plans, one per wave).
> Re-synced 2026-11-18 after plan check iteration 2: no selector changed; behaviours added for verified rollback and connection retirement/replacement (90-02, 90-05, 90-06), the race-test preconditions (90-07) and the two D-09 residual tests (90-08, one renamed).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode=auto`), ruff |
| **Config file** | `pyproject.toml` |
| **Quick run command** | the current task's own selector from the map below (each runs in a few seconds) |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | a few seconds per selector; full suite longer |

TDD mode is on: each regression test is written first and must fail on the unfixed code (D-00a). Tests planned as PASS pins are named as such in the plans and are recorded with their observed result.

---

## Sampling Rate

The schedule is serialized: one plan per wave, plans run strictly in order (90-01 to 90-08) in a single working tree. No plan runs while another plan's RED tests exist.

- **RED run (evidence, not a gate):** after a task's `test(...)` commit, run only that task's selector from the map below. Failures are expected and are recorded per test in the plan SUMMARY (command, pass/fail, failing assertion or error). The full suite is not run as a gate at this point.
- **After every task's `feat(...)` commit (GREEN gate):** the task's `<verify>` command, which includes the task's selector.
- **After every plan (= every wave):** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`. A plan may only end with the full suite green, so the next plan always starts from a green tree.
- **Before `/bm:verify-work`:** full suite must be green.
- **Max feedback latency:** 10 seconds for a task selector.

---

## Per-Task Verification Map

| Task | Wave | Requirement | Behavior | Test Type | Automated Command | File | Status |
|------|------|-------------|----------|-----------|-------------------|------|--------|
| 90-01 T1 | 1 | RMINST-02 | One shared pending rule; NULL outcome counts as pending for the cap (both modes) and tracking, never pruned | unit (db) | `uv run pytest tests/test_db.py -q -k pending_predicate` | tests/test_db.py (new tests) | ⬜ pending |
| 90-01 T2 | 1 | RMINST-02 | `instance_removed` is finished: out of the cap, tracking, grab rate and historical flag; never Legacy; filterable; ages out (D-06, D-07, D-08) | unit (db) | `uv run pytest tests/test_db.py -q -k "instance_removed or pending_predicate"` | tests/test_db.py (new tests) | ⬜ pending |
| 90-02 T1 | 2 | RMINST-01 | Close-out by stable ID only; other identities, finished and Legacy rows untouched; failure and cancellation (UPDATE queued, commit in flight, repeated cancel) leave no open transaction and nothing a later commit can flush; rollback verified and retried after a rollback failure or rollback-task cancellation (real SQL applied); when it cannot be verified the connection is retired, cannot commit, and a replacement on the same file shows the rows still pending after an unrelated commit; rollback-failure log carries type names only | unit (db) | `uv run pytest tests/test_db.py -q -k close_out_instance_removed` | tests/test_db.py (new tests) | ⬜ pending |
| 90-02 T2 | 2 | RMINST-04 | Orphan sweep closes unconfigured and NULL-ID rows; configured, Legacy and finished rows untouched; idempotent; zero configured instances still swept (pre-release orphans; failed close-out of the last instance); cancellation between group updates rolls everything back; persistent rollback failure retires the connection and the abandoned updates are never committed | unit (db) | `uv run pytest tests/test_db.py -q -k orphan_sweep` | tests/test_db.py (new tests) | ⬜ pending |
| 90-03 T1 | 3 | RMINST-03, RMINST-02 | Sonarr/Radarr/Lidarr same-name reuse never selects or credits old rows (mock and real-client variants, history-request assertions kept for the owned row); mixed old/new rows: only own row tracked; NULL-ID row never selected; closed rows never selected | unit/integration | `uv run pytest tests/test_tracking.py -q -k name_reuse` | tests/test_tracking.py (5 rewritten + new) | ⬜ pending |
| 90-03 T1 | 3 | RMINST-03 | Radarr/Lidarr empty stable ID refuses to track; existing per-instance isolation test holds with distinct stable IDs | unit | `uv run pytest tests/test_tracking.py -q -k "empty_stable_id or per_instance_tracking_isolation"` | tests/test_tracking.py (new + 1 adjusted) | ⬜ pending |
| 90-04 T1 | 4 | RMINST-01, RMINST-03 | History badge text, tooltip and gray styling; never conflated with Legacy; filter option present and filtering; row keeps its instance name and is not shown as in progress (D-02..D-05) | template/route | `uv run pytest tests/test_attribution_disclosure.py -q -k "history and instance_removed"` | tests/test_attribution_disclosure.py (new tests) | ⬜ pending |
| 90-04 T2 | 4 | RMINST-01 | Activity rail pill, tooltip, gray styling, never conflated with Legacy; dashed card (PASS pin) | template/route | `uv run pytest tests/test_attribution_disclosure.py -q -k "activity_rail and instance_removed"` | tests/test_attribution_disclosure.py (new tests) | ⬜ pending |
| 90-05 T1 | 5 | RMINST-01, RMINST-02 | Remove action closes rows for all three apps after the write (the Lidarr case builds its own `InstanceConfig` locally; the fixture configures none); write failure closes nothing (PASS pin); a close-out whose rollback cannot be verified gets the shared connection replaced before the lock is released, response unchanged; replacement failure still succeeds; close-out failure still succeeds and tidies up; cancellation (patched and with the real database function) finishes database cleanup before the lock is released and still closes the client; no-ID skip; removed-key and URL-userinfo sentinels absent from stderr and the viewer buffer | integration | `uv run pytest tests/test_web.py -q -k "remove_instance and (close_out or pending_searches or stable_id)"` | tests/test_web.py (new tests) | ⬜ pending |
| 90-05 T2 | 5 | RMINST-01 | Save Settings omission closes rows; disabled or unchanged instance closes nothing (PASS pins); close-out failure still saves; cancellation during close-out: state already persisted, stale clients closed, then re-raised; retired connection replaced; log sentinels absent | integration | `uv run pytest tests/test_web.py -q -k "save_settings and (close_out or pending_searches)"` | tests/test_web.py (new tests) | ⬜ pending |
| 90-06 T1 | 6 | RMINST-04 | Lifespan runs the sweep after the cutover and before scheduler start with all configured instances (disabled included); real-database effect; idempotent across restarts; failure non-fatal and sanitized; a sweep failure that retired the connection starts on a replacement, and stops startup when none can be opened; cancellation reaches startup cleanup; zero-instance configuration still swept (pre-release orphans; failed close-out of the last instance), Legacy preserved | integration | `uv run pytest tests/test_scheduler.py -q -k sweep` | tests/test_scheduler.py (new tests) | ⬜ pending |
| 90-06 T1 | 6 | RMINST-04 | Missing, corrupt or invalid configuration exits before the lifespan (evidence for sweeping a zero-instance configuration; PASS pins) | unit | `uv run pytest tests/test_config.py -q -k "SystemExit or exit or missing or corrupt or invalid"` (executor records the exact test names) | tests/test_config.py (existing; add only a missing case) | ⬜ pending |
| 90-07 T1 | 7 | RMINST-01, RMINST-02, RMINST-03 | Revalidation rule: unchanged accepted with live config; removed, disabled, new ID, replaced client rejected | unit | `uv run pytest tests/test_scheduler.py -q -k revalidate_queued_instance` | tests/test_scheduler.py (new tests) | ⬜ pending |
| 90-07 T1 | 7 | RMINST-01, RMINST-02, RMINST-03 | Race regression (event/barrier; instance under test explicitly enabled with a stable ID first, write barrier ends in the real writer, every wait bounded, gate released and tasks joined in `finally`, removal success asserted before the result is read): scheduled job queued behind a removal (Remove action and Save Settings omission) and behind a same-name re-creation: no stale dispatch, no inserted pending row, no tracking credit; unchanged instance still runs (PASS pin) | integration | `uv run pytest tests/test_web.py -q -k "queued and scheduled_job"` | tests/test_web.py (new tests) | ⬜ pending |
| 90-07 T2 | 7 | RMINST-01, RMINST-02, RMINST-03 | Race regression (event/barrier, same preconditions and bounded waits as the scheduled-job cases): manual search queued behind a removal (both paths) and a same-name re-creation: 400, no dispatch, no row, no credit, rate limiter not stamped; unchanged instance still runs (PASS pin) | integration | `uv run pytest tests/test_web.py -q -k "queued and manual_search"` | tests/test_web.py (new tests) | ⬜ pending |
| 90-08 T1 | 8 | RMINST-01..04, D-09 | End-to-end lifecycle per app (close-out, reuse, tracking, cap, History data, startup sweep incl. zero instances); D-09: a new same-name instance shows none of the old instance's stats (`test_same_name_instance_never_shows_removed_instance_stats`); the helper's name-only mode matches old rows but no view passes a bare name (`test_name_only_stats_helper_mode_matches_old_rows_but_no_view_uses_it`); the unfiltered aggregate view intentionally keeps removed instances' lifetime totals (`test_unfiltered_stats_view_keeps_removed_instance_lifetime_totals`) | integration | `uv run pytest tests/test_removed_instance_lifecycle.py -q` | tests/test_removed_instance_lifecycle.py (new file) | ⬜ pending |
| 90-08 T2 | 8 | RMINST-01..04 (wording) | Requirements, roadmap and state wording widened to three apps; nothing ticked; backlog notes | docs check | `grep -c "Sonarr, Radarr or Lidarr" .planning/REQUIREMENTS.md .planning/ROADMAP.md .planning/STATE.md && uv run pytest tests/test_docs_accuracy.py tests/test_repository_hygiene.py -q` | planning files | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements; no Wave 0 scaffold plan is needed. Helpers to reuse: `_insert_cutover`, `_set_outcome`, `_ids` (`tests/test_db.py`), `_insert_entry` (`tests/test_tracking.py`), `app_env` fixture (`tests/test_attribution_disclosure.py`), `multi_instance_app` fixture (`tests/test_web.py`), lifespan pattern `test_lifespan_records_attribution_cutover_once` and `_FakeScheduler` (`tests/test_scheduler.py`). The lock and settings-write barriers used by the race regressions, and the helper that enables the fixture's disabled `4K` with a stable ID, are created in plan 90-07 Task 1. `multi_instance_app` itself is not edited by any plan: it configures Radarr `Default`/`4K` (disabled) and Sonarr `Default`, and no Lidarr instance.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Badge reads clearly next to Legacy in a real browser | RMINST-01 | Visual judgment | Remove an instance with pending searches, open History and the dashboard rail, confirm the "Instance removed" badge and tooltip beside a Legacy badge (plan 90-04 Task 2 human-check) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
