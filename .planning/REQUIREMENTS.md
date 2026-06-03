# Requirements: Triggarr — v2.10 Recovery, Counts & Config Parity

**Defined:** 2026-06-02
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

Source: approved design spec `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md`. Three disjoint, independently-phaseable tracks.

## v1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase.

### Password Recovery (Track A)

- [ ] **RCOV-01**: User sees a "Forgot password?" link on the login page, shown only when auth is already configured (not during first-run setup).
- [ ] **RCOV-02**: User can request a reset, which mints a CSPRNG token written to the application log AND a `0600` file in the config volume — and the token value never appears in any HTTP response.
- [ ] **RCOV-03**: A reset token is held in memory only, expires 15 minutes after minting, is single-use, and is invalidated when a newer token is minted.
- [ ] **RCOV-04**: User can submit the token plus a new password to set a new bcrypt hash, which rotates `session_secret` (invalidating other sessions) and auto-logs-in the user with a fresh cookie.
- [ ] **RCOV-05**: Both reset endpoints (request and confirm) are rate-limited to resist log/file flooding and token-submission abuse.
- [ ] **RCOV-06**: The `/reset` routes are reachable without authentication (added to middleware `EXEMPT_PREFIXES`), and the token file is deleted on a successful reset.

### Count-Only Refresh (Track B)

- [ ] **CNT-01**: The shared fetch + raw-count + filter + eligible-count logic is extracted from each `run_*_cycle` into a reusable helper, with existing scheduled-cycle search behavior unchanged.
- [ ] **CNT-02**: User can trigger a count-only refresh that updates missing/cutoff/eligible counts and connection health, and the search cursor is never advanced on this path (structural — slicing lives only in the cycle function).
- [ ] **CNT-03**: A count-only refresh does NOT stamp `last_run`/`last_success` and does NOT touch the SAFETY-03 scheduled-search failure counter.
- [ ] **CNT-04**: User (and scripts) can call `POST /api/refresh-counts/{app}/{instance}`, which mirrors `search_now` (same `search_lock`, rate-limit, app/instance validation, app-card partial response) minus the search.
- [ ] **CNT-05**: User sees a "Refresh counts" button on each app card that triggers the count-only refresh and updates the card in place.

### Config Parity (Track C)

- [ ] **CFG-03**: User can set the graceful-shutdown drain timeout via a `GeneralConfig` field and a settings-UI numeric input, bounded `>= 1.0`.
- [ ] **CFG-04**: The configured drain timeout is the default value; `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` overrides it when set; the `>= 1.0` clamp applies to both sources.
- [ ] **DOCS-01**: Project documentation and the deferred record are corrected to reflect that DEBT-07 (request timeout), DEBT-08 (page size), and DEBT-03 (search-history cap) are already shipped, and DEBT-06 (drain timeout) is now shipped.

## v2 Requirements

Deferred to a future release. Tracked but not in this roadmap.

### UI Verification

- **UI-01**: Login page pixel-exact visual verification (human-needed, behind first-run)
- **UI-02**: Setup page pixel-exact visual verification (human-needed, behind first-run)
- **UI-03**: Settings security pixel-exact visual verification (human-needed, behind first-run)

### Performance & Scale

- **PERF-01**: Per-endpoint request timeout overrides
- **PERF-02**: Per-endpoint pagination page-size overrides
- **PERF-03**: State JSON streaming/compression
- **SCALE-01**: Lift 5-instance-per-app-type hard limit
- **SCALE-02**: Search history archival / PostgreSQL path

### Observability & Audit

- **AUDIT-01**: Config change audit log
- **OBS-01**: Scheduler job dashboard

## Out of Scope

Explicitly excluded for v2.10. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Email-based password reset | Single-user app, no mail infra; filesystem-token model proves host access without new network surface |
| Persisted reset token (survives restart) | In-memory token is sufficient; restart-invalidation is acceptable and avoids new persistent auth state |
| Loopback-only restriction on reset endpoints | Would break legitimate reverse-proxy / LAN recovery; rate-limit + CSPRNG token is the chosen defense |
| `count_only` boolean flag threaded through cycle functions | Spec rejects it — helper extraction keeps the hot path clean and makes cursor-non-advance structural |
| Dropping the `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env var | Would silently break existing deployments; env-overrides-config preserves the documented knob |
| `--color-triggarr-primaryDark` token cleanup | Cosmetic, unrelated to these tracks |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| RCOV-01 | TBD | Pending |
| RCOV-02 | TBD | Pending |
| RCOV-03 | TBD | Pending |
| RCOV-04 | TBD | Pending |
| RCOV-05 | TBD | Pending |
| RCOV-06 | TBD | Pending |
| CNT-01 | TBD | Pending |
| CNT-02 | TBD | Pending |
| CNT-03 | TBD | Pending |
| CNT-04 | TBD | Pending |
| CNT-05 | TBD | Pending |
| CFG-03 | TBD | Pending |
| CFG-04 | TBD | Pending |
| DOCS-01 | TBD | Pending |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 14 ⚠️ (roadmapper will resolve)

---
*Requirements defined: 2026-06-02*
*Last updated: 2026-06-02 after initial definition*
