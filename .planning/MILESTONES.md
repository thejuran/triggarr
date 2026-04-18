# Milestones

## v2.7 Dashboard Scale Refresh (Shipped: 2026-04-18)

**Phases completed:** 4 phases, 8 plans
**Timeline:** 3 days (Apr 15-18, 2026 — 2 execution days + 1 audit/ship day)
**LOC:** 6,178 Python + 1,502 HTML templates + 7,184 CSS | 857 tests passing
**Git range:** ecafd9a..c34ae6a (101 commits, 19 files in triggarr/ modified, +5,792 / -409 lines in template/CSS)
**Requirements:** 22/22 satisfied (0 deferred) — all HDR / STAT / CARD / RAIL / LOG / FONT requirements shipped

**Delivered:** Pixel-exact port of the finalized AIDesigner artifact — spacious header with vendored Phosphor icons, scaled stat cards with proportional per-app mini bars, refined app cards with colored left borders, card-based activity rail with opacity fading, updated log viewer with Phosphor icon controls, and a cleaned-up SVG favicon + in-header app icon.

**Key accomplishments:**

- Vendored Phosphor Icons regular weight locally (~144KB woff2, no CDN dependency) + 6 new Tailwind color tokens (triggarr-radarr / sonarr / danger / primary / primaryDark / elevated) for consistent app-type color coding across stat cards, app cards, activity rail, and log viewer
- Three-zone `py-4` header with Phosphor-paired `text-[15px]` nav, CSS pipe divider + sign-out icon on logout, Geist Mono version badge, and "Connection Stable" pill with htmx `load, every 30s` self-polling — FONT-01/02, HDR-01..HDR-05 shipped in Phase 60
- Hero-scaled stat cards: `text-[32px]` hero numbers, Phosphor icons per app type (chart-line-up / film-strip / television / music-notes / clock-countdown), horizontal per-app mini bars on Grab Rate with proportional inline width math, colored-dot subtitles — STAT-01..STAT-04 shipped in Phase 61
- Sectioned app cards with app-type colored left borders (orange Radarr / blue Sonarr / green Lidarr / red unreachable), bordered header/body/footer sections, recessed Missing/Cutoff sub-cards with `bg-triggarr-bg/50`, full-width Search Now with app-colored group-hover accent — CARD-01..CARD-04 shipped in Phase 61
- Card-based activity rail with speech-bubble pointers and double-circle timeline dots, position-based opacity fading, font-mono app badges with colored dot indicators; refined log viewer with Phosphor icon controls, "System Logs" title, TAILING border-container badge, GRAB row highlighting, font-mono level filter — RAIL-01..03 + LOG-01..03 shipped in Phase 62
- Gap-closure Phase 63 for HDR-06 (deferred from Phase 60 D-05): cleaned SVG favicon master (safe markup, no script/on*/xlink:href), regenerated raster bundle (16/32/180/192/512) eliminating Mar 11 white-dot aliasing artifact via direct SVG→PNG rendering (`qlmanage`), 24×24 in-header `<img>` app icon via nested `gap-2` sub-flex preserving outer `gap-3 w-64 shrink-0` invariant
- All phases Nyquist-compliant at close (refreshed during milestone audit): 20 tests for P60, 38 tests for P61, 38 tests for P62, 6 tests for P63 — 102 new phase-scoped tests layered on top of 755 carry-over tests

**Known gaps at close:** None blocking.

