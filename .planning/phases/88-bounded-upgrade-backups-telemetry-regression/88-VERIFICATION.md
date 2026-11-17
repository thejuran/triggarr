---
phase: 88-bounded-upgrade-backups-telemetry-regression
verified: 2026-11-17T03:45:00Z
verified_head: d0df8637
status: passed
score: 20/20 must-haves verified (1 via owner override)
has_blocking_gaps: false
overrides_applied: 1
overrides:
  - must_have: "The test asserts only the outcome (startup completes, /health 200); it does not reference FastAPI's warning wording or private telemetry modules (D-12, Pitfall 11)"
    reason: "Review WR-02 (round 1) required proof that the auto-configure path ran; asserting FastAPI's warning text is the chosen signal, so the test cannot stay green while exercising nothing. No private module is referenced. Accepted brittleness: a FastAPI wording change turns the test red on a dependency bump (visible, easy to fix)."
    accepted_by: "owner"
    accepted_at: "2026-11-17"
    decision: "Keep the wording check (owner answer to the D-12 vs WR-02 question, 2026-11-17)"
gaps: []
---

# Phase 88: Bounded Upgrade Backups & Telemetry Regression Verification Report

**Phase Goal:** Pre-upgrade database backups stay bounded through a crash loop, and the telemetry environment variable can never again crash startup.
**Verified:** 2026-11-17T03:45:00Z at branch head `d0df8637` (phase branch)
**Status:** passed after owner override (originally gaps_found: one minor, non-blocking gap, PLAN 02 truth 3 vs review fix WR-02; the owner accepted the WR-02 wording check on 2026-11-17, overriding D-12 for this assertion)
**Re-verification:** No — initial verification

Verification was done against the code at HEAD, not against the SUMMARYs. Two review-fix rounds changed `triggarr/db.py` and `tests/test_telemetry.py` after the SUMMARYs were written; criterion 2 was judged against the current pre-copy-prune, stage-then-rename, reclaim-stale-partial behavior.

## Goal Achievement

### Observable Truths

