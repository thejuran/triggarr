# Requirements: Fetcharr

**Defined:** 2026-02-24
**Core Value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, without exposing credentials or expanding attack surface.

## v2.0 Requirements

Requirements for v2.0 Closed-Loop Tracking milestone. Each maps to roadmap phases.

### Download Tracking

- [x] **TRACK-01**: System polls Radarr history endpoint after searches to detect grab events for searched items
- [x] **TRACK-02**: System polls Sonarr history endpoint after searches to detect grab events for searched items
- [x] **TRACK-03**: System correlates grabs to fetcharr-triggered searches via timestamp + item ID window matching
- [x] **TRACK-04**: Search history entries update from "searched" to "grabbed" when all wanted items are resolved
- [x] **TRACK-05**: Search history entries update to "partial" when some but not all missing episodes are grabbed (Sonarr), or quality still below cutoff
- [x] **TRACK-06**: Search history entries resolve to "unresolved" when tracking window expires with no grabs detected
- [x] **TRACK-07**: User can configure tracking window duration and poll interval via settings
- [x] **TRACK-08**: System stores item IDs and expected missing counts at search time for correlation

### Dashboard Stats

- [x] **STATS-01**: Dashboard shows aggregate search effectiveness (searched-to-grabbed rate)
- [x] **STATS-02**: Dashboard shows per-app effectiveness breakdown (Radarr vs Sonarr grab rates)
- [x] **STATS-03**: Dashboard shows lifetime stats: movies found, movies updated (fetcharr-triggered only)
- [x] **STATS-04**: Dashboard shows lifetime stats: episodes found, episodes updated (fetcharr-triggered only)
- [x] **STATS-05**: Dashboard shows time-to-grab metric (average time from search to grab)

### Tech Debt

- [x] **DEBT-01**: Rate limiting on search-now endpoint
- [x] **DEBT-02**: CSRF protection on settings POST verified/hardened
- [x] **DEBT-03**: Configurable max rows for search history table (bounded growth)
- [x] **DEBT-04**: Persistent SQLite connection with WAL mode (replaces connection-per-operation)
- [x] **DEBT-05**: Health check endpoint for container orchestrators
- [x] **DEBT-06**: Graceful shutdown handler (close scheduler, clients, DB, flush logs)
- [x] **DEBT-07**: Configurable request timeout on outbound HTTP calls
- [x] **DEBT-08**: Configurable pageSize for *arr API pagination

### Deep Review — Security & Safety

- [x] **DRSEC-01**: row_factory mutation on shared DB connection uses try/finally or cursor-level scoping to prevent async race
- [x] **DRSEC-02**: Template URL attributes use urlencode filter to prevent reflected XSS via search_text
- [x] **DRSEC-03**: Rate limiter re-checks timestamp inside search_lock to prevent check-then-act race
- [x] **DRSEC-04**: Migration backup guarded with path.exists() to prevent FileNotFoundError on fresh installs
- [x] **DRSEC-05**: Migration v1 DEFAULT changed from NULL to 'searched' so v4 backfill only catches truly pre-v1 rows
- [x] **DRSEC-06**: contextlib.suppress(Exception) narrowed to sqlite3.OperationalError in migration functions
- [x] **DRSEC-07**: Exception details in search history sanitized (type-based summary instead of raw str(exc))
- [x] **DRSEC-08**: sourceTitle in tracking detail field truncated to 200 chars (defense-in-depth)

### Deep Review — Code Quality

- [x] **DRQUAL-01**: run_tracking_check and helpers have full type annotations (db, clients, matched_grabs)
- [x] **DRQUAL-02**: Pass counter default changed from 1 to 0 so first wrap-around logs "pass 1" not "pass 2"
- [x] **DRQUAL-03**: Tracking exception handler in scheduler uses specific types instead of bare except Exception
- [x] **DRQUAL-04**: Duplicate tracking log removed — single log point in scheduler or tracking, not both
- [x] **DRQUAL-05**: SearchRecord enforces timezone-aware datetime via __post_init__ validation
- [x] **DRQUAL-06**: `missing_count or 0` replaced with explicit None check to avoid conflating 0 and None
- [x] **DRQUAL-07**: Migration loop uses sorted(MIGRATIONS.keys()) to prevent KeyError on version gaps
- [x] **DRQUAL-08**: _sonarr_outcome restructured to handle expected==0 at top, eliminating dead branch
- [x] **DRQUAL-09**: get_schema_version uses async with for cursor (consistent with rest of db.py)
- [x] **DRQUAL-10**: Ruff I001 import sort violation fixed in tests/test_db.py
- [x] **DRQUAL-11**: tracking_poll_seconds config renamed or removed (currently has no effect)
- [x] **DRQUAL-12**: at_least_one_search_count model validator reinstated on ArrConfig

