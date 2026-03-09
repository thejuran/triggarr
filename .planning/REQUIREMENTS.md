# Requirements: Triggarr

**Defined:** 2026-03-08
**Core Value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

## v2.0 Requirements

Requirements for v2.0 Harden & Fix. Each maps to roadmap phases.

### Deploy

- [x] **DEPLOY-01**: User can configure config directory via `TRIGGARR_CONFIG_DIR` env var
- [x] **DEPLOY-02**: CSS and static assets load correctly behind a reverse proxy

### Hardening

- [x] **HARDEN-01**: `TRIGGARR_CONFIG_DIR` rejects relative and traversal paths at startup
- [x] **HARDEN-02**: Temp file cleaned up if `os.replace` fails during settings save
- [x] **HARDEN-03**: Module-level constant freeze constraint documented in code
- [x] **HARDEN-04**: Test coverage for frozen module-level constants behavior

## Future Requirements

None planned.

## Out of Scope

| Feature | Reason |
|---------|--------|
| (See PROJECT.md Out of Scope) | Carried forward from previous milestones |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEPLOY-01 | Phase 23 | Complete |
| DEPLOY-02 | Phase 23 | Complete |
| HARDEN-01 | Phase 24 | Planned |
| HARDEN-02 | Phase 24 | Planned |
| HARDEN-03 | Phase 24 | Planned |
| HARDEN-04 | Phase 24 | Planned |

**Coverage:**
- v2.0 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after roadmap creation*
