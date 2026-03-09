# Phase 5: Security Hardening - Research

**Researched:** 2026-02-24
**Domain:** Web security (CSRF, SSRF, input validation), Docker hardening, static asset bundling
**Confidence:** HIGH

## Summary

Phase 5 hardens six distinct attack surfaces in Fetcharr: cross-origin request forgery on POST endpoints, server-side request forgery via user-supplied URLs, integer input abuse on form fields, log-level injection, Docker privilege escalation, config file permission leaks, and external CDN dependency. All six areas are well-understood security domains with clear, standard mitigations that use Python stdlib or minimal code changes -- no new dependencies are needed.

The project has no authentication or session cookies, which simplifies CSRF defense. The requirement specifies Origin/Referer header validation (not token-based CSRF), which is the right fit: a lightweight FastAPI middleware checks that the `Origin` or `Referer` header on POST requests matches the server's own host, rejecting cross-origin requests with 403. For SSRF, Python's `urllib.parse` + `ipaddress` stdlib modules provide scheme validation and metadata endpoint blocking. Integer clamping and log-level allowlisting are pure Python. Docker hardening is docker-compose.yml and entrypoint.sh edits. htmx bundling is downloading the pinned .min.js file into static/.

**Primary recommendation:** Implement all six hardening areas as pure Python/config changes with zero new dependencies. Use a FastAPI middleware for Origin validation, `ipaddress` stdlib for SSRF blocking, `max(min())` clamping for integers, docker-compose `security_opt` + `cap_drop` for Docker, `os.chmod` for file permissions, and a vendored htmx.min.js for CDN removal.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SECR-02 | State-changing POST endpoints reject cross-origin requests via Origin/Referer validation | Origin/Referer middleware pattern (Architecture Pattern 1) |
| SECR-03 | ArrConfig URL validates scheme (http/https) and blocks cloud metadata endpoints | URL validation with `urllib.parse` + `ipaddress` stdlib (Architecture Pattern 2) |
| SECR-04 | All form integer fields are bounds-checked and never crash on non-integer input | Integer clamping helper with try/except + min/max (Architecture Pattern 3) |
| SECR-05 | Docker container drops all capabilities, binds to localhost, and sets no-new-privileges | docker-compose.yml `cap_drop`, `security_opt`, port binding (Architecture Pattern 4) |
| SECR-06 | Config file written with restrictive permissions (0o600) | `os.chmod` after every write (Architecture Pattern 5) |
| SECR-07 | htmx bundled locally -- no external CDN or unpinned script tag | Vendored htmx.min.js in static/js/ (Architecture Pattern 6) |
</phase_requirements>

## Standard Stack

### Core

No new libraries are needed. All hardening uses existing dependencies and Python stdlib.

| Library/Module | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| `urllib.parse` | stdlib | URL scheme extraction and hostname parsing | Built-in, zero dependency, well-tested |
| `ipaddress` | stdlib | IP address classification (private, link-local, loopback) | Built-in, handles IPv4/IPv6, edge cases covered |
| `os` | stdlib | File permission setting (`os.chmod`) | Built-in, POSIX-compliant |
| FastAPI middleware | existing dep | Origin/Referer header validation | Already in stack, no new install |
| htmx | 2.0.8 | Frontend interactivity (vendored, not new dep) | Already used via CDN -- moving to local file |

### Supporting

None. All work is stdlib + existing dependencies.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Origin/Referer middleware | fastapi-csrf-protect (token-based) | Adds dependency, requires cookies, overkill for no-auth app |
| Origin/Referer middleware | csrf-starlette-fastapi (SameSite cookies) | Requires cookie setup, heavier than needed for local-network app |
| Custom URL validation | pydantic `AnyHttpUrl` type | Doesn't block metadata IPs, only validates URL format |
| Custom `ipaddress` check | ssrf-king or Advocate library | Abandoned/unmaintained, stdlib does enough for our threat model |

**Installation:** No new packages needed.

## Architecture Patterns

### Pattern 1: Origin/Referer Header Validation Middleware

**What:** A FastAPI middleware that intercepts all POST requests and validates the `Origin` (or fallback `Referer`) header matches the server's own host. Rejects cross-origin POSTs with 403 Forbidden.

**When to use:** On every state-changing endpoint (`POST /settings`, `POST /api/search-now/{app}`)

