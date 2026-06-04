# Milestones

## v2.11 Never-Searched-First Search Queue Priority (Shipped: 2026-06-04)

**Phases completed:** 1 phase (76), 3 plans, 8 tasks. Released as **v2.11.0**. 1090 tests passing, ruff clean.

**Key accomplishments:**

- Replaced the blind integer-cursor search walk (`missing_cursor`/`cutoff_cursor` + `slice_batch`) with an ordered per-instance **searched-log** on `AppState` (`missing_searched`/`cutoff_searched: list[str]`) and a pure `prioritize_batch(eligible_items, searched_log, batch_size, key_fn)` dispatcher — never-searched-first in fetch order, top-up oldest-searched-first, mark-on-attempt, reset-per-pass, prune-to-eligible, commit-at-cycle-end. Wired into all 6 cycle call sites (Radarr/Sonarr/Lidarr × missing/cutoff); `slice_batch` removed.
- Per-app key normalization via `key_fn` (Radarr/Lidarr `str(id)`, Sonarr composite `seriesId:seasonNumber` — Specials season 0 distinct); pass-completion guarded by `bool(batch)` so a zero-search cycle never completes a pass.
- `_merge_defaults` actively **strips legacy cursor keys on load** (`merged.pop(...)`) with a load→save round-trip test asserting absence from the written JSON — no separate migration function. Count-only refresh stays queue-independent.
- **Codex adversarial review (plan stage)** caught 2 design blockers (stale-key persistence; broken runtime checkpoint) + 2 mediums before execution. **Deep review APPROVED** (0 unfixed critical/warning) after fixing 2 findings: a dashboard half-migration (cursor read left in `routes.py`/`app_card.html` → "0 of N" frozen; rewired to searched-log length) and a negative-`batch_size` slice clamp.
- Milestone audit passed (11/11 requirements, 1/1 phase verified, 11/11 cross-phase connections wired); **live NAS walkthrough** on the deployed build confirmed the searched-log numerator climbs (the review-fix surface), never-searched-first dispatch + Sonarr composite-key path work end-to-end, and refresh-counts stays queue-independent — 0 bugs found.

---

## v2.10 Recovery, Counts & Config Parity (Shipped: 2026-06-04)

**Phases completed:** 4 phases (72-75), 11 plans. Released as **v2.10.0**. 1067 tests passing, ruff clean. Three disjoint tracks. Deep-review APPROVED (0 critical/warning); milestone audit passed (14/14 requirements, 4/4 phases verified, 11/11 cross-phase connections wired); live NAS walkthrough on the deployed build exercised all three tracks end-to-end with 0 bugs found.

**Key accomplishments:**

- **Track A — Self-service password recovery (RCOV-01..06, Phases 72-73):** A locked-out operator can reset the admin password entirely over HTTP without hand-editing `triggarr.toml`. "Forgot password?" link on the login page (only when auth is configured) → request mints a single-use, 15-minute CSPRNG token written to the app log + a `0600` `reset-token.txt` (never in any HTTP response) → confirm sets a new bcrypt hash, rotates `session_secret` (invalidating other sessions), deletes the token file, and auto-logs-in. Both endpoints rate-limited; `/reset` routes auth-exempt via a tight exact-or-`/reset/` predicate.
- **Track B — Count-only refresh (CNT-01..05, Phase 74):** Per-card "Refresh counts" button + `POST /api/refresh-counts/{app}/{instance}` shows true post-change missing/cutoff/eligible counts on demand without launching a search wave or advancing the cursor. Extracted a shared fetch+count+filter helper from `run_*_cycle` (behavior-preserving); the count path updates health + counts but never stamps `last_run`/`last_success` or touches the SAFETY-03 failure counter.
- **Track C — Drain-timeout config parity (CFG-03/CFG-04, Phase 75):** Graceful-shutdown drain timeout is now an editable `GeneralConfig` field + settings-UI numeric input (`>= 1.0`, finite-only via `allow_inf_nan=False` + a `math.isfinite` guard), with documented env-override precedence (config is the default; `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` wins; clamp on both sources). The scheduler reads it at shutdown time (hot-reloadable) instead of from an import-time constant.
- **DOCS-01 deferred-record correction (Phase 75):** Corrected the stale planning record — DEBT-07/08/03 were already shipped; DEBT-06 now shipped — across STATE.md, README, and the in-app CHANGELOG.

**Notes:** Phase 73 human-verification (visual reset-flow checks) and the deferred 73-HUMAN-UAT were resolved by the milestone-end NAS walkthrough. Non-blocking tech debt deferred to backlog (see v2.10-MILESTONE-AUDIT.md): retire the dead `_SHUTDOWN_DRAIN_TIMEOUT` constant; migrate `request_timeout` to `safe_float`; tighten the `safe_float` docstring; optional `DEFAULT_CONFIG` drain example.

---

## v2.9 Launch-Hardening / Sibling Consistency (Shipped: 2026-06-03)

**Phases completed:** 4 phases (68-71), 11 plans
**Requirements:** 19/19 satisfied (CDISC ×5, CHARD ×4, PDISC ×3, PREW ×7) — 0 deferred
**Tests:** 984 passing, ruff clean | Released as v2.9.0
**Audit:** passed (19/19); cross-phase integration 8/8 wired; live NAS walkthrough passed

