# Phase 1: Foundation - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Config layer (TOML), state persistence (JSON), and httpx async API clients for Radarr and Sonarr. Establishes security invariants: no API key ever appears in HTTP responses, URLs, or log output. This is infrastructure — no search logic, no UI, no Docker packaging.

</domain>

<decisions>
## Implementation Decisions

### Config file experience
- Config lives at `/config/fetcharr.toml` — single fixed path, Docker-friendly
- Flat TOML structure: `[general]` for global settings, `[radarr]` and `[sonarr]` sections for per-app connection config (url, api_key, enabled)
- When config file is missing on startup, generate a commented default config file and exit with a message telling the user to edit it
- Search-related settings (batch sizes, intervals) are not in Phase 1 config — added in Phase 2 when the search engine is built

### Startup behavior
- If Radarr or Sonarr is unreachable on startup, log a warning and keep running — don't exit
- Run with whatever apps are configured — if user only has Radarr, Sonarr section can be empty/omitted
- Print a startup summary banner showing app name, version, connected apps, and key settings (helpful for Docker log debugging)
- At least one app must be configured — exit with error if both are missing/empty

### Logging style
- Human-readable log lines: `2026-02-23 14:30:00 INFO  Connected to Radarr at http://radarr:7878`
- Use loguru for logging (nice defaults, color output, easy configuration)
- Default log level: INFO — shows connections, cycle starts/completions, warnings
- Debug level available via `log_level = "debug"` in config for verbose request/response logging
- API keys are NEVER logged — not even partially masked. Complete absence from all log output.

### Error handling philosophy
- API call failures (timeout, 500): retry once with short delay, then log and skip — continue processing the rest of the batch
- HTTP timeout: 30 seconds for all *arr API calls (generous for slow NAS hardware)
- Runtime disconnects (app was working, now down): warn and continue each cycle, reconnect automatically when app comes back
- State file uses atomic write (write-then-rename) to prevent corruption on crash

### Claude's Discretion
- Startup API key validation approach (full test call vs URL-only check)
- Pydantic model structure and validation details
- httpx client configuration (connection pooling, retry backoff timing)
- State file location within /config volume
- Exact startup banner format

</decisions>

<specifics>
## Specific Ideas

- Config layout should match the flat preview shown: `[general]` with log_level, `[radarr]` with url/api_key/enabled, `[sonarr]` with url/api_key/enabled
- Log format matches `YYYY-MM-DD HH:MM:SS LEVEL  Message` — similar to how *arr apps log
- "Warn and keep running" philosophy across the board — Fetcharr should be resilient to transient *arr downtime, not fragile

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-23*
