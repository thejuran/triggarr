---
status: complete
phase: 88-bounded-upgrade-backups-telemetry-regression
source: [88-01-SUMMARY.md, 88-02-SUMMARY.md]
started: 2026-11-17T04:00:15Z
updated: 2026-11-17T04:07:31Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Build the phase branch image (docker build -t triggarr:local .) and start it fresh against a copy of an existing Triggarr data folder. It boots without errors, the dashboard loads, and /health returns {"status": "ok"}. Existing settings and search history are intact.
result: pass
note: Run by Claude at owner request on e4ea7bb7. Data folder seeded by released v2.12.1 (fresh setup + marker search-history row); phase image started on it: /health ok, login + dashboard 200, marker row present on /history, triggarr.toml byte-identical. Only warnings: 'No apps configured' and Docker-on-Mac setpriv notice.

### 2. Telemetry environment variables do not crash startup
expected: Start the same image with FASTAPI_OTEL_AUTO_CONFIGURE=true and OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 set. Triggarr still starts, the dashboard loads, and /health returns ok. At most a warning about telemetry appears in the log; nothing is exported and there is no crash or restart loop.
result: pass
note: FASTAPI_OTEL_AUTO_CONFIGURE=true + OTEL_EXPORTER_OTLP_ENDPOINT set; healthy after 40s, RestartCount 0, login + dashboard 200. One log line: 'FastAPI automatic telemetry configuration failed: ... requires fastapi[opentelemetry]'.

### 3. Upgrade backups stay bounded through a crash loop
expected: When a database upgrade keeps failing across restarts, the data folder holds the one original pre-upgrade backup plus at most 3 timestamped retry backups for that version; older retry backups are removed and each removal is logged as one info line. Backups for other versions and unrelated files are untouched. If a cleanup step fails, it is logged as a warning and startup is not blocked.
result: pass
note: Real failing v9->v10 upgrade forced (leftover lifetime_stats_v10, schema_version=9) and container restarted 6 times (exit 3 each). Retry backups 0,1,2,3,3,3; attempts 5-6 each logged one 'Removed old retry backup ... keeping the original backup and the 3 most recent'. Canonical .v9-backup, a .v8 timestamped file, notes.txt and a backup-named directory untouched. Cleanup-failure-warning path not reproduced live (covered by automated tests). Pre-existing, out of scope: failed upgrade also prints a uvicorn lifespan traceback after the clear error line.

### 4. README documents OpenTelemetry is unsupported
expected: In README.md's Configuration Reference, right after the startup-level environment variables paragraph and before Screenshots, one sentence says Triggarr does not support OpenTelemetry export, and that setting FASTAPI_OTEL_AUTO_CONFIGURE or an OTLP endpoint does not stop Triggarr from starting but nothing is exported. No new heading.
result: pass
note: Sentence at README line 215, after the startup-level env vars paragraph, before '## Screenshots' (217); no new heading vs main. Text also describes the one-time FastAPI warning, matching test 2.

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
