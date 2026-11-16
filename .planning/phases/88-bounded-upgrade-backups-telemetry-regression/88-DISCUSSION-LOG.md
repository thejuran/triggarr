# Phase 88: Bounded Upgrade Backups & Telemetry Regression - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 88-CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-11-15
**Phase:** 88-bounded-upgrade-backups-telemetry-regression
**Areas discussed:** After the upgrade succeeds, What the log says, Telemetry doc note, Telemetry test strength
**Pre-answered (not asked):** cap shape (original + 3 most recent, BKUP-01), timestamp-name ordering and never pruning the original or the just-written file (BKUP-02, research Pitfall 9).

## After the upgrade succeeds

| Option | Selected |
|---|---|
| Keep all 4 (original + up to 3 retries); nothing deleted on success | ✓ |
| Keep original, drop retry copies after success | |
| Keep the newest only (breaks the always-keep-original rule) | |

| Option (backups from earlier completed upgrades) | Selected |
|---|---|
| Leave them; note as a deferred idea | ✓ |
| Leave them and add a MAINTENANCE.md backlog item | |

## What the log says

| Option (normal deletion) | Selected |
|---|---|
| One info line per deleted file | ✓ |
| One summary line | |
| Silent unless it fails | |

| Option (failed deletion) | Selected |
|---|---|
| Warning, startup continues | ✓ |
| Error, startup continues | |

## Telemetry doc note

| Option (placement) | Selected |
|---|---|
| README, after the startup env vars paragraph | ✓ |
| New README "Telemetry" section | |

| Option (wording) | Selected |
|---|---|
| Unsupported + harmless (names the variable; startup unaffected; nothing exported) | ✓ |
| Unsupported only | |

## Telemetry test strength

| Option | Selected |
|---|---|
| In-process test now | ✓ |
| Also on the built image now | |
| In-process now, built image in Phase 92 | |

## Claude's Discretion

- Pruning helper placement and timestamp parsing; exact log/README wording; which OTLP variable(s) the test sets; test structure.

## Deferred Ideas

- Cleanup of backups from earlier completed upgrades (not backlogged, by owner choice).
- Telemetry variables in Phase 92's built-image smoke check (optional, not committed).
