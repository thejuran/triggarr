---
phase: 88
slug: 88-bounded-upgrade-backups-telemetry-regression
status: verified
threats_open: 0
asvs_level: 1
created: 2026-11-16
---

# Phase 88 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| process -> local filesystem (config/data directory) | The process deletes files next to its own database (`_prune_timestamped_backups`, and `_remove_abandoned_partial_backups` added during review). File names in the directory may have been created by the user or other tools, so they are untrusted input to the deletion decision. | File paths/names only; no file contents read before deletion |
| process -> log sink | Pruning messages carry paths and OS error text through the existing loguru redacting sink. | Path strings, `type(exc).__name__: exc` text |
| container environment -> FastAPI startup | Operator-set environment variables (`FASTAPI_OTEL_AUTO_CONFIGURE`, `OTEL_*`) influence startup behavior before Triggarr's own code runs. | Env var values only |
| test process -> network | The lifespan under test schedules an existing update-check job; the OTLP endpoint value could in principle be contacted. | None observed to leave loopback |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-88-01 | Tampering | `_prune_timestamped_backups` deletion selection | mitigate | `triggarr/db.py:202-217` — candidate selection requires `entry.name.startswith(prefix)` (prefix = canonical name + `"-"`), `_BACKUP_STAMP_RE.fullmatch` on the remainder, and `entry.is_file()`; enumerated via `db_path.parent.iterdir()` (no glob). Verified: `tests/test_db.py::test_prune_ignores_other_versions_and_non_matching_names` (line 2944) — PASS. | closed |
| T-88-02 | Tampering (loss of recovery data) | canonical `.v{current}-backup` and just-written backup | mitigate | `triggarr/db.py:202-203` — canonical name has no `"-stamp"` suffix so it can never satisfy the `prefix` match; `db.py:208` explicitly excludes `entry == just_written`. Verified: `test_backup_bound_holds_through_repeated_failed_attempts` (line 2582) and `test_prune_never_deletes_just_written_even_if_clock_went_back` (line 2918) — both PASS. | closed |
| T-88-03 | Tampering (wrong order) | retention ordering | mitigate | `triggarr/db.py:226-227` — `candidates.sort(key=lambda pair: pair[0], reverse=True)` sorts by the filename stamp string, never `stat().st_mtime`/`getmtime` (confirmed absent by grep). Verified: `test_prune_orders_by_filename_stamp_not_mtime` (line 2889) — PASS. | closed |
| T-88-04 | Denial of Service | startup during a crash loop (disk fill) | mitigate | `_MAX_RETAINED_TIMESTAMPED_BACKUPS = 3` (`db.py:120`) caps timestamped copies; canonical + 3 is the hard ceiling. Verified: `test_backup_bound_holds_through_repeated_failed_attempts`, `test_backup_crash_loop_then_success_keeps_four_files` (line 2623) — both PASS. Strengthened post-plan by a review fix (`54c67a12`, WR-01/Codex F001) that prunes *before* the new copy and reclaims abandoned `.partial` staging files, so a disk already full of old retry copies no longer blocks startup — see Unregistered Attack Surface below. | closed |
| T-88-05 | Denial of Service | startup when pruning fails | mitigate | `triggarr/db.py:218-224` (listing: `except OSError` -> `logger.warning` -> `return`) and `db.py:230-238` (per-file unlink: `except OSError` -> `logger.warning` -> `continue`), never `raise`. Verified: `test_prune_unlink_failure_logs_warning_and_continues` (line 3018, first-deletion failure), `test_prune_listing_failure_logs_warning` (line 3075), `test_run_migrations_proceeds_when_pruning_fails` (line 3110) — all PASS. | closed |
| T-88-06 | Information Disclosure | pruning log lines | accept | See Accepted Risks Log. Confirmed lines (`db.py:219-223`, `233-237`) are `logger.warning("... {path}: {exc}", path=..., exc=f"{type(exc).__name__}: {exc}")` — no `exc_info`, no `logger.exception`, no traceback; routed through the global redacting sink (`triggarr/logging.py::create_redacting_sink`). | closed (accepted) |
| T-88-07 | Denial of Service | startup with telemetry env vars | mitigate | `tests/test_telemetry.py::test_telemetry_env_vars_do_not_crash_startup` drives the real ASGI lifespan via `with TestClient(app) as client:` after `monkeypatch.setenv(...)` set before `FastAPI(lifespan=...)` construction (lines 36-37 precede line 41). Negative control recorded in `88-02-SUMMARY.md` (Run 1 with simulated crash = FAIL, Run 2 with var removed = PASS). Verified current run: PASS. | closed |
| T-88-08 | Tampering (test integrity) | `tests/test_telemetry.py` | mitigate | Env vars set via `monkeypatch` before `FastAPI()` construction (Pitfall 3/11); `with TestClient(app) as client:` context manager, not a direct lifespan call (Pitfall 2); negative control recorded. Note: two post-SUMMARY review-fix commits (`621aebb0` WR-02, `26899ae4` IN-02) strengthened the committed test to also assert the literal FastAPI warning text and to clear ambient `OTEL_*` vars — an explicit, owner-approved deviation from the PLAN's D-12 "no warning-wording" constraint, recorded in `f0f0ce2c docs(88): owner override keeps WR-02 telemetry wording check (D-12)`. This strengthens rather than weakens the regression guard (the test now fails if FastAPI silently drops the behavior), so the mitigation still holds; flagged here for traceability since it diverges from the PLAN's literal must-have text. | closed |
| T-88-09 | Information Disclosure | OTLP export of request data | mitigate | `uv.lock` contains only `opentelemetry-api` (pulled in transitively by FastAPI for type interfaces); no `opentelemetry-sdk` or `opentelemetry-exporter-otlp*` package is installed (confirmed: `python -c "importlib.util.find_spec('opentelemetry.sdk')"` -> `None`). README states nothing is exported (`README.md:215`). Test endpoint is loopback `127.0.0.1:4318`. `git diff --stat main -- pyproject.toml uv.lock` is empty across the whole phase branch. | closed |
| T-88-10 | Denial of Service | pre-existing update-check job making a network call during lifespan tests | accept | See Accepted Risks Log. | closed (accepted) |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-88-01 | T-88-06 | Pruning WARNING/INFO log lines contain only a backup file path inside the data directory and `type(exc).__name__: exc`; no secrets traverse this code path, output passes through the existing global redacting sink (`triggarr/logging.py`), and no traceback is ever logged (`logger.exception`/`exc_info` are not used in `_prune_timestamped_backups` or `_remove_abandoned_partial_backups`). | Phase 88 PLAN (88-01-PLAN.md threat_model) | 2026-11-16 |
| AR-88-02 | T-88-10 | The lifespan under test schedules Triggarr's existing update-check job, which may attempt a network call during `test_telemetry_env_vars_do_not_crash_startup`'s `TestClient` lifespan dispatch. This is pre-existing, tolerated behavior shared by other lifespan tests in the suite (88-RESEARCH.md Assumption A2); the job's own existing error handler absorbs failures and does not fail the test. | Phase 88 PLAN (88-02-PLAN.md threat_model) | 2026-11-16 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Attack Surface (Informational — WARNING, not a blocker)

