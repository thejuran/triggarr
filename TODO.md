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

Previously listed configurable config-directory work has been retired: current code derives `triggarr.toml`, `state.json`, and `triggarr.db` from the absolute `TRIGGARR_CONFIG_DIR` path, with `/config` retained as the Docker-compatible default when the variable is unset.
