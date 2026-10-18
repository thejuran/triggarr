# Triggarr Pending TODOs

## Refresh README screenshots

**Why:** The current README screenshots predate the latest UI and documentation refresh, so they may underrepresent what users see after installing the app.

**Scope:** Update the README screenshots for the dashboard, search history, and settings views.

**Files:** `docs/screenshots/dashboard.png`, `docs/screenshots/history.png`, `docs/screenshots/settings.png`, `README.md`

**Acceptance criteria:**

- Screenshots are captured from the current app UI at a consistent viewport size.
- Images show representative end-user data without exposing real API keys, hostnames, or credentials.
- README image references and alt text still match the updated screenshots.
- The refreshed images are verified visually before release.

## Update GitHub Actions for Node.js 24 readiness

**Why:** GitHub Actions reported Node.js 20 deprecation warnings during the v2.7.3 CI and release workflows. GitHub will force JavaScript actions to Node.js 24 by default starting June 2, 2026, and remove Node.js 20 runner support on September 16, 2026.

**Scope:** Review and update workflow action versions or runner environment settings for `.github/workflows/ci.yml` and `.github/workflows/release.yml`.

**Files:** `.github/workflows/ci.yml`, `.github/workflows/release.yml`

**Acceptance criteria:**

- CI and release workflows run without Node.js 20 deprecation warnings.
- Updated action versions remain compatible with the current workflow inputs.
- Main CI and release workflow verification pass after the update.

## Consolidate the cached tag resolver (deferred cleanup)

**Why:** The `_get_tags_cached` closure (TTL check, configured-tag coverage check, fetch and store) is copied verbatim in three places. The PR #26 stale-cache fix had to change all three copies the same way, and `routes.py` imports two private scheduler names only to keep them in lockstep. Raised by vibe-check (arch-001, pass 2 on `5520900`); deferred as a behavior-preserving refactor, separate from defect fixes.

**Scope:** Add one public factory in `triggarr/search/scheduler.py` (e.g. `make_cached_tag_resolver(cache_getter, cache_key, client, instance_config)`) that reads `app.state.tag_cache` at call time, and use it from `make_search_job`, `search_now`, and `refresh_counts`.

**Files:** `triggarr/search/scheduler.py`, `triggarr/web/routes.py`

**Acceptance criteria:**

- One resolver implementation remains; `routes.py` no longer imports `_TAG_CACHE_TTL_SECONDS` or `_cached_tags_cover_config`.
- Existing tag-cache tests (hit, miss, TTL expiry, stale-coverage refetch, still-missing, search-now and refresh-counts paths) pass unchanged.
- A failed `get_tags()` is still never cached.

Previously listed configurable config-directory work has been retired: current code derives `triggarr.toml`, `state.json`, and `triggarr.db` from the absolute `TRIGGARR_CONFIG_DIR` path, with `/config` retained as the Docker-compatible default when the variable is unset.