**Why Origin/Referer and not CSRF tokens:**
- Fetcharr has NO authentication and NO session cookies
- Without cookies, the browser has no credentials to silently attach
- The threat model is: a malicious page making cross-origin POST requests to Fetcharr running on the local network
- Origin header check blocks this because browsers always send the Origin header on cross-origin POSTs
- Same-origin requests either have a matching Origin or no Origin header (some older browsers omit it on same-origin, which is safe to allow)

**Implementation approach:**
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class OriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            host = request.headers.get("host", "")

            # Extract origin host for comparison
            if origin:
                from urllib.parse import urlparse
                origin_host = urlparse(origin).netloc
                if origin_host != host:
                    return Response("Forbidden: cross-origin request", status_code=403)
            elif referer:
                from urllib.parse import urlparse
                referer_host = urlparse(referer).netloc
                if referer_host != host:
                    return Response("Forbidden: cross-origin request", status_code=403)
            # If neither Origin nor Referer present: allow (same-origin browser behavior)

        return await call_next(request)
```

**Key detail:** When neither Origin nor Referer is present, the request is allowed. This is correct because:
- Same-origin form POSTs in some browsers may omit both headers
- A cross-origin attack from a malicious website will always include Origin (modern browsers enforce this)
- Privacy-stripping proxies that remove Referer would still have Origin on cross-origin requests

**Where to register:** In `__main__.py` after creating the FastAPI app, before `app.include_router(router)`.

### Pattern 2: URL Scheme + SSRF Validation

**What:** A validation function that checks user-supplied URLs have an allowed scheme (http or https) and do not resolve to cloud metadata or internal-only IP ranges.

**When to use:** In the `save_settings` POST handler, before writing config to disk. Also could be added as a Pydantic validator on `ArrConfig.url`.

**Implementation approach:**
```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
ALLOWED_SCHEMES = {"http", "https"}

def validate_arr_url(url: str) -> tuple[bool, str]:
    """Validate a *arr URL for scheme and SSRF safety.

    Returns (is_valid, error_message).
    """
    if not url.strip():
        return True, ""  # Empty URL is valid (app disabled)

    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"URL scheme must be http or https, got: {parsed.scheme!r}"

    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"

    # Check against known metadata hostnames
    if hostname in BLOCKED_HOSTS:
        return False, f"URL hostname {hostname!r} is blocked (cloud metadata endpoint)"

    # Check if hostname is an IP in a blocked range
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_link_local:  # 169.254.0.0/16 -- covers metadata endpoints
            return False, f"URL resolves to link-local address {hostname}"
    except ValueError:
        pass  # Not an IP literal -- hostname like "radarr", which is fine

    return True, ""
