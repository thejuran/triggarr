# Phase 4: Docker - Research

**Researched:** 2026-02-24
**Domain:** Docker containerization, multi-stage builds, PUID/PGID, self-hoster conventions
**Confidence:** HIGH

## Summary

Fetcharr is a Python/FastAPI application with pytailwindcss-compiled CSS, TOML config at `/config/fetcharr.toml`, and JSON state at `/config/state.json`. Dockerizing it requires a two-stage Dockerfile: a builder stage that installs pytailwindcss to download the Linux-native Tailwind CSS binary and compile `output.css`, and a slim production stage that installs only runtime dependencies and copies the compiled CSS. The `/config` directory serves as the single volume mount point, following the *arr ecosystem convention that Radarr/Sonarr users already know.

The PUID/PGID pattern from LinuxServer.io images provides non-root execution with configurable file ownership. An entrypoint script creates a user with the specified UID/GID, chowns `/config`, and uses `setpriv` (available in Debian slim images) to drop to that user before executing the application. The healthcheck uses Python's stdlib `urllib.request` since `python:3.13-slim` does not include `curl` or `wget`.

**Primary recommendation:** Single plan implementing a multi-stage Dockerfile (pytailwindcss builder + python:3.13-slim production), docker-compose.yml with named volume and PUID/PGID environment variables, entrypoint.sh with setpriv-based user switching, and localhost URL detection warning at startup.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Publish to GHCR: ghcr.io/thejuran/fetcharr
- Base image: python:3.13-slim for production stage
- Tag strategy: `:latest` only when a semver tag is present, otherwise `:dev`
- Dockerfile only for now -- no CI/GitHub Actions workflow in this phase
- Single mount point: `/config` inside the container
- Both config.toml and state.json live in `/config`
- On first run with no config.toml, generate a default config with placeholder values and log setup instructions
- Apps disabled by default in generated config -- user must fill in URL + API key and explicitly enable
- Localhost/127.0.0.1 detection: log a clear warning explaining the Docker networking issue (suggest host.docker.internal or service name), but keep running -- user can fix via web UI
- Include Docker HEALTHCHECK hitting the web UI HTTP endpoint
- Run as non-root with PUID/PGID environment variable support (LinuxServer.io pattern)
- Log to stdout only -- `docker logs` is the interface, no file-based logging
- Default host port: 8080 (avoids conflict with Radarr 7878 / Sonarr 8989)
- Restart policy: unless-stopped
- Fetcharr service only -- no example *arr services (users already have their stack)
- Named Docker volume for /config (not bind mount)

### Claude's Discretion
- Multi-stage build structure and layer optimization
- Exact HEALTHCHECK interval/timeout/retries
- PUID/PGID entrypoint script implementation details
- Default config.toml placeholder text and log message wording

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPL-01 | Fetcharr runs as a Docker container with docker-compose support | Multi-stage Dockerfile, docker-compose.yml with named volume, PUID/PGID support, HEALTHCHECK, localhost detection |
</phase_requirements>

## Standard Stack

### Core
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| python:3.13-slim | 3.13 (bookworm) | Production base image | User decision; slim variant balances size with compatibility |
| pytailwindcss | 0.3.0 | Builder stage CSS compilation | Already a dev dependency; downloads standalone Tailwind binary without Node.js |
| setpriv | util-linux (in Debian bookworm) | Non-root user switching | Already in python:3.13-slim; no extra install needed; runs as PID 1 for signal handling |

### Supporting
| Component | Purpose | When to Use |
|-----------|---------|-------------|
| .dockerignore | Exclude .venv, .git, __pycache__, tests, .planning from build context | Always -- required for clean builds |
| PYTHONUNBUFFERED=1 | Ensures Python output goes straight to stdout for `docker logs` | Always in Docker Python images |
| PYTHONDONTWRITEBYTECODE=1 | Prevents .pyc files in container | Always in Docker Python images |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| setpriv | gosu | gosu requires separate install; setpriv already in Debian base images since Buster |
| python:3.13-slim | python:3.13-alpine | Alpine uses musl libc which can cause issues with some Python packages; slim is safer |
| pytailwindcss in builder | Pre-compiled output.css checked into repo | Would eliminate builder stage but requires manual CSS rebuild on changes |

## Architecture Patterns

### Recommended Dockerfile Structure
```
Stage 1: builder (python:3.13-slim)
├── Install pytailwindcss
├── Download Tailwind CSS Linux binary (tailwindcss_install)
├── Copy source for CSS compilation
├── Run: tailwindcss -i input.css -o output.css --minify
└── Output: compiled output.css artifact

Stage 2: production (python:3.13-slim)
├── ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
├── Install runtime deps only (pip install --no-cache-dir .)
├── COPY compiled output.css from builder
├── COPY entrypoint.sh
├── EXPOSE 8080
├── HEALTHCHECK using python3 -c urllib.request
├── VOLUME /config
└── ENTRYPOINT ["entrypoint.sh"]
```

