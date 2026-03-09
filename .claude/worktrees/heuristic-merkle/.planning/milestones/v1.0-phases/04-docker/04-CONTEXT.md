# Phase 4: Docker - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Fetcharr runs as a Docker container that any self-hoster can pull and run with docker-compose, with config and state on a volume and no credentials baked into the image. Multi-stage Dockerfile with pytailwindcss builder stage and slim production image.

</domain>

<decisions>
## Implementation Decisions

### Image & Registry
- Publish to GHCR: ghcr.io/thejuran/fetcharr
- Base image: python:3.13-slim for production stage
- Tag strategy: `:latest` only when a semver tag is present, otherwise `:dev`
- Dockerfile only for now — no CI/GitHub Actions workflow in this phase

### Volume & Config Layout
- Single mount point: `/config` inside the container
- Both config.toml and state.json live in `/config`
- On first run with no config.toml, generate a default config with placeholder values and log setup instructions
- Apps disabled by default in generated config — user must fill in URL + API key and explicitly enable

### Startup Behavior
- Localhost/127.0.0.1 detection: log a clear warning explaining the Docker networking issue (suggest host.docker.internal or service name), but keep running — user can fix via web UI
- Include Docker HEALTHCHECK hitting the web UI HTTP endpoint
- Run as non-root with PUID/PGID environment variable support (LinuxServer.io pattern)
- Log to stdout only — `docker logs` is the interface, no file-based logging

### Compose Defaults
- Default host port: 8080 (avoids conflict with Radarr 7878 / Sonarr 8989)
- Restart policy: unless-stopped
- Fetcharr service only — no example *arr services (users already have their stack)
- Named Docker volume for /config (not bind mount)

### Claude's Discretion
- Multi-stage build structure and layer optimization
- Exact HEALTHCHECK interval/timeout/retries
- PUID/PGID entrypoint script implementation details
- Default config.toml placeholder text and log message wording

</decisions>

<specifics>
## Specific Ideas

- Follow the *arr ecosystem convention of `/config` as the data directory — familiar to Radarr/Sonarr users
- PUID/PGID pattern matches LinuxServer.io images that self-hosters already know
- The localhost detection is specifically for the common Docker networking mistake where users copy their host config into a container

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-docker*
*Context gathered: 2026-02-23*
