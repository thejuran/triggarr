# Triggarr

## What This Is

A lightweight Docker-based tool that automates searches in Radarr, Sonarr, and Lidarr for wanted and cutoff unmet items, with closed-loop download tracking and multi-instance support. Configurable round-robin searches at configurable intervals detect when searched items are actually grabbed, showing per-item outcome badges and aggregate effectiveness stats on a dark theme web UI. Supports multiple named Radarr/Sonarr/Lidarr instances with per-instance tag-based search filtering, instance health monitoring, and update notifications. Includes CI/CD pipeline, automated GHCR publishing, SQLite search history with tracking correlation, and comprehensive documentation. Built with Python/FastAPI and htmx/Jinja2. Zero credential exposure by design.

## Core Value

Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback showing what was actually grabbed — without exposing credentials or expanding attack surface.

## Current State

v2.11 Never-Searched-First Search Queue Priority shipped 2026-06-04 (released as v2.11.0). 1090 tests passing, ruff clean. 76 phases, 180 plans completed across 17 shipped milestones.

**Latest milestone delivered (v2.11):**
- Replaced the blind integer-cursor search walk (`missing_cursor`/`cutoff_cursor` + `slice_batch`) with an ordered per-instance searched-log on `AppState` + a pure `prioritize_batch()` dispatcher: never-searched-first, top-up oldest-searched-first, mark-on-attempt (`bool(batch)` pass guard so a zero-search cycle never completes a pass), reset-per-pass, prune-to-eligible, commit-at-cycle-end. Wired into all 6 cycle call sites; `slice_batch` removed.
- Per-app `key_fn` (Radarr/Lidarr `str(id)`, Sonarr composite `seriesId:seasonNumber`); `_merge_defaults` strips legacy cursor keys on load (load→save absence test); count-only refresh stays queue-independent.
- Codex adversarial review caught 2 design blockers + 2 mediums at the plan stage; deep review APPROVED after fixing a dashboard half-migration (cursor read → "0 of N" frozen, rewired to searched-log length) + a negative-batch_size clamp. Audit passed (11/11 reqs, 11/11 wired); live NAS walkthrough confirmed the dashboard numerator climbs + Sonarr composite-key path end-to-end, 0 bugs.

**Prior milestone delivered (v2.10):**
- Track A — Self-service password recovery (RCOV-01..06): "Forgot password?" → single-use 15-min CSPRNG token written to log + `0600` `reset-token.txt` (never in any HTTP response) → confirm sets new bcrypt hash, rotates `session_secret`, deletes token file, auto-logs-in. Both endpoints rate-limited; `/reset` auth-exempt via a tight exact-or-`/reset/` predicate.
- Track B — Count-only refresh (CNT-01..05): per-card "Refresh counts" button + `POST /api/refresh-counts/{app}/{instance}` updates missing/cutoff/eligible counts + health without launching a search or advancing the cursor; never stamps `last_run`/`last_success` or touches the SAFETY-03 failure counter. Shared fetch+count+filter helper extracted from `run_*_cycle` (behavior-preserving).
- Track C — Drain-timeout config parity (CFG-03/CFG-04): `shutdown_drain_timeout` `GeneralConfig` field + settings input (`>= 1.0`, finite-only via `allow_inf_nan=False` + `math.isfinite`), config-default-with-env-override precedence read at shutdown time (hot-reloadable). DOCS-01 corrected the stale deferred record (DEBT-07/08/03 already shipped; DEBT-06 now shipped).
- Deep-review APPROVED (0 critical/warning); milestone audit passed (14/14 requirements, 11/11 cross-phase connections wired); live NAS walkthrough exercised all three tracks end-to-end with 0 bugs found.

**Previous milestone (v2.9, shipped 2026-06-03):** Launch-hardening / sibling consistency — hostile-reader code sweep + clean git history, SAFETY-03 unified failure-counter path, SSRF config-load URL validation, full presentation overhaul.

**Prior milestone delivered (v2.8):**
- Data safety: bounded search-history (resolved trim + pending `2×` cap via `PendingCapExceeded`), hardened atomic config writes, AST-audited config-write lock, corrupted-TOML recovery
- Scheduler resilience: narrow exception tuple + `EVENT_JOB_ERROR` listener, consecutive-failure WARNING→ERROR escalation, 60s graceful-shutdown drain naming the stuck cycle
- Security: CSP `script-src` nonce (no `unsafe-inline`), `apikey=` URL rejection, Basic-auth control-char rejection, session-secret startup validation
- Observability: per-app "Last OK" timestamp on the dashboard with amber stale flag (>2× interval), shown even when unreachable
- Performance: 1h per-instance tag-list cache with targeted invalidation on config save/removal
- Test coverage: OriginCheckMiddleware CSRF suite, corrupt-TOML, concurrent-save, async-cleanup tests
- Walkthrough fix: General settings fields were detached from the Save button (silently reset on save) — fixed via `form="settings-form"`, verified live on the deployed build