## Future Requirements

Deferred to v2.1+. Tracked but not in current roadmap.

### Tracking Enhancements

- **TRKE-01**: Grab source metadata display (quality, indexer name) per search entry
- **TRKE-02**: Dashboard sparkline/chart for grab rate trend over time
- **TRKE-03**: Configurable tracking poll interval separate from search interval

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Download client integration (qBit/SAB polling) | *arr apps manage download clients; fetcharr only asks *arr "did you grab this?" |
| Webhook receiver for *arr grab notifications | Adds bidirectional coupling, network config complexity, and attack surface |
| Full import tracking (downloadFolderImported) | Two-phase tracking for marginal value; import is *arr's concern |
| Per-indexer effectiveness stats | Prowlarr's job; out of scope for search automation |
| Automated re-search of unresolved items | Round-robin already handles naturally; explicit retry risks indexer abuse |
| Historical backfill of pre-fetcharr grabs | Impossible to attribute correctly; stats start from first fetcharr search |
| Cookie-based CSRF tokens | Sessionless app; Origin/Referer validation is correct approach |
| slowapi/Redis for rate limiting | Single-user local tool; in-memory timestamp check is sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRACK-01 | Phase 19 | Complete |
| TRACK-02 | Phase 19 | Complete |
| TRACK-03 | Phase 19 | Complete |
| TRACK-04 | Phase 20 | Complete |
| TRACK-05 | Phase 20 | Complete |
| TRACK-06 | Phase 20 | Complete |
| TRACK-07 | Phase 17 | Complete |
| TRACK-08 | Phase 17 | Complete |
| STATS-01 | Phase 21 | Complete |
| STATS-02 | Phase 21 | Complete |
| STATS-03 | Phase 21 | Complete |
| STATS-04 | Phase 21 | Complete |
| STATS-05 | Phase 21 | Complete |
| DEBT-01 | Phase 18 | Complete |
| DEBT-02 | Phase 18 | Complete |
| DEBT-03 | Phase 17 | Complete |
| DEBT-04 | Phase 17 | Complete |
| DEBT-05 | Phase 18 | Complete |
| DEBT-06 | Phase 18 | Complete |
| DEBT-07 | Phase 17 | Complete |
| DEBT-08 | Phase 17 | Complete |
| DRSEC-01 | Phase 20.1 | Complete |
| DRSEC-02 | Phase 20.1 | Complete |
| DRSEC-03 | Phase 20.1 | Complete |
| DRSEC-04 | Phase 20.1 | Complete |
| DRSEC-05 | Phase 20.1 | Complete |
| DRSEC-06 | Phase 20.1 | Complete |
| DRSEC-07 | Phase 20.1 | Complete |
| DRSEC-08 | Phase 20.1 | Complete |
| DRQUAL-01 | Phase 20.2 | Complete |
| DRQUAL-02 | Phase 20.2 | Complete |
| DRQUAL-03 | Phase 20.2 | Complete |
| DRQUAL-04 | Phase 20.2 | Complete |
| DRQUAL-05 | Phase 20.2 | Complete |
| DRQUAL-06 | Phase 20.2 | Complete |
| DRQUAL-07 | Phase 20.2 | Complete |
| DRQUAL-08 | Phase 20.2 | Complete |
| DRQUAL-09 | Phase 20.2 | Complete |
| DRQUAL-10 | Phase 20.2 | Complete |
| DRQUAL-11 | Phase 20.2 | Complete |
| DRQUAL-12 | Phase 20.2 | Complete |

**Coverage:**
- v2.0 requirements: 41 total
- Mapped to phases: 41
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-25 after deep review*