### Pattern 1: Multi-Stage CSS Build
**What:** Builder stage installs pytailwindcss, downloads the Linux-native Tailwind binary, compiles CSS, then the production stage copies only the compiled output.css. The pytailwindcss binary (~73MB) and the package itself never appear in the production image.
**When to use:** Always -- pytailwindcss is a dev dependency only.
**Key detail:** pytailwindcss stores the binary at `site-packages/pytailwindcss/bin/{version}/tailwindcss`. The `tailwindcss_install` command pre-downloads it. In Docker on Linux x86_64, it downloads the `tailwindcss-linux-x64` binary from GitHub releases. Pin the version with `ENV TAILWINDCSS_VERSION=v4.2.1` for reproducible builds.
**Example:**
```dockerfile
# Stage 1: Build CSS
FROM python:3.13-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY fetcharr/ fetcharr/
RUN pip install --no-cache-dir pytailwindcss && \
    tailwindcss_install && \
    tailwindcss -i fetcharr/static/css/input.css -o fetcharr/static/css/output.css --minify
```

### Pattern 2: PUID/PGID Entrypoint with setpriv
**What:** Entrypoint script runs as root to create a user matching the host PUID/PGID, chowns /config, then drops to that user with setpriv to run the application as PID 1.
**When to use:** Always for self-hosted containers where file ownership on bind mounts matters.
**Key detail:** `setpriv --reuid=$PUID --regid=$PGID --init-groups` replaces the current process (exec), maintaining PID 1 for proper signal handling (SIGTERM from Docker stop). Default PUID=1000, PGID=1000 matches most Linux desktop users.
**Example:**
```bash
#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Create group if it doesn't exist
if ! getent group "$PGID" > /dev/null 2>&1; then
    groupadd -g "$PGID" fetcharr
fi

# Create user if it doesn't exist
if ! getent passwd "$PUID" > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -d /config -s /bin/bash fetcharr
fi

# Ensure /config ownership
chown -R "$PUID:$PGID" /config

# Drop to non-root user and exec the app
exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups \
    python -m fetcharr
```

### Pattern 3: Python stdlib HEALTHCHECK
**What:** Use Python's urllib.request for the HEALTHCHECK since python:3.13-slim lacks curl/wget. Inline as a one-liner in the Dockerfile.
**When to use:** Any Python Docker image without curl installed.
**Example:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1
```

### Pattern 4: Localhost URL Detection
**What:** At startup, check if any enabled app's URL contains `localhost`, `127.0.0.1`, or `::1`. Log a warning explaining that in Docker, localhost refers to the container itself, not the host. Suggest `host.docker.internal` (Docker Desktop) or the service name from docker-compose.
**When to use:** On every startup for every enabled app URL.
**Key detail:** Per user decision, log the warning but keep running -- user can fix via the web UI config editor. Check should happen after config loads but before connection validation.

### Anti-Patterns to Avoid
- **Baking credentials into image layers:** Never `COPY config.toml` or use `ENV API_KEY=...` in the Dockerfile. The `/config` volume is runtime-only.
- **Running as root:** Always use the PUID/PGID entrypoint to drop privileges. Root processes create root-owned files on volumes that the host user can't modify.
- **Installing curl for healthcheck:** Adds ~10MB to the image and a potential attack surface. Python's stdlib works fine.
- **Using `CMD` instead of `ENTRYPOINT` + `CMD`:** The entrypoint must handle user creation before the app starts. Use `ENTRYPOINT ["entrypoint.sh"]` and avoid overriding it in compose.
- **Hardcoding TAILWINDCSS_VERSION without pinning:** The `latest` tag can download different versions between builds, breaking reproducibility.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-root user in Docker | Custom uid/gid manipulation with raw chown | setpriv + PUID/PGID pattern | Signal handling, PID 1, well-understood by self-hosters |
| CSS compilation in Docker | Node.js stage or npm install | pytailwindcss in builder stage | Already a project dep; downloads standalone binary; no Node.js needed |
| Container healthcheck | Custom health monitoring script | Dockerfile HEALTHCHECK + python urllib | Built into Docker engine; surfaces in `docker ps` and compose |

**Key insight:** Self-hosters expect the LinuxServer.io conventions (PUID/PGID, /config volume, named volumes). Deviation from these patterns causes confusion and support burden.

## Common Pitfalls

### Pitfall 1: pytailwindcss Downloads macOS Binary on Linux
**What goes wrong:** If you install pytailwindcss and immediately run `tailwindcss`, it auto-downloads based on `platform.system()`. On macOS dev machines the binary is macOS-native. This binary would fail in Docker's Linux builder stage.
**Why it happens:** pytailwindcss detects the platform at runtime. The builder stage runs on Linux, so it correctly downloads the Linux binary. The pitfall is if someone tries to copy a pre-downloaded binary from their dev machine.
**How to avoid:** Always run `tailwindcss_install` inside the Docker builder stage. Never copy the `.venv` or pytailwindcss bin directory into the image. The builder downloads a fresh Linux binary.
**Warning signs:** `Exec format error` when running tailwindcss in the builder stage.

### Pitfall 2: /config Volume Permissions After Container Recreation
**What goes wrong:** If PUID/PGID changes between container runs, files on the volume may be owned by the old UID/GID, causing permission denied errors.
**Why it happens:** Docker named volumes persist data across container recreations. The entrypoint `chown -R` on every start handles this.
**How to avoid:** The entrypoint script runs `chown -R "$PUID:$PGID" /config` on every startup. For large config directories (not an issue here with just 2 files) this could be slow, but Fetcharr's /config is tiny.
**Warning signs:** `PermissionError` when writing config.toml or state.json.

### Pitfall 3: Localhost URLs in Docker
**What goes wrong:** User copies their working host config into the Docker container. URLs like `http://localhost:7878` point to the container itself, not the host where Radarr runs.
**Why it happens:** Docker containers have their own network namespace. `localhost` inside a container refers to that container.
**How to avoid:** Startup detection checks for `localhost`, `127.0.0.1`, or `::1` in app URLs and logs a clear warning with alternatives. Per user decision, the app keeps running so the user can fix via web UI.
**Warning signs:** Connection timeout or "connection refused" errors when validating *arr connections.

