# Requirements: Fetcharr

**Defined:** 2026-02-24
**Core Value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, without exposing credentials or expanding attack surface.

## v2.0 Requirements

Requirements for v2.0 Closed-Loop Tracking milestone. Each maps to roadmap phases.

### Download Tracking

- [ ] **TRACK-01**: System polls Radarr history endpoint after searches to detect grab events for searched items
- [ ] **TRACK-02**: System polls Sonarr history endpoint after searches to detect grab events for searched items
- [ ] **TRACK-03**: System correlates grabs to fetcharr-triggered searches via timestamp + item ID window matching
- [ ] **TRACK-04**: Search history entries update from "searched" to "grabbed" when all wanted items are resolved
- [ ] **TRACK-05**: Search history entries update to "partial" when some but not all missing episodes are grabbed (Sonarr), or quality still below cutoff
- [ ] **TRACK-06**: Search history entries resolve to "unresolved" when tracking window expires with no grabs detected
- [x] **TRACK-07**: User can configure tracking window duration and poll interval via settings
- [ ] **TRACK-08**: System stores item IDs and expected missing counts at search time for correlation

### Dashboard Stats

- [ ] **STATS-01**: Dashboard shows aggregate search effectiveness (searched-to-grabbed rate)
- [ ] **STATS-02**: Dashboard shows per-app effectiveness breakdown (Radarr vs Sonarr grab rates)
- [ ] **STATS-03**: Dashboard shows lifetime stats: movies found, movies updated (fetcharr-triggered only)
- [ ] **STATS-04**: Dashboard shows lifetime stats: episodes found, episodes updated (fetcharr-triggered only)
- [ ] **STATS-05**: Dashboard shows time-to-grab metric (average time from search to grab)

### Tech Debt

- [ ] **DEBT-01**: Rate limiting on search-now endpoint
- [ ] **DEBT-02**: CSRF protection on settings POST verified/hardened
- [x] **DEBT-03**: Configurable max rows for search history table (bounded growth)
- [ ] **DEBT-04**: Persistent SQLite connection with WAL mode (replaces connection-per-operation)
- [ ] **DEBT-05**: Health check endpoint for container orchestrators
- [ ] **DEBT-06**: Graceful shutdown handler (close scheduler, clients, DB, flush logs)
- [x] **DEBT-07**: Configurable request timeout on outbound HTTP calls
- [x] **DEBT-08**: Configurable pageSize for *arr API pagination

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
| TRACK-01 | Phase 19 | Pending |
| TRACK-02 | Phase 19 | Pending |
| TRACK-03 | Phase 19 | Pending |
| TRACK-04 | Phase 20 | Pending |
| TRACK-05 | Phase 20 | Pending |
| TRACK-06 | Phase 20 | Pending |
| TRACK-07 | Phase 17 | Complete |
| TRACK-08 | Phase 17 | Pending |
| STATS-01 | Phase 21 | Pending |
| STATS-02 | Phase 21 | Pending |
| STATS-03 | Phase 21 | Pending |
| STATS-04 | Phase 21 | Pending |
| STATS-05 | Phase 21 | Pending |
| DEBT-01 | Phase 18 | Pending |
| DEBT-02 | Phase 18 | Pending |
| DEBT-03 | Phase 17 | Complete |
| DEBT-04 | Phase 17 | Pending |
| DEBT-05 | Phase 18 | Pending |
| DEBT-06 | Phase 18 | Pending |
| DEBT-07 | Phase 17 | Complete |
| DEBT-08 | Phase 17 | Complete |

**Coverage:**
- v2.0 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-24 after roadmap creation*