**Minor tech debt deferred:**
- Duplicate `--color-triggarr-primaryDark` (#16a34a) token declared but unused — templates use older `triggarr-green-dark` alias (same hex). Safe to collapse in future cleanup pass.
- SUMMARY frontmatter inconsistency on plans 61-01, 62-01, 62-02 (missing `requirements-completed` field). VERIFICATION.md Requirements Coverage tables compensate; future plans should follow 60-xx/63-01 precedent.
- UI-01/UI-02/UI-03 from v2.6 milestone close (auth pages pixel-exact verification) still carries forward — not in v2.7 scope.

---

## v2.6 Built-In Authentication (Shipped: 2026-04-15)

**Phases completed:** 6 phases, 16 plans
**Timeline:** 2 days (Apr 14-15, 2026)
**LOC:** ~20,225 Python (source + test) | 805 tests
**Git range:** adf69e3..0f6fa94 (148 commits, 152 files changed, +19,360 -6,323 lines)
**Requirements:** 18/21 satisfied, 3 deferred (UI pixel-exact visual verification)

**Delivered:** *arr-style built-in authentication — secure by default with Forms/Basic/External/Disabled modes, first-run setup, API key, signed session cookies, settings security section, and security hardening addressing 11 Shield findings.

**Key accomplishments:**

- Deny-all auth middleware with Forms/Basic/External/Disabled modes, timing-safe API key validation via `secrets.compare_digest`, and browser redirect vs API 401 dispatch
- First-run setup flow with credential creation (bcrypt hashing), auto-generated CSPRNG API key with clipboard copy, and auto-login on completion
- Forms login with itsdangerous signed session cookies (30-day expiry), `?next=` redirect preservation with open redirect prevention, and nav bar logout
- Settings security section with password change (htmx inline), auth mode switching (dropdown with contextual warnings), and API key mask/copy/regenerate
- 109 auth-specific tests covering all middleware paths, session lifecycle, setup flow, login/logout, API key auth, mode switching, and 3 cross-cutting E2E integration tests
- Security hardening: login rate limiter (10 attempts/5 min per IP with LRU eviction), CSP headers, API key exposure fix (boolean not raw key), SSRF IPv4-mapped IPv6 + multicast blocking, log sanitization, periodic auth-disabled warning

**Known gaps at close:**

- UI-01, UI-02, UI-03: Pixel-exact visual verification of login/setup/settings pages against AIDesigner artifacts (requires human comparison)
- Nyquist validation non-compliant for phases 54, 55, 56
- Most SUMMARY.md files missing `requirements_completed` frontmatter

---

## v2.5 Dashboard UI Refresh (Shipped: 2026-04-14)

**Phases completed:** 6 phases, 15 plans
**Timeline:** 4 days (Apr 10-13, 2026)
**LOC:** ~17,361 Python (5,406 source + 11,955 test) | 668 tests
**Git range:** 87da2a9..fb8f3ef (49 commits, 116 files changed, +10,696 -2,964 lines)
**Requirements:** 37/37 satisfied | **UAT:** 45/45 passed

**Delivered:** Complete dashboard visual refresh with design-system foundations, redesigned stats/cards/log components, a new sticky activity rail, and a 26-issue deep code review.

**Key accomplishments:**

- Design-system foundations: focus-visible rings, reduced-motion, Geist Mono typography, elevation token, wider max-w-7xl container
- Sticky navigation with active-tab underline and pulsing update-available dot
- Compact health strip + hero Grab Rate card with per-app color-coded bars and Healthy/Warn/Critical badge
- Redesigned app cards: unified connection pill, schedule row, pass pills, danger stripes + Retry button, hover elevation, 3-col xl grid
- Terminal-style application log: Geist Mono, TAILING indicator, level-colored rows, expandable bottom-pinned pane with scanline effect
- Sticky Recent Activity rail with vertical timeline, outcome pills, LIVE indicator, and app filter (replaces inline search log)
- Deep code review: 26 issues fixed across 3 rounds — PaginatedResponse resilience, search_lock concurrency, security headers, Lidarr pagination, event loop blocking, Dockerfile hardening

---

## v2.4 Community Polish & Test Hardening (Shipped: 2026-04-09)

**Phases completed:** 3 phases, 6 plans
**Timeline:** 27 days (Mar 13 – Apr 9, 2026)
**LOC:** ~15,979 Python (5,308 source + 10,671 test) | 606 tests
**Git range:** 6eb469c..4320adf (79 commits, 216 files changed, +10,567 -15,276 lines)

**Delivered:** Open-source community health files (CONTRIBUTING.md, SECURITY.md, issue templates, PR template, repo metadata) and 45 new unhappy-path tests covering connection failures, bad API responses, corrupt state/config, and search logic edge cases.

**Key accomplishments:**

- CONTRIBUTING.md with fork/branch/PR workflow, dev setup, and conventional commit guide; SECURITY.md with vulnerability reporting and 7-mechanism security model summary; MIT LICENSE
- GitHub issue templates (bug report + feature request YAML forms), PR template with CI checklist, blank issues disabled with Discussions contact link
- 7 GitHub topics set and Discussions enabled for community engagement
- 9 connection failure tests — DNS, SSL, timeout, mid-cycle failures, unreachable_since tracking
- 15 bad API response tests — malformed JSON, 403/502 status codes, truncated pagination, Sonarr version edge cases
- 14 corrupt state/config tests — broken TOML, corrupt SQLite, invalid JSON state, migration edge cases
- 7 search edge-case tests — empty queues, all-filtered-by-tag, Lidarr tag resolution failure, cursor boundaries

**Tech debt carried forward:**

- META-01/META-02 require manual GitHub UI verification (topics visible, Discussions enabled)
- Phase 46 VALIDATION.md not updated to nyquist_compliant
- test_state_wrong_structure_list_crashes documents a limitation in _merge_defaults (list JSON)

---

## v2.3 Multi-Instance & Tag Filtering (Shipped: 2026-03-14)

**Phases completed:** 9 phases, 15 plans, 4 tasks

**Key accomplishments:**

- (none recorded)

---

## v2.2 Skip Unreleased Media (Shipped: 2026-03-09)

**Phases completed:** 4 phases, 5 plans
**Timeline:** 1 day (Mar 9, 2026)
**LOC:** ~8,964 Python (3,389 source + 5,575 test) | 302 tests
**Git range:** c38e853..7da1fbf (30 commits, 9 files changed, +527 -7 lines)

**Delivered:** Skip-unreleased media filtering with configurable UI toggle, eligible-count dashboard display, and code review fixes.

**Key accomplishments:**

- `skip_unreleased` config field with TOML persistence and `filter_unreleased_movies()` pure function covering all release-date edge cases (null passthrough, future skip, past pass)
- Settings UI checkbox with full save/load round-trip, conditionally wiring filter into Radarr missing-queue pipeline (after filter_monitored, before cursor/slice_batch)
- Dashboard "X of Y items" eligible-count display with conditional amber skip badge on Radarr cards when items are being skipped
- Fixed skip badge math using `missing_monitored` intermediate count, added INFO skip log, print→loguru migration, Callable type annotation fix
- Nyquist validation complete across all 4 phases; 302 tests passing, 0 ruff violations

**Tech debt carried forward:**

- `missing_monitored` not declared in AppState TypedDict (cosmetic, no runtime impact)
- Sonarr eligible/total mixes units (seasons vs episodes) — accepted as-is

---

## v2.1 Harden & Fix (Shipped: 2026-03-09)

**Phases completed:** 2 phases, 2 plans
**Timeline:** 1 day (Mar 8, 2026)
**LOC:** ~8,322 Python (3,389 source + 4,933 test) | 270 tests
**Git range:** 69bee92..b73a9b4 (19 commits)

**Delivered:** Deployment hardening — configurable config directory, reverse proxy compatibility, path validation, and temp file safety.

**Key accomplishments:**

- Configurable config directory via TRIGGARR_CONFIG_DIR env var for flexible Docker deployments
- ROOT_PATH support for reverse proxy deployments (Nginx, Caddy, Traefik) with consistent request.url_for across all templates
- Config path validation rejects relative/traversal paths at startup with clear errors
- Temp file cleanup on os.replace failure in settings save (matching state.py pattern)
- Module-level freeze constraint documented and tested
- 13 new tests added, 270 total passing

**Tech debt carried forward:** None

---

## v2.0 Closed-Loop Tracking (Shipped: 2026-03-09)

**Phases completed:** 8 phases, 18 plans
**Timeline:** 12 days (Feb 25 – Mar 8, 2026)
**LOC:** ~8,010 Python | 220+ tests
**Git range:** 98dc93a..7b1e6fd (67 commits)

**Delivered:** Closed-loop download tracking with grab detection, per-item outcome badges, dashboard effectiveness stats, production hardening, deep security/quality review, and full rename from Fetcharr to Triggarr.

**Key accomplishments:**

- Closed-loop tracking pipeline: polls Radarr/Sonarr history after searches to detect grabs, correlates via timestamp+itemID windows, updates outcomes atomically with lifetime stats
- Per-item outcome badges (grabbed/partial/unresolved) in search history and dashboard with color coding and tooltips
- Dashboard stats cards: aggregate grab effectiveness rate with per-app breakdown, lifetime movies/episodes found, time-to-grab metric, htmx auto-refresh
- Production hardening: rate limiting (10s window with double-check), health check endpoint, graceful shutdown with 35s lock-drain, CSRF integration test
- Deep code review: 20 fixes across security (XSS urlencode, race conditions, exception sanitization, migration safety) and quality (type annotations, pass counter, sorted migrations, model validators)
- Renamed project from Fetcharr to Triggarr across package, Docker, CI/CD, and all documentation

**Tech debt carried forward:**

- 2 test assertions in test_search.py need updating for DRSEC-07 sanitization change
- test_search.py hangs on execution (pre-existing)

---

## v1.0 MVP (Shipped: 2026-02-24)

**Phases completed:** 8 phases, 18 plans
**Timeline:** 2 days (Feb 23–24, 2026)
**LOC:** ~3,672 Python + ~213 HTML | 115 tests
**Git range:** e56ced3..b4e59ae

**Delivered:** A lightweight Docker-based search automation daemon for Radarr and Sonarr with a dark theme web UI, round-robin scheduling, and zero credential exposure.

**Key accomplishments:**

- Config, state, and API clients with Pydantic models, SecretStr API keys, loguru redaction, and atomic JSON state
- Round-robin search engine with per-app cursors, season-level Sonarr search, and APScheduler integration
- Dark theme web UI with htmx polling dashboard, config editor, and search-now trigger
- Multi-stage Docker packaging with PUID/PGID privilege dropping, HEALTHCHECK, and localhost detection
- Security hardening — CSRF middleware, SSRF validation, input clamping, Docker least-privilege, vendored htmx
- Comprehensive resilience and test coverage — 115 tests, state recovery, schema migration, race condition fix

---

## v1.1 Ship & Document (Shipped: 2026-02-24)

**Phases completed:** 4 phases, 5 plans
**Timeline:** 2026-02-24 (same day as v1.0)
**Git range:** v1.0..HEAD (30 commits)
**Files:** 49 files changed, +4,192 -173 lines

**Delivered:** CI/CD pipeline, automated Docker releases to GHCR, search enhancements (hard max cap + SQLite history), and comprehensive README documentation.

**Key accomplishments:**

- GitHub Actions CI with pytest, ruff linting, and Docker build validation in three parallel jobs
- Automated GHCR publishing — `:dev` on push to main, `:latest` + version tag on release
- Hard max items per cycle with proportional batch capping and settings UI integration
- SQLite persistent search history with auto-migration from JSON and 500-row auto-pruning
- Complete README with Docker install guide, TOML config reference, security model, and screenshot placeholders

---

## v1.2 Polish & Harden (Shipped: 2026-02-24)

**Phases completed:** 4 phases, 8 plans
**Timeline:** 2026-02-24 (same day)
**LOC:** ~5,225 Python | 174 tests
**Git range:** 913d6b2..34b75ee (39 commits, 47 files changed, +4,998 -88 lines)

**Delivered:** Search diagnostics, dashboard observability (position labels, log viewer, outcome badges), browsable search history with filtering/pagination, and a deep code review with security fixes.

**Key accomplishments:**

- CI workflow hardened with uv package caching and Docker BuildKit GHA cache for fast remote runs
- Sonarr v3/v4 API version detection at startup with per-cycle diagnostic summary logging
- Dashboard enhanced with "X of Y" position labels, colored outcome badges, and live application log viewer with secret redaction
- Search history page with toggle-pill filters (app/queue/outcome), text search with debounce, and paginated results
- Deep code review: 7 warning-level fixes (XSS tojson, SSRF blocklist, cursor leaks, atomic config writes, input validation) with 7 regression tests
- 8 medium-severity issues documented and deferred (rate limiting, CSRF, history growth, connection pooling, health check, graceful shutdown, request timeouts, configurable pageSize)

**Tech debt deferred to next milestone:**

- M1: No rate limiting on search-now endpoint
- M2: No CSRF protection on settings POST
- M3: Unbounded search history table growth
- M4: No connection pooling for aiosqlite
- M5: Hardcoded pageSize defaults not configurable
- M6: No health check endpoint
- M7: No graceful shutdown handler
- M8: No request timeout on outbound HTTP calls

---
