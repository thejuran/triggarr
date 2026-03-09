# Phase 16: Deep Code Review

**Date:** 2026-02-24
**Scope:** 42 files, +4,322/-52 lines across 33 unpushed commits (v1.2 phases 13-15)
**Agents:** Bugs & Logic, Security (OWASP), Architecture, Python Issues, CLAUDE.md Compliance

| Found | Reported (>=70) | Filtered (<70) |
|-------|-----------------|----------------|
| 32    | 18              | 14             |

## Resolution Summary

| Level | Total | Fixed | Won't Fix | Deferred |
|-------|-------|-------|-----------|----------|
| Warning (80-94) | 8 | 7 | 1 | 0 |
| Medium (70-79) | 8 | 0 | 0 | 8 |
| Filtered (<70) | 14 | 0 | 0 | 14 |

---

## Warning (80-94)

### W1. Reflected XSS via single-quoted `hx-vals` attribute

**File:** `fetcharr/templates/partials/history_results.html:89`
**Confidence:** 88 | CWE-79
**Resolution:** Fixed -- hx-vals switched to double-quoted tojson filter pattern

Jinja2 autoescaping does not escape single quotes. The `hx-vals` attribute uses single-quote delimiters, so a crafted `?search=foo' onmouseover='alert(1)` breaks out of the attribute context.

```diff
- hx-vals='{"app": "{{ active_apps | join(',') }}", ...}'
+ hx-vals="{{ {'app': active_apps | join(','), 'queue': active_queues | join(','), 'outcome': active_outcomes | join(','), 'page': '1'} | tojson }}"
```

### W2. Non-atomic config write violates CLAUDE.md

**File:** `fetcharr/web/routes.py:235`
**Confidence:** 90 | CLAUDE.md violation
**Resolution:** Fixed -- atomic write-then-rename via tempfile + fsync + os.replace

`save_settings` uses `config_path.write_text()` -- a crash mid-write corrupts the config. CLAUDE.md requires atomic write-then-rename (the pattern used in `state.py`).

```diff
- config_path.write_text(tomli_w.dumps(new_config))
+ content = tomli_w.dumps(new_config)
+ with tempfile.NamedTemporaryFile(mode="w", dir=config_path.parent, suffix=".tmp", delete=False) as tmp:
+     tmp.write(content)
+     tmp.flush()
+     os.fsync(tmp.fileno())
+ os.replace(tmp.name, config_path)
+ os.chmod(config_path, 0o600)
```

### W3. Unvalidated `page` parameter causes 500 on bad input

**File:** `fetcharr/web/routes.py:162`
**Confidence:** 85
**Resolution:** Fixed -- bare int() replaced with safe_int()

Bare `int()` on the query param raises `ValueError` on non-numeric input. The existing `safe_int` helper was built for exactly this.

```diff
- page = int(params.get("page", "1"))
+ page = safe_int(params.get("page"), default=1, minimum=1, maximum=10_000)
```

### W4. Unclosed aiosqlite cursors (resource leak)

**File:** `fetcharr/db.py:118, 189, 198`
**Confidence:** 88
**Resolution:** Fixed -- all cursors wrapped in async with for deterministic cleanup

Cursors from `db.execute()` are never explicitly closed. Use `async with` to ensure deterministic cleanup.

```diff
- cursor = await db.execute("SELECT ... LIMIT ?", (limit,))
- rows = await cursor.fetchall()
+ async with db.execute("SELECT ... LIMIT ?", (limit,)) as cursor:
+     rows = await cursor.fetchall()
```

### W5. `ZeroDivisionError` if `per_page=0`

**File:** `fetcharr/db.py:223`
**Confidence:** 82
**Resolution:** Fixed -- per_page/page guards added at function top

Not currently exploitable from the web layer (default=50), but the function's public API accepts any int.

```diff
  async def get_search_history(..., per_page: int = 50, ...) -> dict:
+     if per_page < 1:
+         per_page = 50
+     if page < 1:
+         page = 1
```

### W6. Redundant `Exception` in except tuple (CLAUDE.md violation)

**File:** `fetcharr/clients/sonarr.py:45`
**Confidence:** 85
**Resolution:** Won't Fix -- broad except Exception is intentional safety net in Sonarr client (per user decision)

`except (httpx.HTTPError, pydantic.ValidationError, KeyError, Exception)` -- the specific types are dead code since `Exception` catches everything. Violates CLAUDE.md's established error-handling pattern.

```diff
- except (httpx.HTTPError, pydantic.ValidationError, KeyError, Exception) as exc:
+ except (httpx.HTTPError, pydantic.ValidationError, KeyError) as exc:
```

### W7. SSRF blocklist missing IPv6 loopback and cloud metadata addresses

**File:** `fetcharr/web/validation.py:13`
**Confidence:** 80 | CWE-918
**Resolution:** Fixed -- added Azure/Alibaba metadata hosts, is_loopback check for IPv6/IPv4 loopback and 0.0.0.0

Only blocks `169.254.169.254` and `metadata.google.internal`. Missing `::1`, `0.0.0.0`, `100.100.100.200`, `metadata.azure.com`.

```diff
  BLOCKED_HOSTS: set[str] = {"169.254.169.254", "metadata.google.internal"}
+ BLOCKED_HOSTS |= {"metadata.azure.com", "100.100.100.200"}

  try:
      addr = ipaddress.ip_address(hostname)
-     if addr.is_link_local:
+     if addr.is_link_local or addr.is_loopback:
          return (False, "Link-local address blocked")
```

