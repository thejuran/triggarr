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

Previously listed configurable config-directory work has been retired: current code derives `triggarr.toml`, `state.json`, and `triggarr.db` from the absolute `TRIGGARR_CONFIG_DIR` path, with `/config` retained as the Docker-compatible default when the variable is unset.
