# Project Research Summary

**Project:** Triggarr
**Domain:** Reliability hardening of an existing, shipped single-process daemon (v2.12.1 → v2.14 Reliability)
**Researched:** 2026-11-15
**Confidence:** HIGH

## Executive Summary

v2.14 is not a build-something-new milestone — it's a "make six already-identified bugs stop happening" milestone. All four researchers independently read the actual Triggarr source (not just the feature descriptions) and confirmed, with exact file and line numbers, that five of the six target defects are real and present in the code today: removing an instance can corrupt in-memory state if the disk write fails; a crashed startup leaks database and network connections; a crashed shutdown can abandon cleanup partway through; search commands can be silently duplicated after a network timeout; and pre-upgrade database backups accumulate without limit during a crash loop. The sixth item — the telemetry environment variable — was already fixed upstream and verified live before this milestone started; what's left for it is a regression test and a documentation note, not a code fix. None of the six needs a new library: every fix reuses a pattern that already exists elsewhere in this same codebase (the correct "validate, write to disk, then update memory" order used by three of four settings routes; the existing "frozen legacy row" labeling pattern; httpx's own built-in connect-retry transport).

The recommended approach is: fix the smallest, most isolated bugs first (settings-write ordering, corrupt state-file recovery, bounded backups, the telemetry regression test), prove the "fix the order of operations, don't add new machinery" pattern works cleanly on those, and only then move to the two riskier, higher-blast-radius items — resource cleanup on startup/shutdown (touches one function used by every request) and the search-retry/duplicate-command logic (touches the shared HTTP client used by all three *arr apps and the pass/fail counter that decides when Triggarr reports itself unhealthy). The removed-Sonarr-instance cleanup work depends on the settings-write fix landing first, because both touch the same route.

The main risk is not "will the fix work" — the fixes themselves are small and well-precedented. The risk is in three places that need the owner's judgment, not just code: (1) how a search command with no confirmed outcome ("did the *arr receive it or not?") should count toward the health/failure tracking that already exists; (2) whether to spend extra effort actually asking the *arr app to confirm a shaky command landed, versus just flagging it as "unknown" and moving on; and (3) exactly how "this backup is old, delete it" and "this instance's leftover search is from a removed instance" should look to a user browsing history. These are flagged explicitly below as open product decisions, not resolved by research, because they're judgment calls about what's honest and useful to show, not technical unknowns.

## Key Findings

### Recommended Stack

No new dependency, runtime or dev, is needed for any of the six capabilities — confirmed against the actual lockfile and the actual installed library source, not assumed. Every fix is "use a tool that's already in the box, correctly," not "add a tool." That matches the milestone's own "no new dependencies" ground rule exactly.

**Core technologies already in place, used differently:**
- `contextlib.AsyncExitStack` (Python stdlib) — for closing whatever a half-finished startup already opened. Not currently used; needs to be added around the startup/shutdown code.
- httpx's own exception types (already a dependency) — `ConnectError`/`ConnectTimeout` mean "never left the client, safe to retry"; `ReadTimeout`/`WriteTimeout`/etc. mean "might have reached the server, do not resend." The code today treats all of these the same way (always retry), which is the bug.
- `httpx.AsyncHTTPTransport(retries=N)` — a built-in, already-shipped feature of the HTTP library that retries only the genuinely-safe case, as a drop-in replacement for part of today's hand-rolled retry.
- Plain `pathlib`/`os` file operations (stdlib) — for pruning old backup files, the same way the database already prunes old history rows.
- Plain SQL, reusing the existing "frozen legacy row" table-and-flag pattern already shipped in v2.12 for a structurally identical problem (orphaned Sonarr rows from the attribution cutover).

**Explicitly rejected as unneeded** (per STACK.md's "What NOT to Add"): a generic retry library like `tenacity`, a backup-rotation package, `asyncio.TaskGroup` for shutdown cleanup (its all-or-nothing failure behavior is the wrong tool for "best-effort, keep going" cleanup — see Pitfall 8 below), and any OpenTelemetry SDK/exporter.

### Expected Features

This milestone has no new user-facing feature — it's entirely "the app should behave correctly when something goes wrong," restated as scope:

**Must have (table stakes — all eight are "Active" requirements in PROJECT.md):**
- Removing an instance never leaves settings, the schedule, and the live connection disagreeing with each other if the disk write fails
- A corrupted-but-still-valid state file (e.g. `[]` or `42` instead of the expected object) recovers to defaults instead of crashing startup
- A startup that fails partway through closes whatever database connection and HTTP connections it already opened
- A shutdown where one connection fails to close doesn't stop every other connection — and the database — from closing too
- A search command that times out waiting for a reply is never blindly resent as a second, possibly-duplicate search
- There's a distinguishable "we don't know if that landed" result, separate from both "it worked" and "it failed"
- Backup copies of the database made before an upgrade attempt stop piling up without limit during a crash loop
- A removed Sonarr instance's leftover, never-resolved pending searches get a defined, visible end state instead of sitting invisibly forever

**Should have (useful follow-ons, not required for "done"):**
- Actually asking Radarr/Sonarr/Lidarr afterward whether an ambiguous command landed, instead of just flagging it unknown and moving on
- A small defense-in-depth guard making the existing (already-correct) instance-identity isolation explicit at the query level too

**Defer / explicitly do not build:**
- Claiming the fix guarantees a search is never duplicated ("exactly once") — it can't be guaranteed, only made much less likely, and the research is explicit that this must never be oversold
- A generic, configurable retry framework
- Automatically re-sending an "unknown" command later, which would reintroduce the exact duplicate-search risk this milestone exists to close
- A new user-facing scheduled-backup feature (only the existing upgrade-backup needs a cap)
- Deleting or quietly reassigning a removed instance's old search history

### Architecture Approach

Triggarr is one Python process: a FastAPI web app plus an APScheduler background scheduler, both sharing one SQLite database connection and one long-lived HTTP client per connected *arr instance. All six bugs live inside that same tight neighborhood of code — a single instance-removal function, a single startup/shutdown function, a single shared HTTP retry helper, a single migration-backup function, and the database queries that track "has this search been checked yet." Nothing in this milestone requires restructuring that shape; every fix is a local correction to one function's order of operations or exception handling, not a new component.

**Major components touched:**
1. `routes.py::remove_instance` — the one settings-change route that doesn't already follow the safe "write to disk, then update memory" order used everywhere else in that file
2. `scheduler.py::create_lifespan` — owns opening the database and HTTP connections at startup and closing them at shutdown; currently has no safety net if either half fails partway
3. `clients/base.py` + `search/engine.py` — the shared HTTP retry logic and the code that decides whether a search attempt counts as accepted or failed
4. `db.py::run_migrations` — makes a backup copy of the database before every upgrade attempt; never deletes old ones
5. `db.py` / `tracking.py` — tracks which searches are still "pending" per instance; has no process for an instance that no longer exists

### Critical Pitfalls

1. **Treating "the response got lost" the same as "the request never went out"** — a search command that times out waiting for a reply may well have already reached Radarr/Sonarr/Lidarr; resending it is what causes the duplicate search. Fix: only treat a connection failure that happened *before* sending as safe to retry.
2. **Papering over "we don't know" by counting it as a failure** — doing that would make a flaky network connection look like a real problem and could trip the "too many failures, mark unhealthy" alarm for no real reason. Fix: give "unknown" its own bucket that doesn't feed that alarm.
3. **Fixing the logging code instead of the decision code** — the function that cleans up error messages for safe display already throws away the distinction needed to decide whether to retry; the retry decision has to happen before that cleanup, not after.
4. **"It still throws an exception" is not proof a leak was fixed** — for the startup/shutdown fixes, a test has to show the database/network connection was actually closed, not just that the original error still surfaces.
5. **An unclosed database connection doesn't just "leak a little memory"** — it leaves a background thread running that never stops on its own, which can make the whole container hang on restart instead of failing fast, turning a quick recovery into Docker forcibly killing it after a long wait, every single restart, until fixed.

## Confirmed Defect Status (read directly from the current code, not assumed)

| # | Item | Status |
|---|------|--------|
| 1 | Settings-write ordering on instance removal | **CONFIRMED PRESENT** — `routes.py:937-995`. The in-memory settings dict is mutated *before* the disk write is attempted; three sibling routes in the same file already do this safely (write first, then update memory) and this one is the outlier. |
| 2 | Non-object state file (`[]`, `42`, `null`) crashes startup | **CONFIRMED PRESENT** — `state.py:210-245`. Already self-documented as a known, accepted gap in the test suite (`test_state_wrong_structure_list_crashes`), whose own comment says to flip the assertion once fixed. |
| 3 | Failed startup leaks the database/HTTP connections it opened | **CONFIRMED PRESENT** — `scheduler.py:460-667`. No safety net exists before the point where cleanup code lives; an error anywhere in setup skips cleanup entirely. |
| 4 | One connection's close failure blocks every other connection — and the database — from closing | **CONFIRMED PRESENT** — `scheduler.py:747-753`. A plain loop with no per-item error handling. |
| 5 | Search commands retried blindly after a timeout | **CONFIRMED PRESENT** — `clients/base.py:64-99`. One retry helper is shared by read requests (safe to retry) and search commands (not safe), with no distinction. |
| 6 | Pre-upgrade database backups pile up without limit | **CONFIRMED PRESENT** — `db.py:172-236`. Every failed upgrade attempt during a crash loop writes a new backup file; nothing ever deletes an old one. |
| 7 | Removed instance's leftover pending searches | **CONFIRMED PRESENT, but narrower than it sounds** — the part that matters most (never crediting a search to the wrong instance) *already works correctly today*; what's missing is only that the leftover rows have no defined end state and look, in the history view, indistinguishable from a search that's still genuinely in progress. |
| 8 | **SA-12 telemetry variable (`FASTAPI_OTEL_AUTO_CONFIGURE`)** | **ALREADY FIXED, verified live.** This was corrected on 2026-11-14, before this milestone started: the installed FastAPI version already catches its own telemetry setup error internally and logs a warning instead of crashing. Confirmed by building and running the actual image with the variable set — the app started and served requests normally. **Nothing to fix in code.** What's left is pinning this down with a permanent automated test (so a future FastAPI upgrade can't silently reintroduce the crash) and one documentation sentence noting Triggarr doesn't actually export any telemetry even if this variable is set. |
| — | **aiosqlite cursor-lifetime issue** (mentioned in the roadmap wording as something to "correct locally if confirmed") | **NOT FOUND.** The researchers who read this code found no such defect; none was looking for it exhaustively, so re-check at phase planning. This line item should be treated as closed/not-applicable rather than carried forward as outstanding work, unless something surfaces during the phase itself. |

## Implications for Roadmap

Based on combined research, the suggested build order groups work by blast radius and by genuine dependency, not by which items are individually "bigger":

### Phase 1: Settings & state-file safety
**Rationale:** Smallest, most isolated fixes; both are "correct a backwards order of operations," a pattern already proven correct elsewhere in the same file. Doing this first also means the removed-Sonarr-instance work (Phase 5) builds on the already-fixed version of the removal route, not the buggy one.
**Delivers:** Removing an instance can no longer corrupt in-memory state on a failed disk write; a corrupted-but-valid state file recovers to defaults instead of crashing.
**Addresses:** Target capabilities 1 and 2 above.
**Avoids:** Pitfalls 4 and 5 (write-before-mutate; non-dict state crash).

### Phase 2: Bounded upgrade backups + telemetry regression test
**Rationale:** Both are small, fully independent, and low-risk; natural to batch together as "narrow, no cross-component coordination" work. The telemetry item needs no code fix at all, only a test and a doc note.
**Delivers:** Pre-upgrade backups stop accumulating without limit; a permanent automated check that the telemetry env var can never again crash startup.
**Addresses:** Target capabilities 6 and 8 above.
**Avoids:** Pitfall 9 (backup pruning must never delete the one backup that predates every failed attempt, and must not sort by file-modified-time, which is unreliable here) and Pitfall 11 (don't pin the test to FastAPI's internal wording).

### Phase 3: Startup/shutdown connection cleanup
**Rationale:** Self-contained to one function (the part of the code that opens the database and network connections at startup and closes them at shutdown), but touches more existing tests than Phases 1-2, so it's sequenced after the simpler pattern is already proven in this codebase.
**Delivers:** A startup that fails partway closes what it already opened; a shutdown where one connection fails to close doesn't block the rest.
**Addresses:** Target capabilities 3 and 4 above.
**Avoids:** Pitfalls 6, 7, and 8 (leaked connections can hang the whole container on restart; don't reach for `asyncio.TaskGroup` for this — its all-or-nothing behavior is the wrong tool for "keep closing the rest even if one fails").
**Must stay together:** The startup half and shutdown half are two sides of one function and should land in the same phase/commit, even though they're logically separate fixes — splitting them risks leaving one half's tests referencing code the other half hasn't touched yet.

### Phase 4: Removed-instance pending-search lifecycle
**Rationale:** Depends on Phase 1's fixed removal route — the natural place to decide "what happens to this instance's leftover searches" is inside that same already-corrected function.
**Delivers:** A removed instance's never-resolved pending searches get a visible, defined end state instead of looking like an in-progress search forever.
**Addresses:** Target capability 7 above.
**Avoids:** Pitfall 10 — do not reuse the existing "Legacy" label from the unrelated v2.12 attribution-cutover feature (it means something different); do not select or label these rows by instance *name* instead of the instance's permanent internal ID (that would reopen the exact cross-instance mixup this feature exists to prevent).

### Phase 5: Search-command retry/delivery-confidence
**Rationale:** The largest blast radius of the six — the retry logic is shared by all three connected apps (Radarr/Sonarr/Lidarr), and the pass/fail tracking it feeds is read by the "mark this instance unhealthy" counter and the dashboard. Sequenced last so the "make a narrow, well-tested behavior change without breaking what already works" pattern has the most practice behind it, and because nothing else in the milestone depends on this landing earlier.
**Delivers:** A timed-out search command is never blindly resent; there's a third, distinguishable result ("don't know if it landed") separate from success/failure.
**Addresses:** Target capability 5 above.
**Avoids:** Pitfalls 1, 2, and 3 (don't treat "lost the reply" the same as "never sent"; don't let "unknown" quietly inflate either the success count or the failure/unhealthy counter; make the retry decision from the real error, before it's cleaned up for logging).
**Must stay together:** The retry-safety fix and the new "unknown" result bucket are two parts of one change — there's no point separating them, because the retry fix is what first creates a case the "unknown" bucket needs to receive.

### Phase 6 (cross-cutting, do last): Built-image smoke-test extension
**Rationale:** Best done once the actual fixes exist, so the smoke test demonstrates real behavior rather than being written ahead of it. Reuses the project's existing container-restart-and-recovery test harness; needs no new tooling, just a couple of added scenarios (corrupt the state file before a restart; simulate more than one failed upgrade attempt in a row).
**Avoids:** Pitfall 12 — this test only proves something if it injects a real failure and uses the harness's existing dynamic-port/unique-name/poll-until-ready conventions; it proves nothing if it just restarts an already-healthy container.

### Phase Ordering Rationale

- Smallest/most isolated fixes first (Phases 1-2) establish the "reorder, don't rebuild" pattern cleanly before it's applied to busier code.
- Phase 4 is sequenced after Phase 1 because it's a genuine dependency: both touch the same removal route.
- Phases 3 and 5 are each self-contained but carry the most risk (shared code, more existing tests to keep passing), so they're sequenced later — not because they're bigger, but because nothing forces them earlier.
- The smoke-test phase is last by design: it should validate real fixes, not anticipate them.

### Research Flags

Needs a product/requirements decision before (or very early in) planning, not just engineering judgment — see "Open Product Decisions for the Owner" below:
- **Phase 5 (search-command delivery):** the grading question and whether to add a confirm-afterward step are genuine open decisions, not resolved by research.
- **Phase 2 (backups):** the exact shape of the cap (how many backups, or how old) is an open decision.
- **Phase 4 (removed-instance rows):** the exact wording/labeling an owner wants a user to see is an open decision.

Standard patterns, safe to plan without additional research:
- **Phase 1:** mechanical reordering, already proven correct three other times in the same file.
- **Phase 3:** stdlib-only cleanup pattern (`AsyncExitStack` or equivalent try/except), well-precedented elsewhere in this codebase.
- **Phase 6:** extends an existing, already-working test harness.

## Open Product Decisions for the Owner

These are the four points every researcher flagged as needing the owner's judgment, not just an engineering call. None of them blocks starting the earlier phases, but all four should be settled before Phase 5 (and, for the backup/labeling ones, before Phases 2 and 4) is planned in detail:

1. **How should an "unconfirmed delivery" search command be graded, and should it count toward the consecutive-failure counter?** When a search command times out waiting for a reply, Triggarr genuinely cannot tell whether Radarr/Sonarr/Lidarr already started that search. Today that case is counted as a hard failure. The fix needs a third bucket ("unknown"), but then: does an unknown result count toward the counter that currently escalates a dashboard card to "unhealthy" after enough consecutive failures? Counting it risks flagging an instance as broken over what might just be a slow network blip; not counting it risks hiding a real, recurring problem. This also determines what a cycle where *every* command came back "unknown" should be graded as overall.

2. **Should Triggarr go one step further and actually ask the *arr app afterward whether an ambiguous command landed?** Radarr/Sonarr/Lidarr expose a status-check endpoint that could confirm a shaky command without resending it — turning "unknown" into a real confirmed answer. This is real, extra work (a new round-trip, its own timeout handling, remembering the command's ID across a search cycle) and is not required to meet this milestone's stated "done" bar. The research flags it as a clean, worthwhile follow-on rather than something to assume ships now — worth a yes/no/defer decision.

3. **What shape should the backup limit take — keep the last N copies, or keep anything from the last N days?** Either is reasonable and small to build; the one hard constraint (not a choice) is that the very first backup taken before any failed attempt must never be deleted by the cap, because it's the one safe restore point the app's own error message points to during a crash loop.

4. **How should a removed instance's leftover, never-resolved searches look to someone browsing history?** The underlying safety property (never crediting a search to the wrong instance) already works correctly and isn't at risk either way. What's open is presentation: what label/wording should these rows carry so they read as "this will never be checked again" rather than looking like a search still quietly in progress — and whether that's worth a visual distinction at all versus a one-line note.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every version claim is read directly from the lockfile; every behavioral claim about httpx, the web framework's startup/shutdown handling, and the database library is verified against the exact installed source code, not general knowledge. |
| Features | HIGH | Every defect claim is grounded in an exact file-and-line read of the current code; the comparison to how Radarr/Sonarr/Lidarr themselves handle duplicate commands and backups is read directly from their own source and official documentation. A few comparable-tool observations (a retired, similar community project) are explicitly marked lower-confidence and don't drive any recommendation on their own. |
| Architecture | HIGH | Every finding is traced to exact file/line in the current codebase; this research file explicitly supersedes a stale, months-old version that no longer matched the shipped code. |
| Pitfalls | HIGH | Grounded in the current code, Triggarr's own existing tests (including one prior test that already proves a related real-world failure mode), and the installed libraries' own source. The design-judgment pitfalls (how to grade an "unknown" result) are flagged as open decisions rather than asserted as settled, which is itself the honest position. |

**Overall confidence:** HIGH

### Gaps to Address

- The aiosqlite "cursor-lifetime" concern named in the roadmap wording was not found by the researchers who read that code; re-check briefly at phase planning before treating it as not applicable.
- The four open product decisions listed above are not gaps in the research — they're genuine judgment calls — but they do need an owner answer recorded before Phase 5 (and, in smaller ways, Phases 2 and 4) is planned in full detail.
- One naming/documentation detail — exactly which existing counter or UI field should display the new "unknown delivery" results — is left as a requirements-time decision rather than resolved here, consistent with how the research treats it.

## Sources

### Primary (HIGH confidence — read directly from the installed codebase and libraries)
- `triggarr/web/routes.py`, `triggarr/state.py`, `triggarr/search/scheduler.py`, `triggarr/clients/base.py`, `triggarr/clients/radarr.py`, `triggarr/clients/sonarr.py`, `triggarr/clients/lidarr.py`, `triggarr/search/engine.py`, `triggarr/search/outcome.py`, `triggarr/db.py`, `triggarr/tracking.py`, `triggarr/models/config.py`, `triggarr/config.py`, `triggarr/startup.py` — current behavior and defect confirmation
- `tests/test_clients.py`, `tests/test_state.py`, `tests/test_web.py`, `tests/test_scheduler.py`, `tests/test_migration_v10_atomic.py`, `tests/harness/image_smoke.py`, `tests/harness/stack.py` — existing coverage gaps and reusable test/harness patterns
- Installed package source read directly: `httpx` 0.28.1, `starlette` 1.10.0, `fastapi` 0.162.4, `aiosqlite` 0.22.1, `apscheduler` 3.11.3, CPython `contextlib` — exact version-matched behavior, not assumed from general knowledge
- `uv.lock`, `pyproject.toml` — all pinned dependency versions
- `.planning/PROJECT.md`, `.planning/backlog/MAINTENANCE.md` — milestone scope, the prior SA-12 correction record, and the bugs-005 removed-instance backlog note

### Secondary (HIGH confidence, external official sources fetched directly)
- Radarr/Sonarr/Lidarr official `CommandQueueManager.cs` source (all three apps, `develop` branch) — confirms how the *arr apps themselves deduplicate a repeated command, and the limits of that protection
- Servarr Wiki official documentation source — confirms the *arr apps' own backup interval/retention defaults and pruning behavior
- Official httpx documentation — confirms the exception hierarchy and httpx's own recommendation to use its built-in connect-only retry rather than a general retry framework
- Official Python `contextlib` documentation — confirms `AsyncExitStack`'s cleanup-on-partial-failure contract

### Tertiary (MEDIUM confidence, used only to corroborate, not as the basis for any recommendation)
- Community tooling notes on a now-retired project with a similar status-polling design
- General industry writing on handling a timed-out write request (the three-state confirmed-success/confirmed-failure/unknown framing)

---
*Research completed: 2026-11-15*
*Ready for roadmap: yes*