### W8. `save_settings` catches bare `except Exception` for validation

**File:** `fetcharr/web/routes.py:228-232`
**Confidence:** 80
**Resolution:** Fixed -- narrowed to pydantic.ValidationError with error detail logging

Only `pydantic.ValidationError` is expected here. The broad catch hides other bugs.

```diff
- except Exception:
+ except pydantic.ValidationError as exc:
-     logger.warning("Invalid settings rejected -- config file unchanged")
+     logger.warning("Invalid settings rejected: {exc}", exc=exc)
```

---

## Medium (70-79)

### M1. Stored XSS defense-in-depth: `entry.detail` in title attribute

**File:** `fetcharr/templates/partials/search_log.html:19`, `fetcharr/templates/partials/history_results.html:110`
**Confidence:** 72 | CWE-79
**Resolution:** Deferred -- backlog for next milestone

Relies on Jinja2 autoescaping being enabled. Explicit `| e` filter makes the protection visible.

```diff
- title="{{ entry.detail }}"
+ title="{{ entry.detail | e }}"
```

### M2. SQL f-string in DDL migration

**File:** `fetcharr/db.py:62-64`
**Confidence:** 75 | CWE-89
**Resolution:** Deferred -- backlog for next milestone

Column names interpolated via f-string. Values are hardcoded so no active risk, but the pattern is visually indistinguishable from unsafe SQL.

### M3. `contextlib.suppress(Exception)` too broad in migration

**File:** `fetcharr/db.py:61-64`
**Confidence:** 78
**Resolution:** Deferred -- backlog for next milestone

Only `OperationalError` (duplicate column) should be suppressed.

```diff
- with contextlib.suppress(Exception):
+ with contextlib.suppress(aiosqlite.OperationalError):
```

### M4. Shared mutable `params` list between COUNT and data queries

**File:** `fetcharr/db.py:189-202`
**Confidence:** 75
**Resolution:** Deferred -- backlog for next milestone

Not a bug today, but a latent mutation hazard if the function is extended.

```diff
+ params_tuple = tuple(params)
  # use params_tuple in both queries
```

### M5. `print()` used instead of Loguru (CLAUDE.md violation)

**File:** `fetcharr/config.py:84-88`
**Confidence:** 78
**Resolution:** Deferred -- backlog for next milestone

Pre-bootstrap message uses `print(file=sys.stderr)`. CLAUDE.md says "never print."

```diff
- print(f"Default config written to {config_path}\n"..., file=sys.stderr)
+ sys.stderr.write(f"Default config written to {config_path}\n"
+     "Edit the config file and restart Fetcharr.\n")
```

### M6. `callable` (lowercase) used as return type annotation (CLAUDE.md violation)

**File:** `fetcharr/search/scheduler.py:75`
**Confidence:** 78
**Resolution:** Deferred -- backlog for next milestone

Triggers ruff UP006. The `# type: ignore` comment acknowledges but doesn't fix.

```diff
- ) -> callable:  # type: ignore[type-arg]
+ ) -> Callable[..., Any]:
```

### M7. `validate_connection` and `detect_api_version` bypass `_request_with_retry`

**File:** `fetcharr/clients/base.py:145`, `fetcharr/clients/sonarr.py:38`
**Confidence:** 75
**Resolution:** Deferred -- backlog for next milestone

Every other method goes through the retry wrapper. These two call `self._client.get` directly -- inconsistent and specifically lacking retry during startup.

### M8. `BaseSettings` / `settings_customise_sources` is dead code

**File:** `fetcharr/models/config.py` + `fetcharr/config.py`
**Confidence:** 72
**Resolution:** Deferred -- backlog for next milestone

`load_settings` manually reads TOML and passes it to `Settings(**data)`, bypassing pydantic-settings source loading entirely.

---

## Filtered Issues (<70)

14 issues filtered by category:

- **Type hint improvements:** 5 (sink params, db return types, middleware dispatch, make_search_job, PaginatedResponse config)
- **Test pattern suggestions:** 3 (conftest non-fixture, async/sync client fixture mix, _default_state import inconsistency)
- **Architectural suggestions:** 4 (path constant consolidation, UTC timestamp utility, state mutate+return, validation error not surfaced to user)
- **Container hardening:** 2 (unquoted $NO_NEW_PRIVS, unpinned deps)

---

## Architectural Notes

| Area | Status | Notes |
|------|--------|-------|
| Pattern consistency | Warning | Retry bypass in clients, broad exception catches, non-atomic write in routes |
| Test coverage | Pass | 2,718 LOC tests / 1,566 LOC source (174% ratio). All modules covered. |
| Documentation | Pass | CLAUDE.md thorough, README covers installation and config |
| Dependencies | Warning | All runtime deps unpinned except APScheduler. No base image digest pin. |
| Separation of concerns | Warning | `routes.py` has 9 internal imports, 115-line config-reload handler. Duplicate ~130-line cycle functions. |
| State management | Pass | Clean split: JSON (cursors/timing) vs SQLite (history). Migration handled. |
| Async patterns | Pass | Correct throughout. asyncio.Lock for search serialization, aiosqlite connection-per-op. |

## Impact Analysis

- **Affected files:** 20 source + 13 test files
- **Blast radius:** Low -- changes are additive (new features). No existing behavior modified.
- **Breaking changes:** None
- **Priority fixes:** W1 (XSS in hx-vals) and W2 (non-atomic config write) -- both one-file fixes with high safety payoff