```

**Important considerations:**
- Only block link-local (169.254.0.0/16) to cover metadata endpoints. Do NOT block private ranges (10.x, 172.16.x, 192.168.x) because *arr apps run on the local network by design.
- The `metadata.google.internal` hostname check catches GCP's metadata service which uses a DNS name, not just the IP.
- Do not attempt DNS resolution of hostnames -- that would be a performance issue and could itself be exploited.

### Pattern 3: Integer Clamping with Safe Defaults

**What:** A helper that safely parses form input to an integer, clamping to safe bounds, and never crashing on garbage input.

**When to use:** In `save_settings` when parsing `search_interval`, `search_missing_count`, `search_cutoff_count` from form data.

**Implementation approach:**
```python
def safe_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Parse a form value to an integer, clamping to [minimum, maximum].

    Returns default if value is None, empty, or non-numeric.
    """
    if not value:
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, n))
```

**Bounds to enforce:**
| Field | Min | Max | Default | Rationale |
|-------|-----|-----|---------|-----------|
| `search_interval` | 1 | 1440 | 30 | 1 min minimum, 24 hours max |
| `search_missing_count` | 1 | 100 | 5 | At least 1 item, cap at 100 to avoid API hammering |
| `search_cutoff_count` | 1 | 100 | 5 | Same rationale as missing count |

**Current bug:** The existing code does `int(form.get(..., 30))` which will crash with `ValueError` if a non-numeric string is submitted. The `safe_int` helper replaces this.

### Pattern 4: Docker Least-Privilege Defaults

**What:** Harden docker-compose.yml with localhost-only port binding, capability dropping, and no-new-privileges. Update entrypoint.sh to pass `--no-new-privileges` to setpriv.

**docker-compose.yml changes:**
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
      - "127.0.0.1:8080:8080"  # Bind to localhost only
    cap_drop:
      - ALL                     # Drop all Linux capabilities
    security_opt:
      - no-new-privileges:true  # Prevent privilege escalation
    restart: unless-stopped
```

**entrypoint.sh change:** Add `--no-new-privileges` flag to `setpriv`:
```bash
exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups --no-new-privileges python -m fetcharr
```

**Note on `cap_drop: ALL`:** The entrypoint.sh uses `setpriv` (not `su`/`sudo`) which does NOT need `SETUID`/`SETGID` capabilities. `setpriv` works at the syscall level before dropping privileges. The `chown` command in the entrypoint runs as root BEFORE `exec setpriv`, and `groupadd`/`useradd` also run as root before the privilege drop. Since docker-compose `cap_drop` affects the container process itself (PID 1 after `exec`), and by that point we are already the unprivileged user, `cap_drop: ALL` is correct.

**Wait -- potential issue:** `groupadd` and `useradd` in the entrypoint might need capabilities. Let me clarify: Docker container starts as root. The entrypoint script runs as root, creates the user/group, does chown, then `exec setpriv` drops to the unprivileged user. The `cap_drop: ALL` in docker-compose drops capabilities for the final exec'd process, not the entrypoint. Actually -- `cap_drop` in docker-compose drops capabilities from the initial process too. This means `groupadd`, `useradd`, and `chown` run without `CAP_CHOWN`, `CAP_FOWNER`, etc. which will FAIL.

**Correct approach:** Use `cap_add` to keep the specific capabilities needed during entrypoint, then drop them in the `setpriv` exec. OR restructure to use `--inh-caps=-all` in `setpriv` to drop capabilities only for the final process. The cleanest solution for the docker-compose.yml is:

```yaml
    cap_drop:
      - ALL
    cap_add:
      - CHOWN       # Needed for chown in entrypoint
      - SETUID      # Needed for setpriv --reuid
      - SETGID      # Needed for setpriv --regid
```

Then `setpriv --no-new-privileges` ensures the Python process cannot regain any capabilities.

### Pattern 5: Config File Permissions

**What:** After every write of the TOML config file, set file permissions to 0o600 (owner read/write only) to prevent other users on the system from reading API keys.

**When to use:** In `config.py:generate_default_config()` and `routes.py:save_settings()` after every `write_text()` / `config_path.write_text()` call.

**Implementation approach:**
```python
import os

def write_config_secure(config_path: Path, content: str) -> None:
    """Write config content to disk with restrictive permissions."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content)
    os.chmod(config_path, 0o600)
```

**Key detail:** `os.chmod` must be called AFTER `write_text` because `write_text` may recreate the file (Python's `Path.write_text` opens with `w` mode which truncates and writes). The chmod applies to the resulting file. This is not atomic but is sufficient -- the window between write and chmod is negligible, and inside Docker the container is single-user anyway.

### Pattern 6: Vendored htmx.min.js

**What:** Download htmx 2.0.8 minified JS and serve it as a local static file instead of loading from unpkg CDN.

**Steps:**
1. Download `htmx.min.js` from `https://unpkg.com/htmx.org@2.0.8/dist/htmx.min.js`
2. Save to `fetcharr/static/js/htmx.min.js`
3. Update `base.html` to reference the local file:
   ```html
   <script src="{{ url_for('static', path='js/htmx.min.js') }}"></script>
   ```
4. Remove the CDN `<script>` tag

**Why vendor instead of npm:** The project has no Node.js toolchain or bundler. The Tailwind CSS build uses pytailwindcss (a standalone binary). Downloading a single .min.js file and checking it in is the simplest approach for a Python-only project.

### Log Level Allowlist

**What:** The `log_level` form field currently accepts any string. Validate against an explicit allowlist and default to "info" for unknown values.

**Implementation:** In `save_settings`, after reading `form.get("log_level")`:
```python
ALLOWED_LOG_LEVELS = {"debug", "info", "warning", "error"}

raw_level = form.get("log_level", "info").lower().strip()
log_level = raw_level if raw_level in ALLOWED_LOG_LEVELS else "info"
```

**Note:** The settings.html template already uses a `<select>` dropdown with only valid options, so this is defense-in-depth for the case where someone crafts a manual POST request.

### Anti-Patterns to Avoid