**Delivered:** Hardened Triggarr's public-facing surface — both the code a skeptical engineer reads and the presentation a visitor sees — to match sibling project SeedSyncarr, so the two repos read as one coherent author.

**Key accomplishments:**

- Hostile-reader code + full-git-history sweep (ruff whole-tree + Shield SAST/secrets/dep-audit + gitleaks over 1038 commits — history CLEAN, no secrets) producing one triaged findings artifact that gated the fix scope.
- SAFETY-03 resolved: manual `/search-now` and scheduled cycles unified through one `_run_one_cycle` failure-counting path (TODO removed, covering tests added); dependency hardening (starlette ≥1.0.1 closing PYSEC-2026-161); `.orchestrator.json` gitignore + `.gitleaksignore` 8.x fingerprint repair.
- SSRF config-load URL validation: `validate_arr_url_config` rejects cloud-metadata/link-local at startup (clean `sys.exit(1)` on bad config), permits loopback for same-host; web-form path unchanged.
- Presentation overhaul: full README rewrite (benefit-led, accurate Quick Start, corrected install/systemd/Docker), SECURITY.md reconciled with v2.8/v2.8.1 hardening + at-rest caveat, community-health files + repo-metadata text, v2.9.0 release notes + in-app changelog, SeedSyncarr signal reconciliation.
- Live NAS walkthrough against the deployed v2.9 build caught and fixed 2 UX bugs (version badge "vv2.8.1"→"v2.8.1"; Search Now in-flight feedback), plus refreshed README screenshots and recompiled output.css to match production.

---

## v2.8 Hardening & Observability (Shipped: 2026-06-01)

**Phases completed:** 4 phases (64-67), 16 plans
**LOC:** ~6,500 Python source + tests | 961 tests passing
**Requirements:** 16/16 satisfied (SAFETY ×6, SEC ×4, RES ×3, TEST ×4) — 0 deferred
**Audit:** `.planning/milestones/v2.8-MILESTONE-AUDIT.md` (status: passed) | Deep review: `.turingmind/REVIEW.md` (APPROVED) | Live walkthrough: passed

**Delivered:** A reliability and security hardening pass — config writes and the search-history DB are now safe under concurrent access and failure, the scheduler fails safely and escalates repeated failures, the web UI's attack surface is narrowed (CSP nonce, URL/secret validation), and the dashboard surfaces a per-app "Last OK" timestamp so a silently stuck connection is visible at a glance. A settings-save bug (General fields detached from the Save button) was caught by the deployed-build walkthrough and fixed.

**Key accomplishments:**

- **Data safety (Phase 64):** SQLite search_history gained a two-bound contract — resolved rows trim inline to `max_history_rows`, pending rows cap at `2× max` via a `PendingCapExceeded` guard so a stalled tracker can't grow the table unboundedly. Atomic TOML config writes now log/re-raise `os.replace` failures, and a config-write lock (AST-audited in CI) serializes concurrent saves.
- **Scheduler resilience (Phase 65):** Narrowed the cycle exception handler to a four-type tuple + an APScheduler `EVENT_JOB_ERROR` listener so code-bug exceptions become operator-visible instead of silently swallowed; per-(app,instance) consecutive-failure counter escalates WARNING→ERROR at a configurable threshold; graceful-shutdown drain extended 35s→60s and names the stuck cycle on timeout.
- **Security hardening (Phase 66):** Removed `'unsafe-inline'` from CSP `script-src` via a per-request nonce (style-src retains it for Tailwind); settings reject an *arr URL carrying an `apikey=` query param; Basic-auth decoding rejects control-char credentials with a logged WARNING; startup warns on a too-short or unpersisted session secret.
- **Observability (Phase 67, RES-02):** Each dashboard app card shows a "Last OK" timestamp — the last successful cycle — flagged amber when older than 2× the search interval, and shown even when the instance is unreachable.
- **Performance (Phase 67, RES-03):** Tag lists are cached per instance for 1 hour (monotonic TTL) instead of re-fetched every cycle, with targeted invalidation on config save / instance removal; manual Search Now uses the cache too.
- **Test coverage (Phase 67, TEST-01):** OriginCheckMiddleware CSRF suite covers missing Origin/Referer, both-absent, scheme-mismatch (pinned ALLOW, documented), and spoofed-host/suffix/port (REJECT).
- **Walkthrough fix:** General settings fields lived in a form separate from the "Save Settings" button, so saving silently reset them (including "Skip Unreleased Movies"). Fixed via `form="settings-form"` association and verified live on the redeployed build.

**Known gaps at close:** None blocking. All 16 requirements satisfied.

**Minor tech debt deferred:**

- REQUIREMENTS.md traceability checkboxes were stale at close (work shipped but boxes unticked); SUMMARY `requirements_completed` frontmatter sparse on several phases — evidence lives in VERIFICATION.md tables and code. Cosmetic; archived REQUIREMENTS marks all complete.
- Phase 67 has no formal VERIFICATION.md (verified instead by deep-review + walkthrough + the 961-test suite).
- Nyquist VALIDATION discovery flagged phases 65/66 non-compliant — a discovery-only signal; both carry `status: passed` VERIFICATION.md.

---

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
