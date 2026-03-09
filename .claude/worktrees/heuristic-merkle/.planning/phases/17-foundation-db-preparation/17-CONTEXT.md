# Phase 17: Foundation & DB Preparation - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Database and config infrastructure that downstream tracking phases depend on. Delivers: WAL mode with shared connection, search history schema additions (item ID, season number, missing episode count), configurable settings (tracking window, timeout, pageSize, max rows), pruning logic that preserves pending rows, and a lifetime_stats table. No tracking logic, no UI changes, no polling — those are Phases 19-21.

</domain>

<decisions>
## Implementation Decisions

### lifetime_stats table shape
- Four counters: movies_found, movies_updated, episodes_found, episodes_updated
- One row per app (Radarr row + Sonarr row), keyed by app name
- Includes a last_reset_at timestamp column so the dashboard can show "Stats since [date]"
- Users can reset stats via a settings button (zeroes counters, updates last_reset_at)

### Pruning behavior
- Pending rows (outcome='searched') are exempt from pruning — always kept until they resolve
- No hard ceiling on pending rows; they stay until tracking resolves them
- Pruning runs after each search cycle (not on startup, not on a separate schedule)
- Default max_rows = 1000
- Existing v1.x rows (which lack the outcome column) are backfilled as 'unresolved' during migration, making them immediately eligible for pruning

### Migration strategy
- Auto-migrate on startup: app detects schema version and runs needed changes automatically
- Schema version tracked in a dedicated meta table (integer version, compare on startup)
- Back up the DB file before migrating (copy to fetcharr.db.v1-backup or similar)
- Log each migration step via Loguru so users see "Migrating schema v1 -> v2: adding outcome column..." in Docker logs

### Claude's Discretion
- Config defaults for tracking window, request timeout, and pageSize (researcher/planner can determine sensible values)
- Exact schema_version table design
- Backup file naming convention
- WAL mode activation approach (PRAGMA on connection init)

</decisions>

<specifics>
## Specific Ideas

- Migration should be transparent in Docker logs — users pulling a new image should see exactly what changed on first startup
- Backup-before-migrate pattern gives users a safety net without requiring manual steps
- Stats reset is a user-facing feature (button in settings), not just a DB operation

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-foundation-db-preparation*
*Context gathered: 2026-02-24*
