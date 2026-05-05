# Codebase Map

Generated: 2026-05-05T23:52:50Z | Files: 110 | Described: 0/110
<!-- gsd:codebase-meta {"generatedAt":"2026-05-05T23:52:50Z","fingerprint":"d15e644e1f0d1a4540ab58776092a65628fb4262","fileCount":110,"truncated":false} -->

### (root)/
- `.dockerignore`
- `.gitignore`
- `.gitleaksignore`
- `CHANGELOG.md`
- `CLAUDE.md`
- `CONTRIBUTING.md`
- `docker-compose.yml`
- `Dockerfile`
- `entrypoint.sh`
- `LICENSE`
- `pyproject.toml`
- `README.md`
- `SECURITY.md`
- `TODO.md`

### .aidesigner/
- `.aidesigner/.gitkeep`

### .github/
- `.github/pull_request_template.md`

### .github/ISSUE_TEMPLATE/
- `.github/ISSUE_TEMPLATE/bug-report.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/ISSUE_TEMPLATE/feature-request.yml`

### .github/workflows/
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

### docs/superpowers/specs/
- `docs/superpowers/specs/2026-04-09-community-polish-design.md`
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md`

### reports/
- `reports/security-2026-04-15.md`

### tests/
- *(35 files: 35 .py)*

### triggarr/
- `triggarr/__init__.py`
- `triggarr/__main__.py`
- `triggarr/auth.py`
- `triggarr/changelog.py`
- `triggarr/config.py`
- `triggarr/correlation.py`
- `triggarr/db.py`
- `triggarr/log_buffer.py`
- `triggarr/logging.py`
- `triggarr/startup.py`
- `triggarr/state.py`
- `triggarr/tracking.py`
- `triggarr/update_check.py`
- `triggarr/version.py`

### triggarr/clients/
- `triggarr/clients/__init__.py`
- `triggarr/clients/base.py`
- `triggarr/clients/lidarr.py`
- `triggarr/clients/radarr.py`
- `triggarr/clients/sonarr.py`

### triggarr/models/
- `triggarr/models/__init__.py`
- `triggarr/models/arr.py`
- `triggarr/models/config.py`

### triggarr/search/
- `triggarr/search/__init__.py`
- `triggarr/search/engine.py`
- `triggarr/search/scheduler.py`

### triggarr/static/
- `triggarr/static/site.webmanifest`

### triggarr/static/css/
- `triggarr/static/css/input.css`
- `triggarr/static/css/output.css`

### triggarr/static/js/
- `triggarr/static/js/htmx.min.js`

### triggarr/templates/
- `triggarr/templates/base-auth.html`
- `triggarr/templates/base.html`
- `triggarr/templates/dashboard.html`
- `triggarr/templates/history.html`
- `triggarr/templates/login.html`
- `triggarr/templates/settings.html`
- `triggarr/templates/setup.html`

### triggarr/templates/partials/
- `triggarr/templates/partials/activity_rail.html`
- `triggarr/templates/partials/app_card.html`
- `triggarr/templates/partials/connection_pill.html`
- `triggarr/templates/partials/health_summary.html`
- `triggarr/templates/partials/history_results.html`
- `triggarr/templates/partials/log_viewer.html`
- `triggarr/templates/partials/migration_banner.html`
- `triggarr/templates/partials/security_apikey.html`
- `triggarr/templates/partials/security_password.html`
- `triggarr/templates/partials/stats_row.html`

### triggarr/web/
- `triggarr/web/__init__.py`
- `triggarr/web/middleware.py`
- `triggarr/web/routes.py`
- `triggarr/web/security.py`
- `triggarr/web/validation.py`