**Prior milestone delivered (v2.7):**
- Phase 60 complete: Phosphor Icons vendored locally (no CDN), 4 new Tailwind color tokens (triggarr-radarr/sonarr/danger/primaryDark), three-zone `py-4` header with icon-paired `text-[15px]` nav, CSS pipe divider + Phosphor sign-out for logout, Geist Mono version badge, "Connection Stable" pill with htmx `load, every 30s` self-polling
- Phase 61 complete: Stat cards scaled to `text-[32px]` hero numbers with `p-5` uniform padding, Phosphor icons per app type (chart-line-up/film-strip/television/music-notes/clock-countdown), three horizontal per-app mini bars on Grab Rate (Radarr/Sonarr/Lidarr), colored-dot subtitles; app cards with app-type colored left borders (orange/blue/green/red), sectioned header/body/footer layout, recessed Missing/Cutoff sub-cards (`bg-triggarr-bg/50`), full-width Search Now with app-colored hover accent
- Phase 62 complete: Card-based activity rail with speech bubble pointers (`rotate-45`), double-circle timeline dots, position-based opacity fading (`opacity-75`/`opacity-60` by index), font-mono app badges with colored dot indicators, outcome-based solid/dashed cards; log viewer refined with `ph-terminal-window`/`ph-pause`/`ph-corners-out` Phosphor controls, "System Logs" title, TAILING border-container badge in `font-mono text-triggarr-primary`, GRAB row highlighting, `font-mono` level filter dropdown; `--font-mono` alias added, obsolete CSS removed (timeline-item / timeline-dot / terminal-pane / scanline-overlay)
- Phase 63 complete (gap closure): Cleaned SVG favicon master (3043 bytes, safe markup) + regenerated raster bundle (16/32/180/192/512) eliminating Mar 11 white-dot aliasing artifact; 24×24 `<img class="w-6 h-6">` app icon beside "Triggarr" logo text via nested `gap-2` sub-flex inside outer `gap-3 w-64 shrink-0` left-zone flex (D-08 invariant preserved); SVG-primary `<link rel="icon" type="image/svg+xml">` before `.ico` fallback. Closes HDR-06 deferred from Phase 60.

**Prior milestone delivered (v2.6):**
- Deny-all auth middleware with Forms/Basic/External/Disabled modes
- First-run setup flow with credential creation and auto-generated API key
- Forms login with signed session cookies (30-day expiry)
- Settings security section (password change, auth mode switching, API key management)
- Security hardening: login rate limiter, CSP headers, SSRF IPv6 hardening, log sanitization
- 109 auth-specific tests covering all middleware paths, session lifecycle, and edge cases

## Next Milestone: (planning)

v2.11 shipped 2026-06-04 (released as v2.11.0). Run `/gsd:new-milestone` to scope the next one. Candidate parked items remain in STATE.md Deferred Items (v2.6 UI pixel-verification, PERF-01/02/03, SCALE-01/02, AUDIT-01, OBS-01, v2.9-audit follow-ups) plus the v2.10 deep-review tech-debt follow-ups (retire the dead `_SHUTDOWN_DRAIN_TIMEOUT` constant; migrate `request_timeout` to `safe_float`).

<details>
<summary>Shipped milestone: v2.11 Never-Searched-First Search Queue Priority (2026-06-04)</summary>

**Goal:** Replace the blind integer-cursor search walk with per-item memory so the scheduler prioritizes items it has never searched before.

**Target features:**
- **Ordered searched-log on `AppState`** — per instance, per queue (missing/cutoff), storing *arr item IDs in the order they were searched (oldest first). Radarr/Lidarr = `id`; Sonarr = composite `seriesId:seasonNumber`. Replaces the integer cursor for dispatch.
- **`prioritize_batch()` pure function** — assembles each cycle's batch never-searched-first (in fetched API order), then tops up oldest-searched-first. Swapped into all 6 cycle call sites (Radarr/Sonarr/Lidarr × missing/cutoff), replacing `slice_batch`.
- **Mark-on-attempt, reset-per-pass, prune-to-eligible, commit-at-cycle-end** — an ID joins the log once its search fires (success or failure, so no item starves the queue); when every eligible item has been searched the log clears and the existing `*_pass` counter bumps; the log is pruned to currently-eligible IDs each cycle (bounded); state commits in the single atomic `save_state()` at cycle end (at-least-once).
- **Removals** — `missing_cursor`/`cutoff_cursor` drop from `AppState` and `slice_batch` is deleted. No separate migration function, but `_merge_defaults` actively STRIPS the legacy cursor keys on load (`merged.pop(...)`) — the merge preserves unknown keys, so they would otherwise persist; a load→save round-trip test asserts the keys are ABSENT from the written `state.json`.

