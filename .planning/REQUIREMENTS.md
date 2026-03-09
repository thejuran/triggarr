# Requirements: Triggarr

**Defined:** 2026-03-09
**Core Value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback -- without exposing credentials or expanding attack surface.

## v2.3 Requirements

Requirements for multi-instance support and tag-based filtering. Each maps to roadmap phases.

### Multi-Instance

- [ ] **INST-01**: User can configure multiple named Radarr instances with independent URL, API key, schedule, and batch sizes
- [ ] **INST-02**: User can configure multiple named Sonarr instances with independent URL, API key, schedule, and batch sizes
- [ ] **INST-03**: Each instance maintains independent round-robin cursors that persist across restarts
- [ ] **INST-04**: Existing single-instance config auto-migrates to multi-instance format on upgrade
- [ ] **INST-05**: User can add, edit, and remove instances from the web UI settings page
- [ ] **INST-06**: User can enable/disable individual instances from the web UI
- [ ] **INST-07**: Dashboard shows an instance health summary card (connected/disconnected count with per-instance detail)

### Tag Filtering

- [ ] **TAG-01**: User can configure a tag name per instance for the missing queue (only items with that tag are searched)
- [ ] **TAG-02**: User can configure a tag name per instance for the cutoff queue (only items with that tag are searched)
- [ ] **TAG-03**: When no tag is configured, all monitored items are searched (default behavior unchanged)
- [ ] **TAG-04**: Tag names are resolved to IDs via the *arr `/api/v3/tag` endpoint each cycle
- [ ] **TAG-05**: Dashboard shows a warning badge when a configured tag is not found in the *arr instance
- [ ] **TAG-06**: Tag name autocomplete dropdown populated from the *arr instance when configuring filters in the web UI

### Observability

- [ ] **OBS-01**: Dashboard renders a status card per instance showing connection health, queue sizes, and last-run time
- [ ] **OBS-02**: Search history is scoped per instance with an instance filter on the history page
- [ ] **OBS-03**: Per-instance effectiveness stats (grab rate, lifetime counts) displayed on dashboard

### Version

- [ ] **VER-01**: Dashboard displays the current Triggarr version
- [ ] **VER-02**: Dashboard indicates when a newer release is available by checking GitHub/GHCR

## Future Requirements

### Deferred

- **DEFER-01**: Cross-instance search deduplication (by TMDB/TVDB ID)
- **DEFER-02**: Dynamic instance hot-add without restart

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-discover *arr instances via network scan | SSRF risk, violates zero-credential-exposure principle |
| Centralized tag management (create/assign tags from Triggarr) | Write operations expand attack surface; Triggarr is read+search-only |
| Tag-based exclusion (search everything EXCEPT tagged) | Inverse logic is confusing; include-only filtering is clearer |
| Priority ordering between instances | Independent per-instance schedules handle different cadences |
| Webhook receiver for instance registration | Adds listener, increases attack surface, requires *arr config |
| Per-instance database connections | SQLite is single-writer; multiple connections add complexity for zero benefit |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INST-01 | Phase 33 | Pending |
| INST-02 | Phase 33 | Pending |
| INST-03 | Phase 34 | Pending |
| INST-04 | Phase 33 | Pending |
| INST-05 | Phase 39 | Pending |
| INST-06 | Phase 38 | Pending |
| INST-07 | Phase 39 | Pending |
| TAG-01 | Phase 36 | Pending |
| TAG-02 | Phase 36 | Pending |
| TAG-03 | Phase 36 | Pending |
| TAG-04 | Phase 35 | Pending |
| TAG-05 | Phase 39 | Pending |
| TAG-06 | Phase 39 | Pending |
| OBS-01 | Phase 39 | Pending |
| OBS-02 | Phase 37 | Pending |
| OBS-03 | Phase 39 | Pending |
| VER-01 | Phase 39 | Pending |
| VER-02 | Phase 39 | Pending |

**Coverage:**
- v2.3 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