- **Do NOT use CSRF tokens for this project:** No auth means no sessions means no cookies to protect. CSRF tokens add complexity (cookie management, template injection, htmx header wiring) for zero benefit beyond what Origin checking provides.
- **Do NOT block private IP ranges in SSRF check:** *arr apps are on the local network by definition. Blocking 10.x/172.x/192.168.x would make the app unusable.
- **Do NOT attempt DNS resolution for SSRF:** Resolving hostnames server-side introduces latency, DNS rebinding attacks, and race conditions. Check the URL string only.
- **Do NOT use `read_only: true` in docker-compose:** The app writes to `/config` volume for config and state persistence. Read-only root filesystem with tmpfs would require careful mount planning for a minimal security gain.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IP range classification | Manual IP string comparison | `ipaddress.ip_address().is_link_local` | Handles IPv4, IPv6, edge cases, octal/hex variants |
| URL parsing | Regex on URL strings | `urllib.parse.urlparse()` | Handles edge cases, encoded characters, relative URLs |
| File permissions | Shell subprocess `chmod` | `os.chmod(path, 0o600)` | Python stdlib, cross-platform within POSIX |

**Key insight:** The stdlib `ipaddress` module properly handles IP encoding tricks (decimal, hex, octal) that would bypass naive string matching against "169.254.169.254".

## Common Pitfalls

### Pitfall 1: Blocking Private IPs Breaks *arr Connectivity

**What goes wrong:** SSRF protection blocks connections to 192.168.x.x, 10.x.x.x, 172.16.x.x where Radarr/Sonarr actually live.
**Why it happens:** Generic SSRF guidance says "block all private IPs" but Fetcharr is a self-hosted tool that ONLY connects to private network services.
**How to avoid:** Only block link-local (169.254.0.0/16) for metadata endpoints, and explicitly block `metadata.google.internal` hostname. Allow all other private ranges.
**Warning signs:** Users report "URL blocked" when entering their actual Radarr/Sonarr URLs.

### Pitfall 2: Docker cap_drop ALL Breaks Entrypoint

**What goes wrong:** `cap_drop: ALL` in docker-compose removes capabilities from PID 1 (the entrypoint shell), causing `groupadd`, `useradd`, and `chown` to fail with "Operation not permitted".
**Why it happens:** Docker applies cap_drop before the entrypoint runs, not after exec.
**How to avoid:** Use `cap_drop: ALL` + `cap_add: CHOWN, SETUID, SETGID` to keep only the capabilities needed for the entrypoint's user setup. The `--no-new-privileges` flag on setpriv ensures the final Python process cannot escalate.
**Warning signs:** Container crashes on startup with "groupadd: Permission denied" or "chown: Operation not permitted".

### Pitfall 3: Missing Origin Header on Same-Origin Requests

**What goes wrong:** Legitimate same-origin form submissions sometimes lack an Origin header (some browsers, some proxy configurations). Rejecting these breaks the settings form.
**Why it happens:** The Origin header is only guaranteed on cross-origin requests. Same-origin requests may or may not include it.
**How to avoid:** Only REJECT when Origin/Referer IS present AND doesn't match. When both are absent, ALLOW the request (it's same-origin or from a context where cross-origin attacks aren't possible).
**Warning signs:** Settings form stops working after enabling CSRF middleware.

### Pitfall 4: Integer Form Fields Crash on Non-Numeric Input

**What goes wrong:** `int(form.get("search_interval", 30))` raises `ValueError` when a crafted POST sends "abc" as the value, causing a 500 error.
**Why it happens:** The HTML `type="number"` attribute is client-side only; any string can be submitted via curl or crafted request.
**How to avoid:** Use try/except with fallback to default, then clamp to safe range.
**Warning signs:** 500 Internal Server Error on settings save with non-standard form data.

### Pitfall 5: setpriv --no-new-privileges Flag Syntax

**What goes wrong:** Using `--no-new-privileges=true` (with `=true`) instead of `--no-new-privileges` (flag only).
**Why it happens:** Confusion with Docker's `security_opt: no-new-privileges:true` syntax.
**How to avoid:** `setpriv --no-new-privileges` is the correct flag syntax (boolean flag, no value).
**Warning signs:** "unrecognized option" error in entrypoint.

## Code Examples

### Safe Integer Parser (used in save_settings)

```python
def safe_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Parse a form value to an integer, clamping to [minimum, maximum]."""
    if not value:
        return default
    try:
        n = int(value)
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, n))

# Usage in save_settings:
new_config[name] = {
    "search_interval": safe_int(form.get(f"{name}_search_interval"), 30, 1, 1440),
    "search_missing_count": safe_int(form.get(f"{name}_search_missing_count"), 5, 1, 100),
    "search_cutoff_count": safe_int(form.get(f"{name}_search_cutoff_count"), 5, 1, 100),
}
```

### URL Validation (used in save_settings and/or ArrConfig validator)

