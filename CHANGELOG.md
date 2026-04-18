# Changelog

## v2.7.1 (2026-04-18)

Dashboard Scale Refresh — pixel-exact port of the finalized AIDesigner artifact. Spacious header with vendored Phosphor icons, scaled stat cards, refined app cards with colored borders, card-based activity rail, updated log viewer, and cleaned-up favicon.

* Features:

  * Vendor Phosphor Icons locally (~144KB woff2, no CDN dependency) with new color tokens for app-type identity
  * Three-zone header with `py-4` padding, icon-paired nav at `text-[15px]`, `gap-6` center alignment, pipe-separated logout with sign-out icon, and Geist Mono version badge
  * "Connection Stable" status pill with pulsing green dot auto-refreshing every 30s via htmx
  * Stat cards scaled to 32px hero numbers with Phosphor icons per app type (chart-line-up / film-strip / television / music-notes / clock-countdown) and colored-dot subtitles
  * Grab Rate card: three horizontal per-app mini progress bars (Radarr orange, Sonarr blue, Lidarr green) with proportional fills
  * App cards: app-type colored left borders (orange / blue / green / red), sectioned header / body / footer layout, recessed Missing/Cutoff sub-cards, full-width Search Now with app-colored hover accent
  * Activity rail: card-based entries with speech bubble pointers, double-circle timeline dots, position-based opacity fading, font-mono app badges with colored dot indicators
  * Log viewer: Phosphor icon controls (terminal-window / pause / corners-out), "System Logs" title, TAILING border-container badge in font-mono, GRAB row highlighting, font-mono level filter with "Level: X" format
  * Cleaned SVG favicon master + regenerated raster bundle (16 / 32 / 180 / 192 / 512) — SVG-primary `<link>` with legacy fallbacks; 24×24 app icon rendered beside "Triggarr" logo text in header

* Fixes:

  * Close HDR-06 — favicon 16×16 white-dot anti-aliasing artifact (originally regressed Mar 11) eliminated by sourcing all rasters from the clean SVG master
  * Refresh stale `output.css` missing Phase 62 `--font-mono` alias (detected during milestone audit)

## v2.7.0 (2026-04-07)

* Features:

  * Add Lidarr support — search missing and upgrade-eligible albums, grab tracking, tag filtering
  * Lidarr instances configurable in settings UI with independent schedules and batch sizes
  * Dashboard shows Lidarr cards with health, queue sizes, and effectiveness stats
  * Search history includes Lidarr entries with per-instance filtering
  * Add in-app changelog — click the version in nav bar to see what's new

* Fixes:

  * Fix Lidarr tracking HTTP 400 — eventType must be integer (1), not string
  * Fix Lidarr badge in dashboard search log showing green instead of Sonarr blue
  * Fix redundant instance badge showing when instance name matches app name (case-insensitive)
  * Move add-instance forms outside main form to fix Save Settings button
  * Gate Docker build on tests and lint passing

## v2.5.2 (2026-03-13)

* Fixes:

  * Use preconfigured Jinja2 Environment for autoescape (security hardening)
  * Sync version string to v2.5.2

## v2.5.1 (2026-03-09)

* Fixes:

  * Change default port to 8484 (6868 conflicts with Profilarr)

## v2.5.0 (2026-03-09)

* Features:

  * Change default port from 8080 to 6868
  * CI: add main tag to all releases

* Fixes:

  * Upgrade Pygments to 2.20.0 (Dependabot security advisory)
  * Redact pydantic ValidationError from HTTP response (CodeQL finding)

## v2.4.1 (2026-03-09)

* Fixes:

  * Address all 42 code review findings from deep review

## v2.4.0 (2026-03-09)

* Features:

  * Add non-Docker pip install release support
  * Add TRUSTED_PROXY_IPS and ROOT_PATH reverse proxy configuration

## v2.3.1 (2026-03-08)

* Features:

  * Add total_items library count to dashboard cards
  * Show git hash for dev builds, semantic version for releases
  * Group version and update badge together in nav bar

* Fixes:

  * Replace ReDoS-vulnerable regex with str.split (security)
  * Resolve all 10 CodeQL security alerts
  * Prevent Sonarr episode stats double-counting on expired partials

## v2.3.0 (2026-03-08)

* Features:

  * Multi-instance support — configure multiple Radarr, Sonarr instances
  * Per-instance round-robin cursors with independent state
  * Tag name → ID resolution via *arr API for tag-based search filtering
  * Per-instance scoped observability in dashboard and search history
  * Version display in nav bar with GitHub update checker

* Fixes:

  * Apply 8 deep review fixes with passing tests

## v2.2.1 (2026-03-08)

* Fixes:

  * Allow missing/cutoff count of 0 in settings UI
  * Auto-create GitHub Release on tag push

## v2.2.0 (2026-03-08)

* Features:

  * Skip unreleased media filter with eligible counts and dashboard skip badges
  * Auto-migration from v2.1 config format

* Fixes:

  * Use per-item history endpoints for accurate grab tracking
  * Sonarr dashboard stats now use consistent episode units
  * Enable proxy_headers for HTTPS reverse proxy support

## v2.0.0 (2026-03-07)

* Features:

  * Closed-loop tracking — polls *arr history after searches, correlates grabs, updates outcomes
  * Outcome badges in search history (grabbed, partial, unresolved)
  * Grab effectiveness stats on dashboard
  * Rename from original project name to Triggarr

## v1.2.0 (2026-02-24)

* Features:

  * Search diagnostics and dashboard observability
  * History UI with filtering and pagination
  * SQLite persistence for search history

## v1.1.0 (2026-02-24)

* Features:

  * CI/CD pipeline with GitHub Actions
  * GHCR publishing with Docker multi-stage build
  * Hard max per-cycle cap
  * README documentation

## v1.0.0 (2026-02-24)

* Features:

  * Round-robin search engine with per-app cursors
  * Season-level Sonarr search
  * Dark theme web UI with FastAPI + htmx + Tailwind CSS v4
  * Settings editor with masked API keys
  * CSRF protection via Origin checking
  * Docker multi-stage build with PUID/PGID support
  * SSRF validation for configured URLs
