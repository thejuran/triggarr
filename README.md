# Triggarr

[![CI](https://github.com/thejuran/triggarr/actions/workflows/ci.yml/badge.svg)](https://github.com/thejuran/triggarr/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/ghcr.io-thejuran%2Ftriggarr-blue?logo=docker)](https://ghcr.io/thejuran/triggarr)

Python automation daemon that triggers searches in Radarr, Sonarr, and Lidarr on a schedule.

Radarr, Sonarr, and Lidarr don't auto-search for missing and upgrade-eligible media on a timer. Triggarr does -- set a schedule, walk away.

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Install](#install)
- [Configuration Reference](#configuration-reference)
- [Security Model](#security-model)
  - [Reverse Proxy](#reverse-proxy)
- [Development](#development)

## Features

- **Radarr, Sonarr, and Lidarr** — movies, TV shows, and music albums
- Scheduled searches for missing and upgrade-eligible media
- Multi-instance support — run multiple instances of each app with independent schedules
- Tag-based filtering — scope searches to specific tags per instance
- Closed-loop tracking — polls *arr history to confirm what was actually grabbed
- Web dashboard with real-time connection status, grab effectiveness stats, and search history
- In-app changelog — see what's new without leaving the UI
- Browser-based config editor -- no manual TOML editing needed
- Hard max limit to cap searches per cycle (safety ceiling)
- Persistent SQLite search history (survives restarts)
- Docker-first with PUID/PGID support, or standalone pip install

## Screenshots

![Dashboard with app cards, grab rate stats, and live recent activity rail](docs/screenshots/dashboard.png?v=2)

![Search history with filter chips for app, queue type, outcome, and title search](docs/screenshots/history.png?v=2)

![Settings page with general options and per-instance configuration for Radarr, Sonarr, and Lidarr](docs/screenshots/settings.png?v=2)

## Install

### Docker (recommended)

```yaml
# docker-compose.yml
services:
  triggarr:
    image: ghcr.io/thejuran/triggarr:latest
    container_name: triggarr
    environment:
      - PUID=1000    # Your user ID (run `id -u` to find)
      - PGID=1000    # Your group ID (run `id -g` to find)
    volumes:
      - triggarr_config:/config
    ports:
      - "127.0.0.1:8484:8484"  # Localhost only -- use Tailscale or reverse proxy for remote access
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - DAC_OVERRIDE
      - FOWNER
      - SETUID
      - SETGID
    restart: unless-stopped

volumes:
  triggarr_config:
```

Run `docker compose up -d`, then visit [http://localhost:8484](http://localhost:8484) to complete first-run account setup and configure your Radarr, Sonarr, and/or Lidarr connections.

When `TRIGGARR_CONFIG_DIR` is unset, Triggarr uses `/config`, so `triggarr.toml`, `state.json`, and `triggarr.db` live on the mounted volume. On an empty volume, Triggarr writes `/config/triggarr.toml` first; with the `restart: unless-stopped` example above, the container then starts normally on the next restart.

### Standalone (pip)

Requires Python 3.11+. Download the `.whl` from the [latest release](https://github.com/thejuran/triggarr/releases/latest), or install the current release directly:

```bash
pip install https://github.com/thejuran/triggarr/releases/latest/download/triggarr-2.7.1-py3-none-any.whl
```

Set an absolute config directory before starting Triggarr:

```bash
export TRIGGARR_CONFIG_DIR="$HOME/.config/triggarr"
mkdir -p "$TRIGGARR_CONFIG_DIR"
triggarr
```

Standalone installs store `triggarr.toml`, `state.json`, and `triggarr.db` in `TRIGGARR_CONFIG_DIR`. If the config file does not exist yet, the first `triggarr` run writes a default template and exits; run `triggarr` again, then visit [http://localhost:8484](http://localhost:8484) to complete setup and configure apps.

To run in the background, use a process manager like systemd, launchd, or supervisor. A minimal systemd unit:

```ini
# /etc/systemd/system/triggarr.service
[Unit]
Description=Triggarr
After=network.target

[Service]
Type=simple
User=triggarr
Environment=TRIGGARR_CONFIG_DIR=/var/lib/triggarr
ExecStart=/usr/local/bin/triggarr
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Configuration Reference

Runtime config lives in `${TRIGGARR_CONFIG_DIR}/triggarr.toml`; when `TRIGGARR_CONFIG_DIR` is unset, Triggarr uses `/config/triggarr.toml` for Docker compatibility. The config directory must be an absolute path and must be set before the Triggarr process starts.

You can edit settings from the web UI at [http://localhost:8484/settings](http://localhost:8484/settings) -- changes are written to the TOML file and take effect immediately without restart. Each app type is a table of named instances, so use nested tables such as `[radarr.Default]` or `[sonarr.Anime]` rather than putting connection fields directly under the app name.

```toml
# Triggarr Configuration

[general]
# Log level: debug, info, warning, error
log_level = "info"

# Hard max items searched per app per cycle. 0 = unlimited.
# When set, the limit is split proportionally between missing and cutoff searches.
hard_max_per_cycle = 0

# Optional scheduler/API tuning defaults:
# request_timeout = 30.0
# page_size = 50
# max_history_rows = 1000
# tracking_window_minutes = 60
# skip_unreleased = true

# The web setup flow creates auth.username, auth.password_hash,
# auth.api_key, and auth.session_secret. Do not copy example secrets.
[auth]
method = "Forms"                   # Forms, Basic, External, or Disabled

[radarr.Default]
url = "http://radarr:7878"          # Radarr base URL
enabled = true
api_key = "<radarr-api-key>"        # From Radarr > Settings > General > API Key
search_interval = 30                # minutes between search cycles
search_missing_count = 5            # missing movies to search per cycle
search_cutoff_count = 5             # cutoff/upgrade movies to search per cycle
missing_tag = ""                    # optional tag filter; empty = all items
cutoff_tag = ""                     # optional tag filter; empty = all items

[radarr."4K"]
url = "http://radarr-4k:7878"
enabled = false
api_key = "<radarr-4k-api-key>"
search_interval = 60
search_missing_count = 3
search_cutoff_count = 3

[sonarr.Default]
url = "http://sonarr:8989"
enabled = true
api_key = "<sonarr-api-key>"
search_interval = 30
search_missing_count = 5
search_cutoff_count = 5
missing_tag = ""
cutoff_tag = ""

[lidarr.Default]
url = "http://lidarr:8686"
enabled = false
api_key = "<lidarr-api-key>"
search_interval = 30
search_missing_count = 5            # missing albums to search per cycle
search_cutoff_count = 5             # cutoff/upgrade albums to search per cycle
```

Startup-level environment variables such as `TRIGGARR_CONFIG_DIR`, `TRUSTED_PROXY_IPS`, and `ROOT_PATH` are read by the process before the TOML settings are loaded; they are not stored in `triggarr.toml`.

## Security Model

Triggarr includes application authentication by default. A fresh config starts in setup mode; the first browser visit redirects to `/setup`, where you create the local username/password and receive a generated API key. After setup, protected browser routes require either a signed `triggarr_session` cookie or another configured auth method.

### Authentication modes

Configured in `[auth]` as `method`:

- `Forms` (default) — browser login page, bcrypt password hash, signed 30-day session cookie, logout, password change, and login rate limiting.
- `Basic` — HTTP Basic credentials are accepted and can establish the same signed session cookie.
- `External` — Triggarr bypasses local auth because an upstream reverse proxy or SSO layer has already authenticated and authorized the user; enable it only after direct access to port 8484 is blocked and the proxy is the sole path to Triggarr.
- `Disabled` — all routes are accessible without Triggarr auth and a warning is logged periodically. Prefer `External` for reverse-proxy deployments.

Requests may also authenticate with `X-Api-Key` when `auth.api_key` is set. The setup flow and security settings page generate API keys; do not paste real keys into examples or logs.

### What IS protected

- **Application routes** are deny-by-default after setup unless auth is `External` or `Disabled`
- **API keys and auth secrets** are stored as `SecretStr`, redacted from logs, and not exposed in normal settings HTML
- **Password hashes** use bcrypt, and session cookies are signed with a generated session secret
- **Login attempts** are rate-limited per client IP
- **Config file** is written with `0600` permissions (owner-read/write only)
- **Config secrets** in `triggarr.toml` are plaintext on disk; protect them with file permissions and volume security
- **Docker container** drops all capabilities except CHOWN, DAC_OVERRIDE, FOWNER, SETUID, SETGID
- **CSRF protection** via Origin/Referer checking on mutating requests
- **Security headers** include frame denial, MIME-sniffing prevention, same-origin referrer policy, and a restrictive CSP
- **URL validation** blocks SSRF attempts by rejecting non-HTTP schemes and metadata, link-local, loopback, unspecified, or multicast targets
- **Security hardening** via `no-new-privileges` applied after privilege setup in entrypoint when the host supports it

### Recommendation

Keep the compose example's localhost bind (`127.0.0.1:8484:8484`) unless Triggarr is behind Tailscale, a VPN, or a reverse proxy. For proxy/SSO deployments, set `auth.method = "External"` only after confirming the proxy enforces authentication and authorization and is the sole path to Triggarr; keep port 8484 bound to localhost or firewalled from direct clients.

### Reverse Proxy

When running Triggarr behind a reverse proxy (Nginx, Caddy, Traefik, etc.), configure `TRUSTED_PROXY_IPS` so Uvicorn accepts forwarded client and scheme headers only from that proxy. Accepted `X-Forwarded-For` values set the client IP; accepted `X-Forwarded-Proto` values become the ASGI request scheme used by scheme-aware behavior such as Secure cookie emission. Without this, Triggarr sees the proxy/default client and protocol. Keep direct access to port 8484 blocked so clients cannot send proxy headers straight to Triggarr.

> These are startup-level environment variables read directly by the process — they are not part of `triggarr.toml` and do not use the `TRIGGARR_` prefix.

| Environment Variable | Default | Description |
|---|---|---|
| `TRUSTED_PROXY_IPS` | `127.0.0.1` | Comma-separated list of trusted proxy IPs or CIDR subnets. Set this to the IP address or subnet of your reverse proxy. **Do not use `*`** — it allows any client to forge its apparent IP address. |
| `ROOT_PATH` | *(empty)* | URL path prefix when Triggarr is served under a subpath (e.g. `/triggarr`). Sets the ASGI `root_path` so links and assets resolve correctly. |

**Example: Nginx reverse proxy on the same Docker network**

```yaml
services:
  triggarr:
    image: ghcr.io/thejuran/triggarr:latest
    container_name: triggarr
    environment:
      - PUID=1000
      - PGID=1000
      - TRUSTED_PROXY_IPS=172.18.0.1       # Prefer the specific proxy IP; use a CIDR only on fully trusted Docker networks
    volumes:
      - triggarr_config:/config
    ports:
      - "127.0.0.1:8484:8484"
    restart: unless-stopped
```

If your proxy runs on the Docker host (e.g. host-networked Nginx), set `TRUSTED_PROXY_IPS=172.17.0.1` (the default Docker gateway) or the specific IP your proxy uses to reach Triggarr.

**Example: subpath behind a reverse proxy**

```yaml
    environment:
      - TRUSTED_PROXY_IPS=172.18.0.1
      - ROOT_PATH=/triggarr
```

Then configure your proxy to forward `/triggarr` to Triggarr's port 8484.

When no proxy is configured, the default trust list (`127.0.0.1`) ensures forwarded headers are only honored from localhost.

### Synology NAS

Synology DSM ships a stripped-down `setpriv` that doesn't support `--no-new-privileges`. Triggarr detects this automatically and skips the flag — no configuration changes needed.

## Development

```bash
uv sync --extra dev                    # Install dependencies
uv run pytest tests/ -x -q             # Run tests
uv run ruff check triggarr/ tests/     # Lint
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch  # CSS dev
docker build -t triggarr:local .       # Local Docker build
```