```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
ALLOWED_SCHEMES = {"http", "https"}

def validate_arr_url(url: str) -> tuple[bool, str]:
    """Validate *arr URL for scheme and SSRF safety."""
    if not url.strip():
        return True, ""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"URL scheme must be http or https, got: {parsed.scheme!r}"
    hostname = parsed.hostname
    if not hostname:
        return False, "URL has no hostname"
    if hostname in BLOCKED_HOSTS:
        return False, f"Blocked hostname: {hostname}"
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_link_local:
            return False, f"Link-local address blocked: {hostname}"
    except ValueError:
        pass
    return True, ""
```

### Origin Check Middleware

```python
from urllib.parse import urlparse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin POST requests via Origin/Referer header validation."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            host = request.headers.get("host", "")

            if origin:
                if urlparse(origin).netloc != host:
                    return Response("Forbidden", status_code=403)
            elif referer:
                if urlparse(referer).netloc != host:
                    return Response("Forbidden", status_code=403)
            # Neither header present: allow (same-origin behavior)

        return await call_next(request)
```

### Secure Config Write

```python
import os
from pathlib import Path

def write_config_secure(config_path: Path, content: str) -> None:
    """Write config and set 0o600 permissions."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content)
    os.chmod(config_path, 0o600)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CSRF tokens for all forms | Origin header check for no-auth apps | Mainstream ~2020 | Simpler, no cookie/token management needed |
| Allowlist IPs for SSRF | stdlib `ipaddress` classification | Python 3.3+ | Handles encoding tricks automatically |
| CDN-hosted JS | Vendored/self-hosted JS | Post-2020 supply chain attacks | Eliminates CDN as attack vector and single point of failure |
| Docker `--privileged` | `cap_drop: ALL` + minimal `cap_add` | Docker 1.13+ / Compose v3 | Principle of least privilege |

**Deprecated/outdated:**
- **SameSite=Lax cookies for CSRF defense:** While effective, unnecessary when there are no cookies/sessions to protect
- **htmx from unpkg CDN:** unpkg has had availability issues; vendoring pinned versions is now recommended by htmx docs

## Open Questions

1. **Should URL validation also check at startup (not just settings save)?**
   - What we know: Currently, startup loads from TOML without URL validation. A hand-edited TOML could have a malicious URL.
   - What's unclear: Whether adding validation to `load_settings` / `ArrConfig` model would break existing configs.
   - Recommendation: Add validation in `save_settings` first (the web UI path). Optionally add a Pydantic validator on `ArrConfig.url` that runs at load time too, but be careful not to break existing valid configs. Phase 6 could add startup validation.

2. **Should the htmx.min.js file be committed to the repo or downloaded during Docker build?**
   - What we know: The file is ~47KB minified. Committing it ensures reproducible builds with no network dependency.
   - What's unclear: Whether there's a preference for committed vendor files vs. build-time download.
   - Recommendation: Commit the file. It's small, pinned to a specific version, and eliminates any build-time network dependency.

## Sources

### Primary (HIGH confidence)
- Python `ipaddress` module docs -- `is_link_local`, `is_private` properties for IP classification
- Python `urllib.parse` module docs -- `urlparse()` for URL component extraction
- Python `os` module docs -- `os.chmod()` for POSIX file permissions
- htmx.org official docs -- self-hosting instructions, version 2.0.8 confirmed at unpkg.com/htmx.org@2.0.8/dist/htmx.min.js
- Docker Compose specification -- `cap_drop`, `cap_add`, `security_opt` keys
- FastAPI/Starlette docs -- `BaseHTTPMiddleware` for custom request interception

### Secondary (MEDIUM confidence)
- [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html) -- cap_drop ALL + minimal cap_add pattern
- [Docker Security Best Practices 2026](https://thelinuxcode.com/docker-security-best-practices-2026-hardening-the-host-images-and-runtime-without-slowing-teams-down/) -- no-new-privileges, read-only filesystem guidance
- [OWASP SSRF Prevention](https://www.rapid7.com/blog/post/2021/11/23/owasp-top-10-deep-dive-defending-against-server-side-request-forgery/) -- metadata endpoint blocking, IP range classification

### Tertiary (LOW confidence)
- None. All findings verified with official docs or multiple credible sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All stdlib, no new dependencies, well-understood patterns
- Architecture: HIGH -- Each pattern is straightforward with clear implementation paths
- Pitfalls: HIGH -- Docker cap_drop interaction with entrypoint is the most subtle issue, verified through Docker documentation

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain, no fast-moving dependencies)
