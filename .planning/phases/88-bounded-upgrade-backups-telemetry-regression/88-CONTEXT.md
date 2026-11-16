# Phase 88: Bounded Upgrade Backups & Telemetry Regression - Context

**Gathered:** 2026-11-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Pre-upgrade database backups taken by `run_migrations` stay bounded through a crash-looping failed upgrade (the original pre-upgrade backup plus at most the 3 most recent later ones), and a permanent automated test pins that Triggarr starts and serves requests with `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint set. The README states that telemetry export is unsupported. The telemetry crash itself is already fixed upstream (FastAPI catches its own setup error), so there is no telemetry code fix. Built-image recovery checks belong to Phase 92. Requirements: BKUP-01, BKUP-02, TELEM-01, TELEM-02.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (milestone standing rules and locked requirements, not re-asked)
- **D-01:** No new runtime dependency (no backup-rotation package, no OpenTelemetry SDK/exporter). Use stdlib `pathlib`/`os`. Each fix lands with a regression test that fails on the unfixed code.
- **D-02:** Cap shape (BKUP-01, locked): the canonical original backup `<db>.v{current}-backup` is always kept, plus at most the 3 most recent timestamped retry backups `<db>.v{current}-backup-{stamp}` for the same `current` version.
- **D-03:** (BKUP-02, locked) Pruning never removes the canonical original or the backup just written. Order is decided by the `%Y%m%dT%H%M%S%fZ` timestamp parsed from the file name, never by file mtime (`shutil.copy2` copies the source db's mtime; research PITFALLS.md Pitfall 9). Pruning runs after the new backup is written, so `earliest_backup` (used in the "restore from ..." recovery log line) is never invalidated.
- **D-04:** (BKUP-02, locked) A pruning failure is logged and never blocks startup or the migration attempt.
- **D-05:** The bound is proven by a test with three or more (e.g. 5+) consecutive failed attempts from the same `current` version, not just one extra attempt.

### After the upgrade succeeds
- **D-06:** Nothing is deleted when an upgrade finally succeeds. The original plus up to 3 retry copies stay on disk; the cap only acts while attempts keep failing. No new delete step on the success path.
- **D-07:** Backups from earlier, already-completed upgrades (other `v{N}` versions) are never touched. Pruning is scoped to the timestamped siblings of the current `v{current}` only. Files whose names don't match the exact timestamped pattern (e.g. user-made copies) are never deleted.

### Logging
- **D-08:** Each deleted retry backup gets one info-level log line naming the file, stating that the original and the 3 most recent are kept.
- **D-09:** A failed deletion logs one warning-level line naming the backup file and the system reason (exception type / OS reason, redacted by the existing sink); startup continues. Not error level, so it is not mistaken for the migration failure that caused the crash loop.

### Telemetry documentation
- **D-10:** The note goes in README.md, Configuration Reference, directly after the existing "Startup-level environment variables such as `TRIGGARR_CONFIG_DIR`..." paragraph. No new section.
- **D-11:** Wording conveys both points: Triggarr does not support OpenTelemetry export; setting `FASTAPI_OTEL_AUTO_CONFIGURE` or an OTLP endpoint does not stop Triggarr from starting, but nothing is exported.

### Telemetry regression test
- **D-12:** An in-process pytest test in this phase only: start the real app (lifespan) with `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint set via `monkeypatch.setenv` (never raw `os.environ`), assert startup completes and `/health` responds. Assert the outcome, never FastAPI's internal warning wording (Pitfall 11). No built-image check in this phase.

### Claude's Discretion
- Where the pruning helper lives (inside `run_migrations` or a small private helper in `db.py`) and how timestamps are parsed.
- Exact wording of the D-08/D-09 log lines and D-11 README sentence, within the constraints above.
- Which OTLP endpoint variable(s) the test sets (e.g. `OTEL_EXPORTER_OTLP_ENDPOINT`) and what value the variable takes, as long as the configuration that originally crashed (SA-12) is reproduced.
- Test structure and fixtures, following existing patterns in `tests/test_db.py` and `tests/test_scheduler.py`.

</decisions>

<specifics>
## Specific Ideas

- Crash-loop example used in discussion: an upgrade from schema v9 fails 5 times and succeeds on try 6. Expected disk state afterwards is 4 files: the v9 original plus 3 retry copies, all kept.
- Disk use per upgrade is bounded and predictable (at most 4 copies), which was the owner's reason for not adding cleanup on success.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — BKUP-01, BKUP-02, TELEM-01, TELEM-02 (exact requirement text)
- `.planning/ROADMAP.md` §"Phase 88" — goal and success criteria

### Research
- `.planning/research/PITFALLS.md` §"Pitfall 9" — never prune the canonical backup; never order by mtime; prune after writing; test 3+ attempts
- `.planning/research/PITFALLS.md` §"Pitfall 11" — telemetry test must not pin FastAPI wording or leak env vars
- `.planning/research/SUMMARY.md` — item 6 (backups, `db.py:172-236`) and item 8 (SA-12 already fixed, verified live 2026-11-14)
- `.planning/research/STACK.md` — "What NOT to Add" (no rotation package, no OTel SDK)

### Prior phase
- `.planning/phases/87-settings-state-file-safety/87-CONTEXT.md` — D-08/D-11 set-aside pattern (bounded single copy; failure logged, never blocks startup), the closest precedent

### Project conventions
- `CLAUDE.md` — Loguru with redacting sink, atomic writes, pytest-asyncio auto mode, review workflow
- `docs/PLANNING-FORMAT.md` — planning file format for STATE/ROADMAP updates

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/db.py::run_migrations` (around lines 172-236): already writes the canonical `.v{current}-backup` once and timestamped `.v{current}-backup-{stamp}` siblings on later attempts; `stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")`. Pruning slots in right after the timestamped `shutil.copy2`.
- `triggarr/db.py::_apply_atomic_migration`: logs "restore from {backup}" using `earliest_backup`, which must keep pointing at an existing file.

### Established Patterns
- Tests call the lifespan directly: `async with lifespan_fn(app): ...` (`tests/test_scheduler.py` around lines 974-998); env-var tests use `monkeypatch.setenv` (e.g. `test_drain_timeout_env_overrides_configured`).
- Backup tests already exist in `tests/test_db.py` (`test_backup_created_on_migration` ~line 383, `test_run_migrations_fresh_install` ~line 1082): extend them for the multi-attempt bound.
- Phase 87 set-aside logic: bounded copies, failure logged, startup never blocked.

### Integration Points
- `run_migrations` is called from the app lifespan at startup; a crash loop is the container restart policy calling it repeatedly while `current < target`.
- README.md Configuration Reference, paragraph on startup-level environment variables (end of section, before "## Screenshots").

</code_context>

<deferred>
## Deferred Ideas

- Cleaning up backups from earlier, already-completed upgrades (one file per past schema upgrade, never deleted today). Owner chose to leave them alone; not added to the backlog.
- Built-image proof that the telemetry variables don't break startup: Phase 92's built-image smoke checks could set these variables too, if wanted then (not committed scope).

</deferred>

---

*Phase: 88-bounded-upgrade-backups-telemetry-regression*
*Context gathered: 2026-11-15*
