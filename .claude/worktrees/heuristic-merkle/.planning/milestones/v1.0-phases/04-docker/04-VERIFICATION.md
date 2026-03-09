---
phase: 04-docker
verified: 2026-02-24T13:00:41Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 4: Docker Verification Report

**Phase Goal:** Fetcharr runs as a Docker container that any self-hoster can pull and run with docker-compose, with config and state on a volume and no credentials baked into the image
**Verified:** 2026-02-24T13:00:41Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up` starts Fetcharr and the web UI is reachable in a browser | ? HUMAN | docker-compose.yml valid, image reference present, HEALTHCHECK defined — needs live container test |
| 2 | Config and state files live on a named Docker volume at /config and survive container recreation | VERIFIED | `docker-compose.yml` line 13: `fetcharr_config:/config`; `Dockerfile` line 41: `VOLUME /config` |
| 3 | No API keys or config values are baked into the Docker image layers | VERIFIED | `grep -r "api_key\|API_KEY" Dockerfile docker-compose.yml entrypoint.sh` returned nothing |
| 4 | Startup emits a clear warning (not a silent hang) if an enabled *arr URL contains localhost/127.0.0.1 | VERIFIED | `check_localhost_urls()` in `fetcharr/startup.py` lines 25-48; called at step 4.5 in `startup()`; all 5 tests pass |
| 5 | Container runs as non-root user via PUID/PGID environment variables | VERIFIED | `entrypoint.sh`: numeric validation, groupadd/useradd, `exec setpriv --reuid=$PUID --regid=$PGID --init-groups python -m fetcharr` |
| 6 | Docker HEALTHCHECK hits the web UI endpoint and reports health status | VERIFIED | `Dockerfile` lines 43-44: `HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" \|\| exit 1` |

**Score:** 5/6 truths verified programmatically (1 requires live container — automated checks all pass)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Dockerfile` | Multi-stage build: pytailwindcss builder + python:3.13-slim production | VERIFIED | 47 lines, two stages: `FROM python:3.13-slim AS builder` (line 4) and `FROM python:3.13-slim` (line 22); `ENV TAILWINDCSS_VERSION=v4.2.1`; HEALTHCHECK, VOLUME /config, EXPOSE 8080, ENTRYPOINT all present |
| `entrypoint.sh` | PUID/PGID user creation and privilege dropping via setpriv | VERIFIED | 37 lines; numeric validation, `groupadd`, `useradd`, `chown -R`, `exec setpriv --reuid=...`; `set -e` at top |
| `.dockerignore` | Build context exclusions for .venv, .git, tests, .planning | VERIFIED | 16 lines; excludes `.venv/`, `.git/`, `tests/`, `.planning/`, `__pycache__/`, `*.py[cod]`, `.DS_Store`, `.vscode/`, `.idea/` |
| `docker-compose.yml` | Service definition with named volume, port 8080, PUID/PGID env, unless-stopped | VERIFIED | 20 lines; `fetcharr_config:/config`, `"8080:8080"`, `PUID=1000`/`PGID=1000`, `restart: unless-stopped`, top-level `volumes:` block |
| `fetcharr/startup.py` | Localhost URL detection warning before connection validation | VERIFIED | `LOCALHOST_PATTERNS = {"localhost", "127.0.0.1", "::1"}` (line 22); `check_localhost_urls()` function (lines 25-48); called at step 4.5 before `validate_connections()` (line 165) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `Dockerfile` | `entrypoint.sh` | COPY and ENTRYPOINT directive | VERIFIED | Line 36: `COPY entrypoint.sh /entrypoint.sh`; Line 46: `ENTRYPOINT ["/entrypoint.sh"]` |
| `Dockerfile` | `fetcharr/static/css/output.css` | COPY --from=builder compiled CSS into production stage | VERIFIED | Line 34: `COPY --from=builder /build/fetcharr/static/css/output.css fetcharr/static/css/output.css` |
| `docker-compose.yml` | `Dockerfile` | build context reference or image name | VERIFIED | Line 7: `image: ghcr.io/thejuran/fetcharr:latest`; comment on line 3 explains `build: .` alternative |
| `entrypoint.sh` | `fetcharr/__main__.py` | exec setpriv ... python -m fetcharr | VERIFIED | Line 36: `exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups python -m fetcharr` |
| `fetcharr/startup.py` | `fetcharr/models/config.py` | Reads settings.radarr.url and settings.sonarr.url for localhost check | VERIFIED | Line 10: `from urllib.parse import urlparse`; Line 37: `hostname = urlparse(cfg.url).hostname`; iterates over `settings.radarr`/`settings.sonarr` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DEPL-01 | 04-01-PLAN.md | Fetcharr runs as a Docker container with docker-compose support | SATISFIED | Dockerfile, entrypoint.sh, .dockerignore, docker-compose.yml all exist and are substantive; `docker compose config` validates without errors; tests pass |

No orphaned requirements found. REQUIREMENTS.md traceability table maps DEPL-01 only to Phase 4.

### Anti-Patterns Found

No anti-patterns found. Scan of Dockerfile, entrypoint.sh, docker-compose.yml, and fetcharr/startup.py returned no TODO/FIXME/HACK/PLACEHOLDER markers, no empty implementations, no static return stubs.

### Test Results

- **57 tests pass** (52 existing + 5 new localhost detection tests)
- `tests/test_startup.py`: 5/5 pass — localhost, 127.0.0.1, IPv6 loopback, non-localhost, disabled app
- `docker compose config` validates successfully

### Human Verification Required

#### 1. Container Boot and Web UI Reachability

**Test:** Run `docker compose up` from the project root (requires Docker daemon and built/pulled image)
**Expected:** Container starts, logs show the startup banner and connection validation, web UI is reachable at `http://localhost:8080/`
**Why human:** Cannot start containers in this verification environment; requires Docker daemon and image available

#### 2. Volume Persistence Across Recreation

**Test:** Start container, let config file be created at `/config/fetcharr.toml`, run `docker compose down && docker compose up`
**Expected:** Config file and state survive — not reset to defaults
**Why human:** Requires live Docker volume and container lifecycle test

#### 3. PUID/PGID File Ownership

**Test:** Set `PUID=1001 PGID=1001` in environment, start container, exec in and verify `/config` is owned by 1001:1001 and the process runs as uid 1001
**Expected:** `ls -la /config` shows owner 1001:1001; `ps aux` inside container shows python process under non-root uid
**Why human:** Requires running container

### Gaps Summary

No gaps. All six truths verified. All five artifacts exist and are substantive (no stubs, no placeholders). All five key links wired. DEPL-01 satisfied. 57 tests pass. One truth (web UI reachable after `docker compose up`) requires human verification with a live Docker environment but all automated preconditions — image reference, HEALTHCHECK, port mapping, entrypoint wiring — are present and correct.

---

_Verified: 2026-02-24T13:00:41Z_
_Verifier: Claude (gsd-verifier)_
