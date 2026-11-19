# Phase 89: Startup & Shutdown Resource Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-18
**Phase:** 89-startup-shutdown-resource-cleanup
**Areas discussed:** Failed-startup log, Shutdown close failure, Hung cleanup cap, How it's proven

---

## Failed-startup log

| Option | Description | Selected |
|--------|-------------|----------|
| Original + 1 summary | Original error first, unchanged; one line saying what was closed | ✓ |
| Original error only | Nothing new unless a cleanup step fails | |
| One line per step | A line per closed item; noisy in a crash loop | |

**User's choice:** Original + 1 summary

| Option | Description | Selected |
|--------|-------------|----------|
| Warning, original wins | Failed cleanup steps logged as warnings; original error stays the cause | ✓ |
| Error level | Cleanup failures logged as errors | |

**User's choice:** Warning, original wins

---

## Shutdown close failure

| Option | Description | Selected |
|--------|-------------|----------|
| App + instance + reason | Error type plus redacted message | ✓ |
| App + instance only | No reason given | |

| Option | Description | Selected |
|--------|-------------|----------|
| Warning | Process exits anyway; consistent with Phase 88 | ✓ |
| Error | Treat as a fault worth attention | |

| Option | Description | Selected |
|--------|-------------|----------|
| No, keep current ending | "Search engine stopped" stays as is | ✓ |
| Yes, add a count | Summary of how many closes failed | |

---

## Hung cleanup cap

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed cap per step | About 5s per close step, constant not setting; warn and move on | ✓ |
| Reuse drain setting | Bound by shutdown_drain_timeout (60s default) | |
| No cap | Today's behavior | |

| Option | Description | Selected |
|--------|-------------|----------|
| No, close properly | No forced exit; fix the leak itself | ✓ |
| Yes, force exit | Last-resort forced exit after the cap | |

---

## How it's proven

| Option | Description | Selected |
|--------|-------------|----------|
| Tests now, image in 92 | In-process tests per failure stage; built image in Phase 92 | ✓ |
| Also a built-image check now | CI check of a failing-upgrade image exiting fast | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, assert it | Test that the aiosqlite worker thread stopped | ✓ |
| Close-called is enough | Only assert close() was called | |

---

## Claude's Discretion

- Mechanism (AsyncExitStack vs tracked try/except), exact cap value and constant name, log wording, scheduler unwind placement, test fixtures; interaction of a timed-out db close with the thread assertion.

## Deferred Ideas

None new; Phase 87 cancellation/close deferrals stay in the maintenance backlog.
