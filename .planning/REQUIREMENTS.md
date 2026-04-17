# Requirements: Triggarr

**Defined:** 2026-04-15
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

## v2.7 Requirements

Pixel-exact port of the finalized AIDesigner artifact to Triggarr's Jinja2/Tailwind templates.

**Design spec:** `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html`

### Header

- [ ] **HDR-01**: Header has increased vertical padding matching artifact (py-4)
- [ ] **HDR-02**: Navigation links use text-[15px] with Phosphor icons paired to each link
- [ ] **HDR-03**: Navigation is center-aligned with gap-6 spacing
- [ ] **HDR-04**: Logout link separated by vertical pipe divider with sign-out icon
- [ ] **HDR-05**: "Connection Stable" status pill with pulsing green dot appears on right side of header
- [ ] **HDR-06**: Refined favicon/app icon displayed to the left of "Triggarr" logo text in header (matching SeedSyncarr's icon placement)

### Stat Cards

- [ ] **STAT-01**: Stat cards use p-5 padding with text-[32px]/text-[36px] hero numbers
- [ ] **STAT-02**: Grab Rate card includes per-app mini progress bars (orange Radarr, blue Sonarr)
- [ ] **STAT-03**: Movies/Series/Next Scan cards have colored Phosphor icons matching app type
- [ ] **STAT-04**: Card subtitles separated by visual structure matching artifact layout

### App Cards

- [ ] **CARD-01**: App cards use colored left border per app type (orange for Radarr, blue for Sonarr, red for unreachable)
- [ ] **CARD-02**: App card header has title and connection status pill separated by border-bottom
- [ ] **CARD-03**: Missing/Cutoff stats displayed in recessed sub-cards with bg-triggarr-bg/50
- [ ] **CARD-04**: Search Now button in footer section with app-colored hover accent

### Activity Rail

- [ ] **RAIL-01**: Activity rail items use card-based layout with speech bubble pointer and colored timeline dots
- [ ] **RAIL-02**: App badges use font-mono with colored dot indicators
- [ ] **RAIL-03**: Older entries fade with decreasing opacity

### Log Viewer

- [ ] **LOG-01**: Log viewer uses refined header with Phosphor icons for pause/expand controls
- [ ] **LOG-02**: TAILING badge uses font-mono with pulsing green dot
- [ ] **LOG-03**: Log level filter uses font-mono styled select dropdown

### Font Discipline

- [ ] **FONT-01**: Body text uses system sans-serif (not Geist Mono) — matching current Triggarr
- [ ] **FONT-02**: Geist Mono applied only to: version badge, TAILING/LIVE labels, log viewer body, log filter dropdown, activity rail app badges/timestamps, app card schedule rows

## Future Requirements

None — this milestone is a focused UI port.

## Out of Scope

| Feature | Reason |
|---------|--------|
| New functionality or features | Pure visual port, no behavior changes |
| Mobile-specific responsive changes | Desktop-first artifact; existing responsive behavior preserved |
| Login/setup/settings page redesign | Auth pages stay as-is from v2.6 |
| Phosphor icons CDN dependency | Bundle or vendor Phosphor icons; no external CDN in production |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FONT-01 | Phase 60 | Pending |
| FONT-02 | Phase 60 | Pending |
| HDR-01 | Phase 60 | Pending |
| HDR-02 | Phase 60 | Pending |
| HDR-03 | Phase 60 | Pending |
| HDR-04 | Phase 60 | Pending |
| HDR-05 | Phase 60 | Pending |
| HDR-06 | Phase 63 | Pending |
| STAT-01 | Phase 61 | Pending |
| STAT-02 | Phase 61 | Pending |
| STAT-03 | Phase 61 | Pending |
| STAT-04 | Phase 61 | Pending |
| CARD-01 | Phase 61 | Pending |
| CARD-02 | Phase 61 | Pending |
| CARD-03 | Phase 61 | Pending |
| CARD-04 | Phase 61 | Pending |
| RAIL-01 | Phase 62 | Pending |
| RAIL-02 | Phase 62 | Pending |
| RAIL-03 | Phase 62 | Pending |
| LOG-01 | Phase 62 | Pending |
| LOG-02 | Phase 62 | Pending |
| LOG-03 | Phase 62 | Pending |

**Coverage:**
- v2.7 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-15 after roadmap creation*
