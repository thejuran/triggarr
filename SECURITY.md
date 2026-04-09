# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.x     | Yes       |
| 1.x     | No        |

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Please use [GitHub's private vulnerability reporting](https://github.com/thejuran/triggarr/security/advisories/new) to report security issues. You will receive a response within 7 days.

## Security Model

Triggarr is a single-process automation daemon that connects to Radarr and Sonarr instances. The following security mechanisms are in place:

### Credential Protection

- **SecretStr for API keys** -- All instance API keys are stored as Pydantic `SecretStr` fields. The secret value is only unwrapped at HTTP client initialization (`get_secret_value()`), never serialized to logs, responses, or HTML.
- **Loguru redaction** -- A custom redacting sink filters all collected API key values from log output before writing. Secrets are collected at startup and passed to the redaction filter, covering both log messages and exception tracebacks.

### Web Security

- **CSRF protection** -- `OriginCheckMiddleware` validates the `Origin` and `Referer` headers on state-changing requests (POST, PUT, PATCH, DELETE), rejecting cross-origin submissions with 403 Forbidden.
- **SSRF validation** -- URL inputs are validated against an allow-list of schemes (`http`, `https`) and a block-list of cloud metadata and link-local hostnames to prevent server-side request forgery.
- **Input clamping** -- Integer form values are clamped to safe bounds (minimum/maximum) rather than rejected, preventing overflow or abuse of numeric settings.

### Data Integrity

- **Atomic file writes** -- All config (TOML) and state (JSON) writes use a write-to-tempfile, fsync, then rename pattern. This prevents corruption from interrupted writes or container restarts.

### Container Hardening

- **Multi-stage Docker build** -- Tailwind CSS compilation happens in a builder stage; only the compiled CSS artifact is copied to the production image. Build tools are not present at runtime.
- **PUID/PGID privilege dropping** -- The entrypoint creates a non-root user with the specified UID/GID and drops privileges via `setpriv --reuid/--regid` with `--no-new-privileges` (where supported).
- **Health check** -- A built-in Docker HEALTHCHECK verifies the application is responsive.