Two review-driven changes landed on this branch **after** the PLAN's threat_model block was authored and are not mapped to a Threat ID in the register above:

1. **`_remove_abandoned_partial_backups` (`triggarr/db.py:246-291`)** — a second filesystem-deletion routine added by fix commit `54c67a12` (WR-01 / paired Codex finding F001) that deletes leftover `<stem>.v{current}-backup-<stamp>.partial` staging files left by an interrupted copy. It is structurally identical in its security properties to the already-verified `_prune_timestamped_backups` (T-88-01/T-88-05 pattern): exact-suffix match, ASCII-only stamp regex (`_BACKUP_STAMP_RE`, restricted to `[0-9]` by a later fix `579d734e`/IN-01 round 1), `entry.is_file()` guard, narrow `except OSError` → `logger.warning` → continue, never raises. It is covered by its own tests, all passing: `test_restart_reclaims_abandoned_partials_and_keeps_newest_backups`, `test_stale_partial_removal_failure_logs_warning_and_does_not_block`, `test_failed_partial_cleanup_logs_warning_and_reraises_copy_error`, `test_retry_backup_fits_on_full_disk_after_pre_copy_cleanup`.
2. **Pre-copy pruning reorder** (`run_migrations`, `db.py:338-339`) — pruning now also runs *before* the new timestamped copy (in addition to after), to free space on a nearly-full disk. Same code path, same mitigation pattern as T-88-04/T-88-05.

Both were independently caught and vetted by this repo's own review process (`88-REVIEW.md`, `88-REVIEW-FIX.md`, paired Codex review `codex:e5fcc401380b:a1:F001`) rather than by this audit, and one residual note from that review (IN-01, round 2: the single-process assumption behind partial-file reclamation is documented but not lock-enforced — a second instance on a shared volume could delete another instance's in-progress `.partial` file) was explicitly backlogged by owner ruling, with no valid backup data ever at risk. Recommendation: fold both functions into the PLAN's threat_model as formal Threat IDs (e.g. T-88-11/T-88-12) on the next phase touching `triggarr/db.py`'s backup machinery, so future audits verify them by ID rather than by cross-referencing review artifacts. Not a blocker for this phase: disposition, test coverage, and review evidence already satisfy the same bar as the registered threats.

Also noted, not a gap: `SA-01` in `88-REVIEW.md` (a retry-backup copy failure can still block startup with `ENOSPC` even though the canonical backup is already safe) was explicitly "set aside" for a future owner ruling and is pre-existing behavior outside this phase's BKUP-01/02 scope — not a regression introduced by this phase.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-11-16 | 10 | 10 | 0 | bm-security-auditor |

Verification performed this run:
- `uv run pytest tests/test_db.py tests/test_telemetry.py -q` → 122 passed
- `uv run ruff check triggarr/db.py tests/test_db.py tests/test_telemetry.py` → All checks passed
- `grep -v '^\s*#' triggarr/db.py | grep -c "st_mtime\|getmtime"` → 0
- `git diff --stat main -- pyproject.toml uv.lock` → empty (no new dependency on this branch)
- `python -c "importlib.util.find_spec('opentelemetry.sdk')"` → `None`; `uv.lock` has `opentelemetry-api` only
- README.md:215 placement confirmed between the "Startup-level environment variables" paragraph (line 213) and `## Screenshots` (line 217)
- All 9 PLAN-declared tests located and read in full: `test_backup_bound_holds_through_repeated_failed_attempts`, `test_backup_crash_loop_then_success_keeps_four_files`, `test_prune_orders_by_filename_stamp_not_mtime`, `test_prune_never_deletes_just_written_even_if_clock_went_back`, `test_prune_ignores_other_versions_and_non_matching_names`, `test_prune_logs_one_info_line_per_deleted_backup`, `test_prune_unlink_failure_logs_warning_and_continues`, `test_prune_listing_failure_logs_warning`, `test_run_migrations_proceeds_when_pruning_fails`
- Full phase git history reviewed (`git log --oneline main..HEAD`, 36 commits) to catch mitigations/attack surface added after 88-01-SUMMARY.md/88-02-SUMMARY.md were written (review-fix rounds WR-01/WR-02/IN-01..04/F001)

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-16