ROADMAP success criteria (the contract) first, then PLAN frontmatter truths.

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| SC1 | After repeated failed upgrade attempts, only the original pre-upgrade backup plus at most the 3 most recent later backups remain | VERIFIED | `run_migrations` (`triggarr/db.py` 331-367): pre-copy `_prune_timestamped_backups(..., None)` keeps `candidates[: _MAX_RETAINED_TIMESTAMPED_BACKUPS - 1]` = 2, then the new copy lands (3), then a post-copy prune excluding the new file. `test_backup_bound_holds_through_repeated_failed_attempts` asserts `<= 3` after each of 5 attempts and exactly 3 at the end; `test_backup_crash_loop_then_success_keeps_four_files` asserts 4 v9 files after 5 failures + 1 success. Both pass at HEAD. |
| SC2 | Pruning never removes the original backup or the one just written, orders backups by the timestamp in their names, and a pruning failure is logged without blocking startup | VERIFIED | Original: candidate prefix is `canonical_name + "-"`, so the canonical name structurally cannot match (db.py 202-213). Just written: `if entry == just_written: continue` (208); the pre-copy prune runs before the new file exists, so it cannot touch it either. Order: `candidates.sort(key=lambda pair: pair[0], reverse=True)` on the filename stamp; `grep -v '^\s*#' triggarr/db.py \| grep -c "st_mtime\|getmtime"` = 0. Failure: two `except OSError` handlers log at WARNING and `return`/`continue`; `test_run_migrations_proceeds_when_pruning_fails` reaches schema v10 with unlink failing. Spot-check below reproduces all three properties directly. |
| SC3 | An automated test pins that Triggarr starts and serves requests with `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint set | VERIFIED | `tests/test_telemetry.py::test_telemetry_env_vars_do_not_crash_startup`: `monkeypatch.setenv` of both variables (lines 36-37) before `FastAPI(lifespan=...)` (41); drives the real `create_lifespan` + `router` through `TestClient(app)` as a context manager (44); asserts `/health` 200 `{"status": "ok"}`. Passes at HEAD. SUMMARY records a negative control (forced lifespan crash -> FAIL; delenv -> PASS); the committed file contains no control code (`grep -c "_runtime\|os.environ\|async with lifespan_fn"` = 0). |
| SC4 | The documentation states plainly that telemetry export is unsupported and nothing is exported | VERIFIED | `README.md` line 215: "Triggarr does not support OpenTelemetry export. Setting `FASTAPI_OTEL_AUTO_CONFIGURE` or an OTLP endpoint ... does not stop Triggarr from starting, but nothing is exported." Placement check (after the startup-variables paragraph, before "## Screenshots", no new heading) passes: lines 213 < 215 < 217; `git diff main -- README.md \| grep -c "^+#"` = 0. |
| P1.1 | 5 consecutive failed attempts from v9: canonical + exactly 3 stamped; never more than 3 after any attempt | VERIFIED | Same as SC1. |
| P1.2 | 5 failed + 1 success: schema v10, exactly 4 v9 files, nothing extra deleted on success (D-06) | VERIFIED | No prune call after the migration loop (db.py 373-388); `test_backup_crash_loop_then_success_keeps_four_files` passes. Owner ruling D-06 stands; post-success cleanup is backlogged in MAINTENANCE.md. |
| P1.3 | Canonical backup never deleted and byte-identical to the pre-attempt db | VERIFIED | Structural exclusion (SC2); test asserts `canonical.read_bytes() == original_bytes`. |
| P1.4 | Just-written backup never deleted even if its stamp sorts oldest | VERIFIED | `test_prune_never_deletes_just_written_even_if_clock_went_back` passes; spot-check below (just-written stamped 2020 kept while 2026-stamped files were pruned). |
| P1.5 | Ordering by filename stamp, never mtime | VERIFIED | `test_prune_orders_by_filename_stamp_not_mtime` passes; spot-check: oldest-named file with newest mtime was deleted. |
| P1.6 | Other versions, non-matching names, directories never deleted (D-07) | VERIFIED | `_BACKUP_STAMP_RE.fullmatch` + `is_file()` gate (db.py 213-215); `test_prune_ignores_other_versions_and_non_matching_names` passes; spot-check kept `test.v8-backup-<stamp>` and `test.v9-backup-mycopy`. |
| P1.7 | One INFO line per deleted file stating the original and 3 most recent are kept (D-08) | VERIFIED | db.py 239-243; `test_prune_logs_one_info_line_per_deleted_backup` passes. Note: the same wording is emitted by the pre-copy prune while only 2 remain at that instant (review IN-02, owner-backlogged). Truth as worded still holds. |
| P1.8 | OSError on delete or listing: one WARNING naming file/dir and exception type, remaining deletions run, no exception escapes, migration still runs (D-04, D-09) | VERIFIED | `inspect.getsource` check: exactly 2 `except OSError as exc`, no `logger.error`/`logger.exception`/`raise` in the body (ran at HEAD, "helper shape OK"). `test_prune_unlink_failure_logs_warning_and_continues` injects failure on the FIRST unlink and asserts the second stale file is still deleted; `test_prune_listing_failure_logs_warning` and `test_run_migrations_proceeds_when_pruning_fails` pass. |
| P1.9 | RED evidence observed and recorded for the run_migrations crash-loop tests (D-01) | VERIFIED | 88-01-SUMMARY "Observed RED Evidence" records `assert 4 <= 3` and `assert 6 == 4` AssertionErrors for the two public tests and ImportError/propagated OSError for the helper tests, from node-ID runs without `-x`. Commit order `07f50a76` test -> `4f646134` feat -> `4150c8b5` test -> `5519addc` feat confirmed in `git log`. (Documentary claim; the RED runs themselves are not re-runnable at HEAD.) |
| P1.10 | No new dependency; stdlib only | VERIFIED | `git diff --quiet main -- pyproject.toml uv.lock` exits 0; helper uses `re`, `pathlib`, `shutil` already imported. |
| P2.1 | Real app (create_lifespan + router) completes startup via FastAPI's ASGI lifespan; `/health` 200 (TELEM-01, D-12) | VERIFIED | Same as SC3. |
| P2.2 | Both variables set with `monkeypatch.setenv` before `FastAPI(lifespan=...)`; driven with `TestClient(app)` context manager, never `async with lifespan_fn(app)` | VERIFIED | setenv lines 36-37 precede `FastAPI(` line 41; `with caplog.at_level(...), TestClient(app) as client:` line 44; no `async with lifespan_fn`. The literal acceptance grep `with TestClient(app) as client` now prints 0 only because the `caplog` context manager shares the `with` statement; the link is semantically intact. |
| P2.3 | Test asserts only the outcome; does not reference FastAPI's warning wording or private telemetry modules | FAILED (minor) | Line 51: `assert "automatic telemetry configuration failed" in caplog.text`. Added by review fix WR-02 (`621aebb0`) with a documented rationale (prove the auto-configure path ran). No private module is referenced. See Gaps Summary. |
| P2.4 | Negative control recorded in SUMMARY (FAIL under forced crash; PASS with delenv) | VERIFIED | 88-02-SUMMARY "Negative Control" section records control shape, Run 1 FAIL, Run 2 PASS, and post-control clean diff. (Documentary claim; the control is uncommitted by design and not re-runnable here.) |
| P2.5 | README paragraph in the D-10 location with D-11 content | VERIFIED | Same as SC4. |
| P2.6 | No code change to `triggarr/` and no new dependency from plan 02 | VERIFIED | `git log --name-only --format= --grep "(88-02)"` touches only `README.md`, `tests/test_telemetry.py`, and planning files. |

**Score:** 19/20 truths verified (all 4 ROADMAP success criteria verified; 1 PLAN-level truth failed, severity minor).

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `triggarr/db.py` | `_prune_timestamped_backups` helper, `_BACKUP_STAMP_RE`, `_MAX_RETAINED_TIMESTAMPED_BACKUPS`, call in the timestamped branch | VERIFIED | Lines 119-120 constants (ASCII-digit pattern per IN-01 round 1), 181-243 helper, 246-291 `_remove_abandoned_partial_backups` (added round 2), 338-339 pre-copy calls, 345-358 `.partial` stage-then-rename with cleanup, 367 post-copy call. Substantive (~110 lines of logic, two narrow error boundaries) and wired into `run_migrations`, which the app lifespan calls at startup. |
| `tests/test_db.py` | Crash-loop, ordering, just-written, scoping, logging, failure tests | VERIFIED | 15 phase tests present (9 from the plan + 6 from review rounds covering `.partial` staging, full-disk pre-copy cleanup, stale-partial reclamation, cleanup-failure branch). All pass at HEAD. |
| `tests/test_telemetry.py` | TELEM-01 regression test through the real ASGI lifespan | VERIFIED (with P2.3 deviation) | 52 lines; clears runner OTEL variables (IN-02 round 2), sets both target variables before construction, real lifespan + router, TestClient context manager. |
| `README.md` | TELEM-02 statement | VERIFIED | Line 215; contains `FASTAPI_OTEL_AUTO_CONFIGURE` and "nothing is exported". |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `run_migrations` (`backup_path.exists()` branch) | `_prune_timestamped_backups` | direct call after the copy, before the migration loop | WIRED | Pattern `_prune_timestamped_backups(db_path, current, timestamped_path)` found exactly once (line 367), inside the branch, after `earliest_backup = backup_path`, before the loop. Also a pre-copy call with `None` (339). |
| `_prune_timestamped_backups` | `Path.unlink` | only for `backup_path.name + "-" + fullmatch(_BACKUP_STAMP_RE)` entries | WIRED | `_BACKUP_STAMP_RE.fullmatch` at line 213 gates candidates; `stale_path.unlink(missing_ok=True)` at 231 runs only over the sorted tail. |
| `tests/test_telemetry.py` | FastAPI `__call__` lifespan interception | `TestClient(app)` context manager | WIRED | Line 44. Literal grep pattern drifted (shared `with`), link intact; the recorded negative control is the evidence that the lifespan step is reached. |
| `tests/test_telemetry.py` | `triggarr/web/routes.py::health` | `app.include_router(router)`; `client.get("/health")` | WIRED | Lines 42, 45. |

### Data-Flow Trace (Level 4)

Not applicable: no artifact in this phase renders dynamic data. The pruning helper's inputs are the real directory listing of the database's parent (verified by spot-check and by `seed_v9_db`-based tests that operate on real files).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite green at HEAD | `uv run pytest tests/ -x -q` (run once) | `3351 passed, 1 skipped, 38 warnings in 87.85s` | PASS |
| Lint clean | `uv run ruff check triggarr/ tests/` | `All checks passed!` | PASS |
| The 15 phase tests pass by node ID | `uv run pytest -q <15 node IDs>` | `15 passed, 1 warning in 0.76s` | PASS |
| Helper: order by name, keep just-written, spare decoys | Scratch dir with canonical + 5 stamped (oldest-named given newest mtime) + v8 decoy + `-mycopy` decoy + just-written stamped 2020; call `_prune_timestamped_backups(db, 9, just_written)` | Remaining: canonical, just-written (2020), the two newest-named 2026 files, v8 decoy, `-mycopy`; three INFO lines, one per deleted file | PASS |
| Helper shape (two narrow OSError handlers, no error-level log, no re-raise) | PLAN 01 Task 2 `inspect.getsource` acceptance one-liner | `helper shape OK` | PASS |
| No dependency change | `git diff --quiet main -- pyproject.toml uv.lock` | exit 0; lockfile has `opentelemetry-api` only (FastAPI's own dependency), no SDK/exporter | PASS |
| README placement | awk check from PLAN 02 Task 2 | lines 213 / 215 / 217, exit 0 | PASS |

### Probe Execution

Not applicable: no `scripts/*/tests/probe-*.sh` are declared by the PLANs or SUMMARYs, and `find scripts -path '*/tests/probe-*.sh'` is not part of this phase's contract.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| BKUP-01 | 88-01 | Original backup always kept plus at most the 3 most recent later ones | SATISFIED | SC1, P1.1-P1.2; tests pass at HEAD |
| BKUP-02 | 88-01 | Never removes original or just-written; orders by name timestamp; pruning failure logged without blocking startup | SATISFIED | SC2, P1.3-P1.8; `inspect.getsource` check; tests pass |
| TELEM-01 | 88-02 | With both variables set, Triggarr starts and serves; an automated test pins this | SATISFIED | SC3; `tests/test_telemetry.py` passes. Note: REQUIREMENTS wording says "in the container environment"; CONTEXT D-12 scopes this phase to an in-process test and names a built-image check as optional, uncommitted Phase 92 scope. Not a gap against the phase contract. |
| TELEM-02 | 88-02 | Documentation states export is unsupported and nothing is exported | SATISFIED | SC4; README line 215 |

Orphaned requirements: none. REQUIREMENTS.md maps exactly BKUP-01, BKUP-02, TELEM-01, TELEM-02 to Phase 88, and both are claimed by the plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | - | `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` in the 4 modified files | - | No debt markers found; no stub returns |
| `triggarr/db.py` | 239-243 | Pre-copy prune logs "keeping ... the 3 most recent" while 2 remain at that moment | Info | Review round 3 IN-02; owner-backlogged under the stopping rule (MAINTENANCE.md). Message accuracy only. |
| `triggarr/db.py` | 246-260, 332-339 | Single-process assumption for `.partial` reclamation is documented, not enforced | Info | Review round 3 IN-01; owner-backlogged. Unsupported multi-instance deployment only; no backup loss. |
| `tests/test_telemetry.py` | 51 | Asserts a dependency's log wording | Warning (the one gap) | Brittleness on FastAPI wording changes; see Gaps Summary |

### Human Verification Required

None. Every success criterion is pinned by an automated test that was run at HEAD, and the pruning helper's three invariants were reproduced directly on a scratch directory. The review-fix report marked WR-01 "requires human verification" for the order-of-operations change; that change is now covered by `test_retry_backup_fits_on_full_disk_after_pre_copy_cleanup`, `test_restart_reclaims_abandoned_partials_and_keeps_newest_backups`, and the updated `test_failed_retry_backup_copy_leaves_no_candidate_and_spares_good_backups`, all passing.

### Gaps Summary

The phase goal is achieved: all four ROADMAP success criteria are verified in the code at HEAD, the full suite and ruff are clean, and both requirement groups are satisfied. There are no blocking gaps.

One minor gap remains, and it is a plan-vs-review conflict rather than a missing implementation. PLAN 02 (from CONTEXT D-12 and research Pitfall 11) required the telemetry test to assert only the outcome and never FastAPI's warning wording, to avoid a test that goes red when FastAPI rewords an internal message. Review round 1 (WR-02) asked for the opposite tradeoff: without some signal that the auto-configure path actually ran, the test would stay green if FastAPI renamed or dropped the variable, and the "pin" would be hollow. The fix (`621aebb0`) added `assert "automatic telemetry configuration failed" in caplog.text`. Both concerns are legitimate; the current code favours detection power over dependency-wording stability. The practical cost is one possible false red on a future FastAPI bump, which an operator would triage as a wording change. The PLAN 02 acceptance grep for `telemetry configuration failed` now also prints 1 instead of 0 for the same reason.

**This looks intentional.** To accept this deviation, add to this file's frontmatter:

```yaml
overrides:
  - must_have: "The test asserts only the outcome (startup completes, /health 200); it does not reference FastAPI's warning wording or private telemetry modules (D-12, Pitfall 11)"
    reason: "Review WR-02 (round 1) required proof that the auto-configure path ran; asserting the warning text is the chosen signal. No private module is referenced. Accepted brittleness: a FastAPI wording change turns the test red on a dependency bump."
    accepted_by: "<owner>"
    accepted_at: "<ISO timestamp>"
```

Alternatively, a wording-independent signal (for example, asserting that at least one WARNING-level record was emitted on the `fastapi` logger during startup, without matching its text) would satisfy both the plan truth and WR-02.

Items noted but not counted as gaps: the two round-3 Info findings (log-line count wording; single-process assumption) are owner-backlogged under the stopping rule; the D-06 post-success retention is an owner ruling with a backlog entry; the "container environment" wording of TELEM-01 is scoped by D-12 to an in-process test for this phase.

---

_Verified: 2026-11-17T03:45:00Z_
_Verifier: Claude (bm-verifier)_