### Pitfall 4: Config File Missing on First Run Causes Immediate Exit
**What goes wrong:** Container starts, no config.toml exists, Fetcharr generates default config and exits with code 1. Docker restarts it (unless-stopped), same thing happens, infinite restart loop.
**Why it happens:** The existing `ensure_config()` calls `sys.exit(1)` when config is missing. With `restart: unless-stopped`, Docker keeps restarting it.
**How to avoid:** This behavior is actually correct and desired. The default config has `enabled = false` for both apps, so even if we changed the exit behavior, pydantic validation would fail with "at least one app must be configured." The user sees the message in `docker logs`, edits the config on the volume, and the next restart works. The restart loop generates clear log messages each time.
**Warning signs:** Container in restart loop showing "Default config written to /config/fetcharr.toml" in logs.

### Pitfall 5: Build Context Too Large
**What goes wrong:** Docker sends the entire project directory including .venv (~300MB), .git, __pycache__, and tests to the daemon.
**Why it happens:** Missing or incomplete .dockerignore file.
**How to avoid:** Create a comprehensive .dockerignore excluding .venv, .git, __pycache__, *.pyc, tests/, .planning/, .pytest_cache/, .DS_Store.
**Warning signs:** Slow `docker build` with "Sending build context" taking many seconds.

## Code Examples

### Complete Dockerfile (Multi-Stage)
```dockerfile
# Stage 1: Build Tailwind CSS
FROM python:3.13-slim AS builder

WORKDIR /build
ENV TAILWINDCSS_VERSION=v4.2.1

COPY pyproject.toml .
COPY fetcharr/ fetcharr/

RUN pip install --no-cache-dir pytailwindcss && \
    tailwindcss_install && \
    tailwindcss -i fetcharr/static/css/input.css \
                -o fetcharr/static/css/output.css \
                --minify

# Stage 2: Production
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install runtime dependencies only
COPY pyproject.toml .
COPY fetcharr/ fetcharr/
RUN pip install --no-cache-dir .

# Copy compiled CSS from builder (overwrite the dev version)
COPY --from=builder /build/fetcharr/static/css/output.css \
     fetcharr/static/css/output.css

# Entrypoint for PUID/PGID support
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080
VOLUME /config

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
```

### Complete docker-compose.yml
```yaml
services:
  fetcharr:
    image: ghcr.io/thejuran/fetcharr:latest
    container_name: fetcharr
    environment:
      - PUID=1000
      - PGID=1000
    volumes:
      - fetcharr_config:/config
    ports:
      - "8080:8080"
    restart: unless-stopped

volumes:
  fetcharr_config:
```

### Complete entrypoint.sh
```bash
#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Validate numeric values
if ! [[ "$PUID" =~ ^[0-9]+$ ]]; then
    echo "WARNING: PUID is not numeric, defaulting to 1000"
    PUID=1000
fi
if ! [[ "$PGID" =~ ^[0-9]+$ ]]; then
    echo "WARNING: PGID is not numeric, defaulting to 1000"
    PGID=1000
fi

# Create group if GID doesn't exist
if ! getent group "$PGID" > /dev/null 2>&1; then
    groupadd -g "$PGID" fetcharr
fi

# Create user if UID doesn't exist
if ! getent passwd "$PUID" > /dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -d /config -s /sbin/nologin fetcharr
fi

# Ensure /config ownership
chown -R "$PUID:$PGID" /config

# Drop privileges and run Fetcharr
exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups \
    python -m fetcharr
```

