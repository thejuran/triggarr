# Changelog

## v2.10.0 (2026-06-04)

Password recovery, per-card count refresh, and a configurable shutdown drain timeout.

* Features:

  * Password recovery flow — operators can now reset the admin password without SSH access. A "Forgot password?" link appears on the login page once initial setup is complete; a single-use, 15-minute token is written to the config directory (logged at startup, never returned over HTTP). Confirming the reset rotates the session secret and signs in automatically, invalidating all other active sessions.

  * Per-card count refresh — each app card now has a "Refresh counts" button that fetches current missing/cutoff counts from *arr and updates the dashboard without triggering a search cycle. Counts update instantly; last-searched time and the consecutive-failure counter are unchanged.

  * Configurable shutdown drain timeout — the graceful-shutdown drain (how long Triggarr waits for an in-flight search cycle to finish before forcing close) is now a persisted config field (`general.shutdown_drain_timeout`, settable in Settings, default 60 s, minimum 1 s). The `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` environment variable overrides the configured value when set.

## v2.9.0 (2026-06-02)

Security hardening, a search-reliability fix, and a documentation overhaul.

* Security:

  * URL validation for *arr instances now applies at config-load time, not only when saving settings via the web UI. Cloud-metadata and link-local addresses are blocked on startup; loopback addresses are permitted for same-host deployments.

* Fixes:

  * Fixed the manual-search failure counter not incrementing or resetting after a manual cycle, which could prematurely pause a recovered instance or suppress its paused state when searches were triggered from the UI.

* Documentation:

  * Full README rewrite: benefit-led introduction, accurate Quick Start, corrected pip install and systemd unit instructions, tag-filtering fail-open behavior documented.
  * SECURITY.md updated to reflect v2.8/v2.8.1 hardening and clarify the at-rest plaintext credential caveat.

## v2.8.1 (2026-05-31)

Security patch release: password changes now invalidate other sessions.

* Security:

  * Changing your password now logs out all other active sessions. The session secret is rotated on every password change, so any other browser or device that was signed in is immediately signed out — the one you change it from stays logged in. This makes a password change an effective way to lock out a session you think may be compromised.

## v2.8.0 (2026-06-01)

Hardening & Observability — a reliability-focused release. Triggarr is now sturdier under load and failure, gives you a clearer at-a-glance picture of whether searches are actually working, and tightens security around the web UI. No changes to how you configure or run it.

* Features:

  * The dashboard now shows a "Last OK" time on each app card — the last time a search cycle actually completed successfully. If it's been too long (more than twice your search interval), the time turns amber so you can spot a silently stuck connection at a glance. It still shows even when an app is unreachable, which is exactly when you want to know.

* Improvements:

  * Tag lists are now cached for an hour instead of being re-fetched every single cycle, so tag-filtered searches put less load on Radarr/Sonarr/Lidarr. Saving an instance's settings refreshes its tags immediately.
  * Searches now keep running smoothly through unexpected hiccups instead of quietly stopping, and Triggarr now warns you in the log if the same app keeps failing cycle after cycle.
  * Shutdowns wait a little longer for an in-progress search to finish cleanly, and tell you which one was still running if it has to force-close.
  * The search history database now stays bounded even if download tracking gets stuck, so it can't quietly balloon over time.

* Security:

  * The web UI's content security policy is stricter (inline scripts are gone), reducing the browser-side attack surface.
  * Settings now reject an *arr URL that has an API key pasted into it, and flag a too-short or unsaved session secret on startup.
  * Login handling is more defensive against malformed credentials.

* Fixes:

  * Fixed a bug where saving Settings silently reset the General options (including "Skip Unreleased Movies") because the Save button wasn't tied to those fields. General settings now save correctly.

## v2.7.3 (2026-05-08)

Security patch release for a high-severity multipart parser advisory.

* Security:

  * Require `python-multipart>=0.0.27` to remediate GHSA-pp6c-gr5w-3c5g / CVE-2026-42561, a denial-of-service issue in multipart part header parsing.
  * Refresh `uv.lock` so locked installs resolve `python-multipart 0.0.27`.
  * Docker installs now enforce the patched dependency floor through `pyproject.toml`.

## v2.7.2 (2026-05-06)

Portable config directory and documentation refresh.

* Improvements:

  * Custom config directory deployments now behave more consistently, including migration marker handling.
  * Documentation now better reflects current Docker, pip, authentication, reverse proxy, and multi-instance configuration behavior.
  * Radarr, Sonarr, and Lidarr examples have been refreshed to match the current named-instance config format.
  * Reverse proxy guidance now more clearly explains `ROOT_PATH`, `TRUSTED_PROXY_IPS`, and secure cookie behavior.
  * Release automation has been tightened so container publishing only runs from successful main-branch CI.

* Fixes:

  * Fixed a config migration marker path issue when Triggarr is launched with a runtime config path.
  * Removed generated agent/runtime files from the source tree so releases stay cleaner.

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
