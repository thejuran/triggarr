# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? |
|---|------|-------|----------|--------|-----------|------------|
| 1 | v1.0 | arch | Web framework | FastAPI + htmx/Jinja2 | User familiarity, no build step, server-rendered | no |
| 2 | v1.0 | arch | Sonarr search level | Season-level via SeasonSearch | Avoids hammering indexers with full-show searches | no |
| 3 | v1.0 | arch | Item selection strategy | Round-robin over random | Ensures every item gets searched eventually | no |
| 4 | v1.0 | security | Authentication | No auth — local network tool | No user accounts = no passwords = no credential attack surface | yes |
| 5 | v1.0 | arch | Scheduler | APScheduler 3.x over 4.x | 4.x still alpha, 3.x stable with AsyncIOScheduler | yes |
| 6 | v1.0 | security | CSRF protection | Origin/Referer header checking | No auth/sessions means no cookies to protect; token-based impossible | no |
| 7 | v1.0 | arch | htmx delivery | Vendored over CDN | Reproducible builds, no external dependency | no |
| 8 | v1.0 | arch | Log redaction | Custom loguru sink | Filter only sees message, sink sees full output including tracebacks | no |
| 9 | v1.0 | quality | Linting | Ruff E,F,I,UP,B,SIM | Comprehensive but non-noisy | no |
| 10 | v1.1 | arch | Hard max split | Proportional floor(missing/total*max) | Missing gets proportional share, cutoff gets remainder | no |
| 11 | v1.1 | arch | Config write safety | Atomic tempfile + fsync + os.replace | Prevents partial writes on crash | no |
| 12 | v2.0 | arch | Tracking approach | Post-search polling inside cycle functions | No separate scheduler job; tracks after each search inside search_lock | no |
| 13 | v2.0 | arch | Grab attribution | Probabilistic timestamp window matching | No commandId link available; window matching sufficient | no |
| 14 | v2.0 | security | SQL injection prevention | frozenset allowlist for stat column names | Prevents injection in dynamic SET clause | no |
| 15 | v2.0 | arch | Rate limiter pattern | Double-checked locking | Pre-check optimistic, re-check inside lock authoritative | no |
| 16 | v2.0 | arch | SQLite aggregation | SUM(CASE WHEN) over FILTER clause | FILTER not available in all SQLite versions | no |
| 17 | v2.1 | arch | Config dir | get_config_dir() function | Avoids module reload issues in tests vs env var at import time | no |
| 18 | v2.1 | security | Config path validation | Absolute paths only | Prevents relative/traversal path misconfiguration | no |
| 19 | v2.2 | arch | Release date filter | Null dates = pass through | PITFALLS.md: unknown != unreleased, don't blackhole items | no |
| 20 | v2.2 | arch | Release date fields | digitalRelease/physicalRelease only | inCinemas = cam quality; status field lags behind dates | no |
| 21 | v2.2 | arch | Filter pipeline position | After filter_monitored, before cursor/slice | Skip only monitored unreleased items | no |
| 22 | v2.3/S01 | arch | Config model rename | ArrConfig → InstanceConfig with backward-compat alias | Multi-instance naming clarity | no |
| 23 | v2.3/S01 | arch | Config migration detection | Flat key set intersection | v2.2 uses flat url/api_key/enabled under radarr/sonarr | no |
| 24 | v2.3/S01 | arch | Migration marker | .migrated empty file | Web UI only needs existence check for banner | no |
| 25 | v2.3/S01 | arch | TOML write helper | Extracted _atomic_toml_write | Reusable for migration and future routes.py | no |
| 26 | v2.3/S02 | arch | State shape | dict[str, AppState] per app type | Per-instance cursors keyed by instance name | no |
| 27 | v2.3/S02 | arch | Dashboard wiring (interim) | First enabled instance | Phase 39 for full multi-instance UI | yes |
| 28 | v2.3/S03 | arch | Tag model | extra=ignore on Tag BaseModel | Matches GrabEvent/SystemStatus pattern | no |
| 29 | v2.3/S03 | arch | Tag resolution | Pure function resolve_tag_id | Follows filter_monitored pattern | no |
| 30 | v2.3/S04 | arch | Tag accessor pattern | Callable[[dict], list[int]] | Radarr tags on movie, Sonarr tags on series object | no |
| 31 | v2.3/S04 | arch | Tag resolution timing | Once per cycle, not per queue | Minimizes API calls | no |
| 32 | v2.3/S04 | arch | Sonarr tag filter placement | Before deduplicate_to_seasons | Deduped dicts lose series.tags | no |
| 33 | v2.3/S04 | arch | Radarr filter order | filter_monitored → filter_by_tag → filter_unreleased | Tag narrows scope before release date check | no |
| 34 | v2.3/S05 | arch | instance_id default | 'Default' string everywhere | Backward compat with single-instance data, no NULL handling needed | no |
| 35 | v2.3/S05 | arch | lifetime_stats composite PK | (app, instance_id) via table-swap migration | Per-instance stats without separate table; table-swap preserves data | no |
| 36 | v2.3/S05 | arch | Stats row auto-creation | INSERT OR IGNORE before UPDATE | No need to pre-seed stats rows for new instances | no |
