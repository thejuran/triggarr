# Requirements: Triggarr

**Defined:** 2026-03-09
**Core Value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback -- without exposing credentials or expanding attack surface.

## v2.2 Requirements

Requirements for skip-unreleased-media milestone. Each maps to roadmap phases.

### Configuration

- [x] **CFG-01**: User can enable/disable skip-unreleased-media filtering via web UI toggle
- [x] **CFG-02**: Skip-unreleased setting persists in TOML config file with default enabled

### Filtering

- [x] **FILT-01**: When enabled, Radarr missing-queue items are skipped if no digital or physical release date has passed
- [x] **FILT-02**: When enabled, Sonarr unaired episodes are skipped (existing behavior made conditional on toggle)
- [x] **FILT-03**: Movies with null/missing release dates are still searched (not silently blackholed)
- [x] **FILT-04**: Cutoff-unmet items are never filtered (already have files, proven released)

### Dashboard

- [ ] **DASH-01**: Dashboard shows eligible vs total item counts per app (e.g., "X eligible of Y total")
- [ ] **DASH-02**: Skip-count indicator visible on app cards when items are being skipped

## Future Requirements

None -- feature is self-contained.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-app skip toggle (separate for Radarr/Sonarr) | Unnecessary complexity -- single toggle sufficient |
| Filter by theatrical/inCinemas date | Theatrical release still means cam quality -- not useful |
| Radarr `status` field filtering | Status enum can lag behind actual dates (known Radarr issue #9849) |
| Per-item override (force-search unreleased) | Use Radarr/Sonarr UI directly for one-offs |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CFG-01 | Phase 26 | Complete |
| CFG-02 | Phase 25 | Complete |
| FILT-01 | Phase 25 | Complete |
| FILT-02 | Phase 25 | Complete |
| FILT-03 | Phase 25 | Complete |
| FILT-04 | Phase 25 | Complete |
| DASH-01 | Phase 27 | Pending |
| DASH-02 | Phase 27 | Pending |

**Coverage:**
- v2.2 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
