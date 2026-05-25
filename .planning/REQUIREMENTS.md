# Requirements: v2.8 Hardening & Observability

**Defined:** 2026-05-25
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Source:** `.planning/codebase/CONCERNS.md` (audit dated 2026-05-25). Each requirement below has a concrete file:line pointer in that audit.

## v1 Requirements

### Correctness & Data Safety

- [ ] **SAFETY-01**: Search history table trims to `max_history_rows` after each insert so the database does not grow unbounded (DEBT-03; `triggarr/db.py`, `triggarr/models/config.py:79`)
- [ ] **SAFETY-02**: Scheduler exception handler catches only expected types (`httpx.HTTPError`, `pydantic.ValidationError`, `aiosqlite.Error`, `OSError`) instead of bare `Exception` (`triggarr/search/scheduler.py:124-129`)
- [ ] **SAFETY-03**: Scheduler tracks consecutive failures per job and escalates from WARNING to ERROR after N (configurable, default 5) consecutive failures (`triggarr/search/scheduler.py`)
- [ ] **SAFETY-04**: `_atomic_toml_write` logs `OSError` before suppressing during temp file cleanup, and re-raises any non-`FileNotFoundError` `OSError` raised by `os.replace()` (`triggarr/config.py:113-115`)
- [ ] **SAFETY-05**: A config-write lock serializes web UI config saves so two concurrent PUT requests cannot interleave or silently overwrite each other (`triggarr/web/routes.py`, `triggarr/config.py`)

### Security Hardening

- [ ] **SEC-01**: Content Security Policy `script-src` directive no longer includes `'unsafe-inline'`; inline `<script>` blocks are extracted to static JS files or use a per-response nonce (`triggarr/web/middleware.py:41-48`)
- [ ] **SEC-02**: `*arr` URL validation at config save time rejects URLs that contain an `apikey=` query parameter with a clear error message (`triggarr/clients/base.py:30-35`, `triggarr/startup.py`)
- [ ] **SEC-03**: Basic auth header decoder rejects credentials containing null bytes or other control characters, and logs failed base64 decode attempts at WARNING level (`triggarr/web/middleware.py:158-184`)
- [ ] **SEC-04**: Startup validation enforces session secret length ≥ 32 characters and logs a WARNING when the secret was auto-generated and not yet persisted to the config file (`triggarr/auth.py:61-67`)

### Resilience & Observability

- [ ] **RES-01**: Graceful shutdown extends the `search_lock` drain timeout from 35s to 60s and logs the specific job identifier and elapsed runtime of any cycle still holding the lock before forcing close (DEBT-06; `triggarr/search/scheduler.py:266-273`)
- [ ] **RES-02**: Dashboard surfaces a "last successful search" timestamp per app type (Radarr, Sonarr, Lidarr), visibly stale-flagged when the timestamp is older than 2× the configured interval (`triggarr/web/routes.py`, dashboard templates)
- [ ] **RES-03**: Tag list responses from `*arr` instances are cached in `app.state` with a 1-hour TTL and invalidated on instance config save, eliminating the per-cycle `get_tags()` round-trip (`triggarr/search/engine.py`, `triggarr/clients/base.py`)

### Test Coverage Gaps

- [ ] **TEST-01**: `OriginCheckMiddleware` test suite covers missing Origin, missing Referer, both missing, mismatched scheme, and spoofed-host scenarios (`triggarr/web/middleware.py:52-77`)
- [ ] **TEST-02**: Startup behavior with a corrupted TOML config (syntax error and invalid UTF-8) is tested and produces a clear, actionable error message that mentions the backup file path (`triggarr/config.py:170-185`)
- [ ] **TEST-03**: Two concurrent PUT requests to the config save endpoint are tested to verify the SAFETY-05 lock prevents interleaved writes (`triggarr/web/routes.py`)
- [ ] **TEST-04**: Async client cleanup is tested for in-flight requests at shutdown — client `aclose()` does not hang and any in-flight responses raise cleanly (`triggarr/clients/base.py:275-283`, `triggarr/search/scheduler.py:275-281`)

## v2 Requirements

Deferred to future milestones — surfaced by the 2026-05-25 audit but explicitly out of scope for v2.8.

### Performance & Scaling

- **PERF-01**: Per-endpoint or adaptive request timeout overrides (DEBT-07)
- **PERF-02**: Per-endpoint or adaptive pagination page-size overrides (DEBT-08)
- **PERF-03**: State JSON load/save streaming or compression for large state files
- **SCALE-01**: Lift the 5-instance-per-app-type hard limit (`triggarr/models/config.py:133-137`)
- **SCALE-02**: Search history archival / PostgreSQL migration path for multi-GB retention

### Observability & Audit

- **AUDIT-01**: Audit log of who/when/what for config changes via web UI
- **OBS-01**: Scheduler job dashboard showing next run time and last duration per job

### Carryover from prior milestones

- **UI-01**: Pixel-exact verification of v2.6 login page against AIDesigner artifact (human-required)
- **UI-02**: Pixel-exact verification of v2.6 setup page against AIDesigner artifact (human-required)
- **UI-03**: Pixel-exact verification of v2.6 settings security section against AIDesigner artifact (human-required)
- **CLEANUP-01**: Collapse duplicate `--color-triggarr-primaryDark` token (cosmetic)

## Out of Scope

Explicitly excluded from v2.8 to keep the hardening milestone focused.

| Feature | Reason |
|---------|--------|
| Database migration rollback mechanism | Backup-before-migrate (`*.bak`) is already in place; full rollback adds complexity for marginal recovery value |
| LogBuffer rotation to file | 200-entry in-memory buffer is sufficient for current use; rotation reintroduces filesystem concerns |
| Session cookie clock-skew tolerance | NTP-synced containers are the norm; user-side time misconfig isn't ours to fix |
| Migration `.migrated` marker hardening | Cosmetic banner only; migration durability is unaffected |
| Removing the `python-multipart` patch pin | Tracked as a watch item, not a milestone deliverable |
| Replacing in-memory rate limiter with Redis | Locked Out of Scope at the project level — single-user homelab tool |
| Per-instance API key in URL detection at runtime | URL validation at save time (SEC-02) is sufficient |

## Traceability

Empty until ROADMAP.md is created. The roadmapper will populate this section, mapping every v1 REQ-ID to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SAFETY-01 | TBD | Pending |
| SAFETY-02 | TBD | Pending |
| SAFETY-03 | TBD | Pending |
| SAFETY-04 | TBD | Pending |
| SAFETY-05 | TBD | Pending |
| SEC-01 | TBD | Pending |
| SEC-02 | TBD | Pending |
| SEC-03 | TBD | Pending |
| SEC-04 | TBD | Pending |
| RES-01 | TBD | Pending |
| RES-02 | TBD | Pending |
| RES-03 | TBD | Pending |
| TEST-01 | TBD | Pending |
| TEST-02 | TBD | Pending |
| TEST-03 | TBD | Pending |
| TEST-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 16 ⚠️

---
*Requirements defined: 2026-05-25*
*Last updated: 2026-05-25 after initial definition*
