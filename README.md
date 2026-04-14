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

Run `docker compose up -d`, then visit [http://localhost:8484](http://localhost:8484) to configure your Radarr, Sonarr, and/or Lidarr connections.

On first run, a default config file is auto-generated at `/config/triggarr.toml`. Use the web UI to configure -- no need to edit the file by hand.

### Standalone (pip)

Requires Python 3.11+. Download the `.whl` from the [latest release](https://github.com/thejuran/triggarr/releases/latest), or install directly:

```bash
pip install https://github.com/thejuran/triggarr/releases/latest/download/triggarr-2.7.0-py3-none-any.whl
```

Set the config directory and run:

```bash
export TRIGGARR_CONFIG_DIR="$HOME/.config/triggarr"
mkdir -p "$TRIGGARR_CONFIG_DIR"
triggarr
```

Visit [http://localhost:8484](http://localhost:8484) to configure. Config and data files are stored in `TRIGGARR_CONFIG_DIR`.

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

All settings live in `/config/triggarr.toml`. You can also edit everything from the web UI at [http://localhost:8484/settings](http://localhost:8484/settings) -- changes are written to the TOML file and take effect immediately without restart.

```toml
# Triggarr Configuration

[general]
# Log level: debug, info, warning, error
log_level = "info"                  # default: "info"

# Hard max items searched per app per cycle. 0 = unlimited.
# When set, the limit is split proportionally between missing and cutoff searches.
hard_max_per_cycle = 0              # default: 0 (unlimited), valid: 0+

[radarr]
# Radarr connection settings
url = "http://radarr:7878"          # Radarr base URL (string, required if enabled)
api_key = "your-api-key-here"       # From Radarr > Settings > General > API Key
enabled = false                     # default: false -- set to true to activate

search_interval = 30                # default: 30 (minutes between search cycles)
search_missing_count = 5            # default: 5 (missing items to search per cycle)
search_cutoff_count = 5             # default: 5 (cutoff/upgrade items to search per cycle)

[sonarr]
# Sonarr connection settings
url = "http://sonarr:8989"          # Sonarr base URL (string, required if enabled)
api_key = "your-api-key-here"       # From Sonarr > Settings > General > API Key
enabled = false                     # default: false -- set to true to activate

search_interval = 30                # default: 30 (minutes between search cycles)
search_missing_count = 5            # default: 5 (missing items to search per cycle)
search_cutoff_count = 5             # default: 5 (cutoff/upgrade items to search per cycle)

[lidarr]
# Lidarr connection settings
url = "http://lidarr:8686"          # Lidarr base URL (string, required if enabled)
api_key = "your-api-key-here"       # From Lidarr > Settings > General > API Key
enabled = false                     # default: false -- set to true to activate

search_interval = 30                # default: 30 (minutes between search cycles)
search_missing_count = 5            # default: 5 (missing albums to search per cycle)
search_cutoff_count = 5             # default: 5 (cutoff/upgrade albums to search per cycle)
```

Environment variable overrides are supported via pydantic-settings (e.g., `TRIGGARR_GENERAL__LOG_LEVEL=debug`), but TOML is the primary configuration method.

## Security Model

Triggarr has **no authentication**. This is intentional.

### Design philosophy

Triggarr is designed to run on a trusted local network -- behind Tailscale, a VPN, or bound to localhost. No passwords means no credential attack surface.

### What IS protected

- **API keys** are never exposed in HTTP responses or HTML (`SecretStr` discipline throughout)
- **Log output** redacts all configured secrets automatically
- **Config file** written with `0600` permissions (owner-read/write only)
- **Docker container** drops all capabilities except CHOWN, DAC_OVERRIDE, FOWNER, SETUID, SETGID
- **CSRF protection** via Origin header checking on POST requests
- **URL validation** blocks SSRF attempts (non-HTTP schemes, inappropriate public IPs)
- **Security hardening** via `no-new-privileges` applied after privilege setup in entrypoint

### What is NOT protected

Anyone with network access to port 8484 can view the dashboard and edit configuration. There is no login, no session management, no user accounts.

### Recommendation

Bind to localhost (`127.0.0.1:8484:8484` as shown in the docker-compose example) and access via Tailscale or a reverse proxy with authentication.

### Reverse Proxy

When running Triggarr behind a reverse proxy (Nginx, Caddy, Traefik, etc.), configure `TRUSTED_PROXY_IPS` so Triggarr trusts the `X-Forwarded-For` and `X-Forwarded-Proto` headers from your proxy. Without this, Triggarr cannot determine the real client IP or protocol, which affects logging and scheme-aware behavior.

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
      - TRUSTED_PROXY_IPS=172.18.0.1       # Docker network gateway (use 172.18.0.0/16 for the full subnet)
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