### Localhost Detection (Python)
```python
import re
from urllib.parse import urlparse

LOCALHOST_PATTERNS = {"localhost", "127.0.0.1", "::1"}

def check_localhost_urls(settings) -> None:
    """Warn if any enabled app URL points to localhost."""
    for name in ("radarr", "sonarr"):
        cfg = getattr(settings, name)
        if not cfg.enabled:
            continue
        parsed = urlparse(cfg.url)
        hostname = parsed.hostname or ""
        if hostname in LOCALHOST_PATTERNS:
            logger.warning(
                "{app} URL ({url}) uses localhost, which inside Docker "
                "refers to the container itself, not your host machine. "
                "Use 'host.docker.internal' (Docker Desktop) or the "
                "container/service name (e.g. 'http://radarr:7878') instead.",
                app=name.title(),
                url=cfg.url,
            )
```

### .dockerignore
```
.venv/
venv/
.git/
.gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.pytest_cache/
tests/
.planning/
.idea/
.vscode/
.DS_Store
*.swp
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| gosu for privilege dropping | setpriv (in util-linux) | Available since Debian Buster (2019) | No extra package install needed |
| curl in HEALTHCHECK | Python urllib.request one-liner | Best practice since 2023+ | Smaller image, no extra packages |
| Alpine for small images | Slim (Debian bookworm) | Ongoing shift | Better compatibility, musl issues avoided |
| Docker Compose v2 `docker-compose` | `docker compose` (plugin) | 2023 | v2 still works but plugin is standard |

**Note on docker-compose.yml:** The file format is compatible with both `docker-compose` (standalone) and `docker compose` (plugin). The compose file uses the modern `services:` top-level key without the `version:` field, which is the current best practice.

## Open Questions

1. **Tailwind CSS version pinning strategy**
   - What we know: `TAILWINDCSS_VERSION=v4.2.1` matches the current dev environment
   - What's unclear: Whether to update this pin automatically or manually
   - Recommendation: Pin to `v4.2.1` now; update manually when upgrading Tailwind. Add a comment in the Dockerfile explaining the pin.

2. **First-run restart loop UX**
   - What we know: `ensure_config()` exits with code 1 when no config exists. With `restart: unless-stopped`, Docker will keep restarting.
   - What's unclear: Whether this restart loop is confusing for users or acceptable
   - Recommendation: Acceptable. Each restart prints a clear message. The alternative (staying alive with no config) is worse because the pydantic validator requires at least one enabled app. User flow: `docker compose up` -> see logs -> `docker exec` or volume edit -> container auto-restarts -> works. This matches Radarr/Sonarr behavior.

## Sources

### Primary (HIGH confidence)
- pytailwindcss source code (inspected locally) - binary storage at `site-packages/pytailwindcss/bin/{version}/tailwindcss`, platform detection via `platform.system()`/`platform.machine()`
- Docker official docs (https://docs.docker.com/build/building/multi-stage/) - multi-stage build patterns
- LinuxServer.io docs (https://docs.linuxserver.io/general/understanding-puid-and-pgid/) - PUID/PGID pattern and rationale
- Servarr Wiki (https://wiki.servarr.com/docker-guide) - *arr ecosystem Docker conventions
- Fetcharr source code (inspected locally) - CONFIG_PATH=/config/fetcharr.toml, STATE_PATH=/config/state.json, port 8080, ensure_config exit behavior

### Secondary (MEDIUM confidence)
- NiceGUI entrypoint.sh (https://github.com/zauberzeug/nicegui/blob/main/docker-entrypoint.sh) - setpriv implementation reference with PUID/PGID validation
- PhotoPrism gosu-to-setpriv PR (https://github.com/photoprism/photoprism/pull/2730) - setpriv as gosu replacement rationale
- FastAPI Docker best practices (https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/) - Python Docker env vars, healthcheck patterns
- Docker HEALTHCHECK without curl (https://muratcorlu.com/docker-healthcheck-without-curl-or-wget/) - urllib.request alternative

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python Docker images, pytailwindcss binary management, and setpriv are all inspected/verified
- Architecture: HIGH - Multi-stage Dockerfile, PUID/PGID, and healthcheck patterns are well-established and verified against official docs and real implementations
- Pitfalls: HIGH - Localhost networking issue is documented by Docker; pytailwindcss platform detection verified by source inspection; permission issues are fundamental Docker behavior

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain, patterns don't change frequently)