**Key context:** Source of truth is the approved design spec `docs/superpowers/specs/2026-06-04-search-queue-priority-design.md` (10 locked decisions in §3, explicit YAGNI scope fence in §9, anticipated affected files in §10). Behavior-preserving on a cold start (empty log = everything unsearched = identical to today's first cycle). Phase numbering continued from v2.10 (Phase 76). Explicitly **untouched**: fetch/filter phases, batch-size config (`search_missing_count`/`search_cutoff_count`), `hard_max_per_cycle`, the global `search_lock`, scheduler intervals, the manual-search rate limit, the SAFETY-03 consecutive-failure counter, and the count-only refresh path.

**Shipped:** Codex adversarial review caught 2 design blockers (stale-key persistence; broken runtime checkpoint) + 2 mediums before execution; deep review APPROVED after fixing a dashboard half-migration + a negative-batch_size clamp; audit passed (11/11 reqs, 11/11 wired); live NAS walkthrough 0 bugs.

</details>

**Still parked for a future milestone:** v2.6 UI pixel-verification (UI-01..03, human-needed, behind first-run), PERF-01/02/03, SCALE-01/02, AUDIT-01, OBS-01, the `--color-triggarr-primaryDark` cosmetic token cleanup, v2.9-audit follow-ups, and the v2.10 deep-review tech-debt follow-ups (retire the dead `_SHUTDOWN_DRAIN_TIMEOUT` constant; migrate `request_timeout` to `safe_float`). See STATE.md Deferred Items.

<details>
<summary>Shipped milestone: v2.10 Recovery, Counts & Config Parity (2026-06-04)</summary>

**Goal:** Ship two parked backlog features plus a small config-parity rider — without expanding the network attack surface or relaxing any existing security invariant.

**Target features:**
- **UI password recovery** (Track A) — self-service reset so a locked-out user never hand-edits `triggarr.toml`. Filesystem-token model: a CSPRNG token written to logs + the config volume proves host access; in-memory, 15-min TTL, single-use, rotates `session_secret`, both endpoints rate-limited, `/reset` exempt from auth middleware.
- **Count-only refresh** (Track B) — surface accurate missing/cutoff counts on demand without triggering searches or advancing the cursor. Extract a fetch+count+filter helper from the engine cycle functions so the count path *structurally* cannot advance the cursor. `POST /api/refresh-counts/{app}/{instance}` mirrors `search_now`; updates connection health + counts but NOT `last_run`/`last_success` or the SAFETY-03 failure counter.
- **DEBT-06 drain-timeout settings knob** (Track C) — expose the graceful-shutdown drain timeout as a `GeneralConfig` field + settings-UI input. Precedence: config value is the default, `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env overrides it when set; `>=1.0` clamp preserved.

**Key context:** Three disjoint, independently-phaseable tracks (no shared code), per the approved design spec `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md`. Cross-track documentation deliverable: correct the stale deferred record — **DEBT-07 (request timeout), DEBT-08 (page size), DEBT-03 (search-history cap) are already shipped** (present in `settings.html`), so only DEBT-06 remained genuinely unexposed. Phase numbering continues from v2.9 (last phase 71).

**Still parked for a future milestone:** v2.6 UI pixel-verification (UI-01..03, human-needed, behind first-run), PERF-01/02/03, SCALE-01/02, AUDIT-01, OBS-01, the `--color-triggarr-primaryDark` cosmetic token cleanup, and v2.9-audit follow-ups (validate_arr_url dedup; Retry-Connection hx-disabled-elt; bug-report.yml dropdown). See STATE.md Deferred Items.

</details>

## Requirements

### Validated

- ✓ Connect to Radarr/Sonarr via API key + URL with startup validation — v1.0
- ✓ Fetch wanted (missing) and cutoff unmet items from both apps — v1.0
- ✓ Round-robin through items sequentially with persistent cursors — v1.0
- ✓ Sonarr searches at season level via SeasonSearch command — v1.0
- ✓ Configurable items per cycle and search interval per app — v1.0
- ✓ Web UI dashboard with htmx polling (status, search log, queue position, counts) — v1.0
- ✓ Web UI config editor with masked API keys — v1.0
- ✓ Search-now button for immediate per-app trigger — v1.0
- ✓ Connection health monitoring with "unreachable since" display — v1.0
- ✓ Per-app enable/disable toggle — v1.0
- ✓ API keys never exposed via any HTTP endpoint — v1.0
- ✓ CSRF protection via Origin/Referer middleware — v1.0
- ✓ SSRF validation, input clamping, config file permissions — v1.0
- ✓ Docker deployment with PUID/PGID, least-privilege, HEALTHCHECK — v1.0
- ✓ State recovery, schema migration, race condition serialization — v1.0
- ✓ 115 tests covering all async paths — v1.0
- ✓ README with install guide, config reference, and security model — v1.1
- ✓ GitHub Actions CI (pytest, lint, Docker build validation) — v1.1
- ✓ Docker release pipeline — dev tag on push, latest + version on release (ghcr.io) — v1.1
- ✓ Local deep code review convention (Claude offers /deep-review before push) — v1.1
- ✓ Configurable hard limit / safety ceiling on max items per cycle — v1.1
- ✓ Persistent search history beyond in-memory log (SQLite storage) — v1.1
- ✓ Search history UI with filtering and pagination — v1.2
- ✓ Sonarr v3/v4 API version detection and logging — v1.2
- ✓ pageSize ceiling logging for large libraries — v1.2
- ✓ CI workflow pushed to GitHub with caching for fast remote runs — v1.2
- ✓ Dashboard position labels show "X of Y" progress — v1.2
- ✓ Application logs visible in web dashboard (live log viewer) — v1.2
- ✓ Search detail log with outcome/detail info per entry — v1.2
- ✓ Deep code review: XSS, SSRF, cursor, atomic write, input validation fixes — v1.2
- ✓ Poll Radarr/Sonarr history endpoints after searches to detect grabs — v2.0
- ✓ Update search history entries with grabbed/partial/unresolved outcome badges — v2.0
- ✓ Aggregate stats on dashboard showing search effectiveness (searched-to-grabbed rate) — v2.0
- ✓ Lifetime stats cards: movies found/updated, episodes found/updated (triggarr-triggered only) — v2.0
- ✓ Time-to-grab metric on dashboard — v2.0
- ✓ Rate limiting on search-now endpoint — v2.0
- ✓ CSRF protection on settings POST verified/hardened — v2.0
- ✓ Bounded search history table growth (configurable max rows) — v2.0
- ✓ Persistent WAL-mode SQLite connection (replaces connection-per-op) — v2.0
- ✓ Health check endpoint for container orchestrators — v2.0
- ✓ Graceful shutdown handler — v2.0
- ✓ Request timeout on outbound HTTP calls — v2.0
- ✓ Configurable pageSize defaults — v2.0
- ✓ Deep security review: row_factory guards, XSS urlencode, rate limiter race fix, migration safety — v2.0
- ✓ Deep quality review: type annotations, pass counter, sorted migrations, model validators — v2.0
- ✓ Project renamed from Fetcharr to Triggarr across package, Docker, CI/CD, and docs — v2.0
- ✓ Configurable config directory via `TRIGGARR_CONFIG_DIR` env var — v2.1
- ✓ CSS and static assets work behind reverse proxy via ROOT_PATH — v2.1
- ✓ Config path validation rejects relative/traversal paths at startup — v2.1
- ✓ Temp file cleanup on os.replace failure during settings save — v2.1
- ✓ Module-level freeze constraint documented and tested — v2.1
- ✓ Consistent request.url_for across all templates for root_path awareness — v2.1
- ✓ Configurable toggle to skip unreleased Radarr movies via web UI checkbox — v2.2
- ✓ Skip movies until digital or physical release date has passed — v2.2
- ✓ Null/missing release dates pass through filter (not blackholed) — v2.2
- ✓ Cutoff-unmet items never filtered (already have files) — v2.2
- ✓ Dashboard eligible vs total counts per app with skip-count indicator — v2.2
- ✓ Skip badge math uses monitored count (not raw total) for accuracy — v2.2
- ✓ Multiple named Radarr/Sonarr instances with independent URL, API key, schedule, and batch sizes — v2.3
- ✓ Per-instance round-robin cursors that persist across restarts — v2.3
- ✓ Auto-migration from single-instance to multi-instance config on upgrade — v2.3
- ✓ Per-instance tag filtering for missing and cutoff queues — v2.3
- ✓ Tag autocomplete from *arr instances in settings UI — v2.3
- ✓ Instance CRUD (add/edit/remove/enable/disable) from web UI — v2.3
- ✓ Instance health summary card with connected/disconnected counts — v2.3
- ✓ Tag warning badges on app cards when configured tag not found — v2.3
- ✓ Per-instance effectiveness stats with instance filter dropdown — v2.3
- ✓ GitHub release update notification in nav bar — v2.3
- ✓ Dismissible migration banner for v2.2→v2.3 upgrade — v2.3
- ✓ Deep review: XSS, CSRF, version parsing, input validation hardening — v2.3
- ✓ CONTRIBUTING.md with fork/branch/PR workflow and dev setup instructions — v2.4
- ✓ SECURITY.md with vulnerability reporting and security model summary — v2.4
- ✓ GitHub issue templates (bug report + feature request as YAML forms) — v2.4
- ✓ Repo metadata (topics + GitHub Discussions) — v2.4
- ✓ Unhappy-path tests for connection failures (DNS, SSL, timeout, mid-cycle) — v2.4
- ✓ Unhappy-path tests for bad API responses (malformed JSON, 403/502, truncated pagination) — v2.4
- ✓ Unhappy-path tests for corrupt state/config (broken TOML, SQLite, JSON, migration) — v2.4
- ✓ Unhappy-path tests for search logic edge cases (empty queues, tag filtering, cursors) — v2.4

- ✓ Design-system foundations: focus-visible rings, reduced-motion, Geist Mono, elevation token, wider container — v2.5
- ✓ Sticky nav with active-tab underline and pulsing update dot — v2.5
- ✓ Compact health strip + hero Grab Rate card with per-app bars and health badge — v2.5
- ✓ Redesigned app cards: unified connection pill, schedule row, pass pills, danger stripes, hover elevation, 3-col grid — v2.5
- ✓ Terminal-style application log: Geist Mono, TAILING, level-colored rows, expandable bottom pane — v2.5
- ✓ Sticky Recent Activity rail with timeline, outcome pills, LIVE indicator — v2.5
- ✓ Lidarr documented as first-class supported *arr alongside Radarr and Sonarr — v2.5
- ✓ Deep code review: 26 fixes (PaginatedResponse resilience, concurrency, security headers, Dockerfile) — v2.5
- ✓ Conditional stat tiles: Movies/Episodes/Albums tiles only shown when respective app is enabled — v2.5

- ✓ First-run setup page redirects from all routes, credential creation with bcrypt hashing — v2.6
- ✓ Auto-generated CSPRNG API key with clipboard copy on setup completion — v2.6
- ✓ Forms login with itsdangerous signed session cookies (30-day expiry) — v2.6
- ✓ Basic auth mode (WWW-Authenticate popup) and External mode (reverse proxy delegation) — v2.6
- ✓ Disabled auth mode via config file only, with periodic startup warning every 60s — v2.6
- ✓ API key authentication via X-Api-Key header with timing-safe comparison — v2.6
- ✓ Deny-all auth middleware with path whitelist, unauthenticated /health endpoint — v2.6
- ✓ Settings security section: password change, auth mode switching, API key mask/copy/regenerate — v2.6
- ✓ Nav bar logout button clearing session cookie — v2.6
- ✓ Login rate limiter (10 attempts/5 min per IP with LRU eviction) — v2.6
- ✓ CSP headers with frame-ancestors 'none', SSRF IPv4-mapped IPv6 + multicast blocking — v2.6
- ✓ Log sanitization (no user-supplied data in login/setup logs) — v2.6

- ✓ Phosphor Icons vendored locally (regular weight only, ~144KB woff2, no CDN) — v2.7
- ✓ Tailwind color tokens for app-type identity (triggarr-radarr/sonarr/danger/primary/primaryDark/elevated) — v2.7
- ✓ Three-zone header: py-4 padding, Phosphor-paired nav at text-[15px], gap-6 center alignment, pipe-separated logout with sign-out icon — v2.7
- ✓ "Connection Stable" status pill with pulsing green dot + htmx `load, every 30s` self-polling — v2.7
- ✓ Font discipline: body font-sans, Geist Mono only on version badge / TAILING-LIVE / log body / log filter / activity rail badges-timestamps / app card schedule rows (via `--font-mono` alias) — v2.7
- ✓ Stat cards: text-[32px] hero numbers, p-5 padding, colored Phosphor icons per app type, colored-dot subtitles — v2.7
- ✓ Grab Rate card: three horizontal per-app mini progress bars (Radarr orange, Sonarr blue, Lidarr green) with proportional inline widths — v2.7
- ✓ App cards: app-type colored left borders (orange/blue/green/red), bordered header-body-footer sections, recessed Missing/Cutoff sub-cards (bg-triggarr-bg/50), full-width Search Now with app-colored group-hover accent — v2.7
- ✓ Activity rail: card-based entries with speech bubble pointers, double-circle timeline dots, outcome-based solid/dashed cards, position-based opacity fading, font-mono app badges — v2.7
- ✓ Log viewer: Phosphor icon controls (terminal-window/pause/corners-out), "System Logs" title, TAILING border-container badge in font-mono, GRAB row keyword highlighting, font-mono level filter with "Level: X" format — v2.7
- ✓ Cleaned SVG favicon master + regenerated raster bundle (16/32/180/192/512) eliminates Mar 11 white-dot aliasing artifact — v2.7
- ✓ 24×24 in-header app icon beside "Triggarr" logo text via nested gap-2 sub-flex (preserves D-08 version badge spacing) — v2.7

- ✓ Bounded search history: resolved rows trim to `max_history_rows`, pending rows cap at 2× via `PendingCapExceeded` — v2.8
- ✓ Hardened atomic config writes (log/re-raise `os.replace` OSError) + AST-audited config-write lock serializing saves — v2.8
- ✓ Narrowed scheduler exception handling + `EVENT_JOB_ERROR` listener + consecutive-failure WARNING→ERROR escalation — v2.8
- ✓ Graceful-shutdown drain extended to 60s, names the stuck cycle (job_id + elapsed) on timeout — v2.8
- ✓ CSP `script-src` nonce migration (no `unsafe-inline`); reject `apikey=` in *arr URLs; Basic-auth control-char rejection; session-secret startup validation — v2.8
- ✓ Per-app "Last OK" timestamp on dashboard with amber stale flag (>2× interval), shown even when unreachable — v2.8
- ✓ Per-instance tag-list cache (1h monotonic TTL) with targeted invalidation on config save/removal — v2.8
- ✓ Test coverage: OriginCheckMiddleware CSRF suite, corrupt-TOML recovery, concurrent config save, async client cleanup — v2.8
- ✓ Settings save form fix: General fields associated with the Save button via `form="settings-form"` (were silently reset) — v2.8
- ✓ Hostile-reader code + full-git-history sweep (ruff whole-tree + Shield SAST/secrets/dep-audit + gitleaks over 1038 commits) → triaged findings artifact gating fix scope; history clean — v2.9 (CDISC-01..05)
- ✓ SAFETY-03: manual `/search-now` + scheduled cycles unified through one `_run_one_cycle` failure-counting path with covering tests; `.orchestrator.json` gitignore + `.gitleaksignore` 8.x repair; starlette ≥1.0.1 (PYSEC-2026-161) — v2.9 (CHARD-01..04)
- ✓ SSRF config-load URL validation: cloud-metadata/link-local blocked at startup with clean exit, loopback permitted for same-host; web-form path unchanged — v2.9 (PREW-02 code half)
- ✓ Presentation overhaul: README rewrite, SECURITY.md reconciled with v2.8/v2.8.1 hardening + at-rest caveat, community-health + repo-metadata, v2.9.0 release notes + in-app changelog, SeedSyncarr signal reconciliation, fresh Playwright screenshots — v2.9 (PDISC-01..03, PREW-01..07)
- ✓ Never-searched-first search queue: ordered per-instance searched-log on `AppState` + pure `prioritize_batch()` dispatcher (never-searched-first, top-up oldest-first, mark-on-attempt, `bool(batch)` pass guard, reset-per-pass, prune-to-eligible, commit-at-cycle-end); per-app `key_fn` (Sonarr composite key); `_merge_defaults` strip-on-load; `slice_batch` removed; count-only refresh stays queue-independent — v2.11 (QUEUE-01..11)

### Active

No active requirements — v2.11 shipped. Run `/gsd:new-milestone` to scope the next set.

Parked for a future milestone: v2.6 UI pixel-verification (UI-01..03), PERF-01/02/03, SCALE-01/02, AUDIT-01, OBS-01, v2.9-audit follow-ups, and v2.10 deep-review tech-debt follow-ups (dead `_SHUTDOWN_DRAIN_TIMEOUT` constant; `request_timeout` → `safe_float`). See STATE.md Deferred Items.

### Out of Scope

- User accounts / multi-user — single-user auth only, no user management
- Readarr / other *arr support — Radarr + Sonarr + Lidarr only
- Notifications (Discord, Telegram, Apprise) — web UI log sufficient
- Prowlarr / indexer management — uses existing *arr search infrastructure
- Download queue management — *arr apps handle this
- Media discovery / TMDB browsing — Overseerr's job
- OAuth / SSO — single-user app; Forms/Basic/External sufficient
- Mobile app — web UI sufficient
- Download client integration (qBit/SAB polling) — *arr apps manage download clients
- Webhook receiver for *arr grab notifications — adds coupling, network config, and attack surface
- Full import tracking (downloadFolderImported) — two-phase tracking for marginal value
- Per-indexer effectiveness stats — Prowlarr's job
- Automated re-search of unresolved items — round-robin handles naturally
- Historical backfill of pre-triggarr grabs — impossible to attribute correctly
- Cookie-based CSRF tokens — Origin/Referer validation sufficient alongside session cookies
- slowapi/Redis for rate limiting — single-user local tool; in-memory check sufficient

## Context

Shipped v2.8 (Hardening & Observability) on 2026-06-01. 961 tests passing. 67 phases, 155 plans completed across 14 shipped milestones. v2.8 added no new runtime dependencies — it hardened existing config/scheduler/security paths and added the dashboard "Last OK" signal + tag-list cache.
Tech stack: Python 3.13, FastAPI, httpx, Pydantic, pydantic-settings, APScheduler, aiosqlite, Jinja2, htmx, Tailwind CSS v4, loguru, ruff, bcrypt, itsdangerous, Phosphor Icons (vendored regular weight).
Docker: multi-stage build with pytailwindcss builder, python:3.13-slim production, PUID/PGID entrypoint.
CI/CD: GitHub Actions (pytest, ruff, Docker build validation) with uv caching + GHCR release workflow with BuildKit cache. `:main`/`:dev` tags on main push, `:latest` + version tag on release.
Registry: ghcr.io/thejuran/triggarr
Repo: github.com/thejuran/triggarr

Known tech debt: _update_info as module-level mutable dict (should move to app.state); tag_warnings typed as list[dict] (should be list[TagWarning] TypedDict); Sonarr eligible/total mixes units (accepted); test_state_wrong_structure_list_crashes documents a limitation in _merge_defaults (list JSON). UI-01/UI-02/UI-03 pixel-exact visual verification from v2.6 still pending (auth pages). Duplicate `--color-triggarr-primaryDark` token declared but unused (templates use `triggarr-green-dark` alias) — collapse in future cleanup pass.

## Constraints

- **Tech stack**: Python (FastAPI) + htmx/Jinja2 — matches user's existing project experience
- **Deployment**: Docker container with docker-compose support
- **Security**: API keys must never be exposed via any HTTP endpoint
- **Scope**: Search automation only — deliberately minimal to reduce attack surface
- **Auth**: Single-user only — no multi-user accounts, OAuth, or SSO

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python/FastAPI over Go | User familiarity, faster iteration | ✓ Good — built in 2 days |
| htmx/Jinja2 over React SPA | Lightweight, no build step, server-rendered | ✓ Good — simple, fast |
| Season-level Sonarr search | Avoids hammering indexers with full-show searches | ✓ Good |
| Round-robin over random | Ensures every item gets searched eventually | ✓ Good |
| No auth (v1.0–v2.5) → built-in auth (v2.6) | Single-user *arr-style auth with Forms/Basic/External/Disabled modes | ✓ Good — v2.6 shipped |
| bcrypt for password hashing | Industry standard, constant-time verification | ✓ Good — v2.6 |
| itsdangerous for signed cookies | Lightweight, no Redis/DB dependency, 30-day expiry | ✓ Good — v2.6 |
| In-memory rate limiter (no Redis) | Single-user homelab tool; resets on restart acceptable | ✓ Good — v2.6 |
| API key boolean in template (not raw key) | Prevents accidental exposure in HTML; reveal-on-regen only | ✓ Good — v2.6 |
| SameSite=Lax + Origin check for CSRF | No CSRF tokens needed; double-submit pattern sufficient | ✓ Good — v2.6 |
| Single instance per app | Simpler config, matches user's setup | ✓ Good |
| APScheduler 3.x over 4.x | 4.x still alpha, 3.x stable with AsyncIOScheduler | ✓ Good |
| Origin/Referer CSRF over tokens | No auth/sessions means no cookies to protect | ✓ Good |
| Vendored htmx over CDN | Reproducible builds, no external dependency | ✓ Good |
| Custom loguru sink for redaction | Filter only sees message, sink sees full output including tracebacks | ✓ Good |
| Ruff rule sets E,F,I,UP,B,SIM | Comprehensive but non-noisy linting | ✓ Good |
| Proportional hard max split | floor(missing/total*max) for missing, remainder for cutoff | ✓ Good |
| Toggle-pill filter pattern for history | URL param manipulation in Jinja2, no JS framework needed | ✓ Good |
| Atomic config write (tempfile + fsync + os.replace) | Prevents partial writes | ✓ Good |
| Post-search tracking inside cycle functions | No separate scheduler job; tracks after each search cycle inside search_lock | ✓ Good — v2.0 |
| Probabilistic grab attribution (timestamp window) | No commandId link available; window matching sufficient | ✓ Good — v2.0 |
| Zero new dependencies for v2.0 | All features achievable with existing stack + stdlib | ✓ Good — v2.0 |
| frozenset allowlist for stat column names | Prevents SQL injection in dynamic SET clause | ✓ Good — v2.0 |
| Double-checked locking for rate limiter | Pre-check optimistic, re-check inside lock authoritative | ✓ Good — v2.0 |
| _sanitize_exc type-based dispatch | Avoids leaking internal details in exception messages | ✓ Good — v2.0 |
| SUM(CASE WHEN) for SQLite compatibility | FILTER clause not available in all SQLite versions | ✓ Good — v2.0 |
| get_config_dir() function for testable env var reading | Avoids module reload issues in tests | ✓ Good — v2.1 |
| url_for via request.url_for everywhere | Consistent root_path support for reverse proxies | ✓ Good — v2.1 |
| Absolute-path-only config dir validation | Prevents relative/traversal path misconfiguration | ✓ Good — v2.1 |
| Null release dates = pass through (not blackhole) | PITFALLS.md approach; unknown != unreleased | ✓ Good — v2.2 |
| Filter uses digitalRelease/physicalRelease only | inCinemas = cam quality; status field lags behind dates | ✓ Good — v2.2 |
| Filter after filter_monitored, before cursor/slice | Correct pipeline position: skip only monitored unreleased | ✓ Good — v2.2 |
| Cutoff-unmet never filtered | Already have files = proven released | ✓ Good — v2.2 |
| Skip badge uses missing_monitored not missing_count | Avoids inflating skip count with unmonitored items | ✓ Good — v2.2 |
| contextlib.suppress for date parsing | ruff SIM105 compliance; cleaner than try/except/pass | ✓ Good — v2.2 |
| Dict-based multi-instance config (nested TOML tables) | Natural TOML mapping, pydantic-settings compatible | ✓ Good — v2.3 |
| Auto-migration from v2.2 flat config to v2.3 nested format | Zero-downtime upgrade path | ✓ Good — v2.3 |
| Tag resolution per-cycle (not cached) | Tags may change in *arr; fresh resolution ensures correctness | ✓ Good — v2.3 |
| Mutable dict for _update_info Jinja2 global | In-place update avoids re-registration; no .clear() for atomicity | ✓ Good — v2.3 |
| HX-Request header check for CSRF on DELETE endpoints | Htmx sends custom header; cross-origin requests blocked by CORS preflight | ✓ Good — v2.3 |
| Sticky Recent Activity rail + expandable terminal log (vanilla JS, no framework) | Rail queries existing SQLite search history via a dedicated `/partials/activity-rail` polling endpoint — reuses `get_recent_searches()` DB helper with no new schema changes. Sticky positioning keeps activity visible during scroll. Expandable log uses fixed bottom-pinned pane with vanilla JS toggle — avoids Alpine/React dependency. Rail hidden below xl: breakpoint so narrow screens use History page instead. | ✓ Good — v2.5 |
| Vendor Phosphor Icons regular weight locally (v2.7) | Only regular weight needed; local vendor avoids CDN dependency (CONSTRAINT: no external CDN) and saves ~800KB vs all-weights bundle. Delivered via single woff2 + generated CSS linked from base.html head. | ✓ Good — v2.7 |
| Three-zone absolute-centered header layout (v2.7) | `w-64 shrink-0` left/right zones with `absolute left-1/2 -translate-x-1/2` center nav gives precise alignment without flexbox justify hacks; zones provide deterministic space for favicon/version badge + connection pill. | ✓ Good — v2.7 |
| Connection pill htmx `load, every 30s` self-polling (v2.7) | Avoids threading health data through every route context. Partial re-renders with `hx-swap="outerHTML"` and the returned fragment carries the same trigger attrs, so polling continues after each swap. | ✓ Good — v2.7 |
| Defer HDR-06 rather than ship with aliasing artifacts (P60 D-05) | Mar 11 favicon PNGs had visible white-dot aliasing artifacts at 16×16. Rather than ship degraded visuals, defer to dedicated gap-closure phase that produces a clean SVG master + regenerated rasters. | ✓ Good — v2.7 (closed in Phase 63) |
| CSS `--font-mono: "Geist Mono"` alias (v2.7 Phase 62) | Enables `font-mono` utility class to map to Geist Mono without requiring Tailwind v4 theme restructuring; preserves existing `font-geist-mono` utility for version badge while letting activity rail/log viewer/app card schedule rows use standard `font-mono`. | ✓ Good — v2.7 |
| Regenerate 16×16/32×32 favicons from SVG via qlmanage (P63 D-19) | Bypasses realfavicongenerator.net's downsampled pipeline that caused the Mar 11 aliasing artifact. macOS `qlmanage -t -s 16/32` renders directly from the clean SVG master, producing bytes that differ from Mar 11 backup (verified via `cmp`). | ✓ Good — v2.7 |
| SVG-primary favicon `<link>` before `.ico` fallback (P63) | Modern browsers pick the crisp SVG; legacy fall through to rasters. SVG master also serves as the source for the 24×24 in-header `<img class="w-6 h-6">` app icon via same `url_for('static', path='favicon.svg')`. | ✓ Good — v2.7 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-04 after v2.11 Never-Searched-First Search Queue Priority milestone shipped (v2.11.0)*
