# Pitfalls Research

**Domain:** Adding multi-instance support and tag-based filtering to existing search automation daemon
**Researched:** 2026-03-09
**Confidence:** HIGH (based on direct codebase analysis of all core modules + Radarr/Sonarr API research + multi-instance community patterns)

---

## Critical Pitfalls

### Pitfall 1: Single search_lock Serializes All Instances

**What goes wrong:**
The current system uses one `asyncio.Lock()` (`app.state.search_lock`) that serializes ALL search cycles. With N instances, each cycle waits for all others to finish. If Radarr-4K has 500 items and Radarr-HD has 200, the HD instance waits for 4K to complete before it can run. This effectively turns "parallel instances" into a slow sequential queue, defeating the purpose of separate instances.

**Why it happens:**
The single lock was correct for single-instance (prevents concurrent API calls to the same server). Developers carry it forward assuming "one lock = safe" without recognizing that different instances target different servers and can safely run concurrently.

**How to avoid:**
Use per-instance locks. Each instance gets its own `asyncio.Lock()` keyed by instance ID. Store in a dict: `{instance_id: asyncio.Lock()}`. This allows Radarr-4K and Sonarr-anime to search simultaneously (different servers) while preventing concurrent cycles on the SAME instance. The search-now endpoint and graceful shutdown must also use per-instance locks instead of the global lock.

**Warning signs:**
- Search cycles taking much longer after adding instances
- "next_run" times drifting behind schedule
- Log messages showing one instance idle while another runs

**Phase to address:**
Phase 1 (core multi-instance infrastructure) -- foundational to scheduler design.

---

### Pitfall 2: Config Migration Destroys Existing Single-Instance Setups

**What goes wrong:**
The TOML config changes from `[radarr]` (single table) to `[[instances]]` (array of tables) or similar. `tomllib` parses `[radarr]` as `dict` and `[[instances]]` as `list[dict]`. These are incompatible types -- Pydantic validation fails. Existing users upgrade the Docker image, the container starts, hits a parse error, and their working setup breaks with no clear error.

**Why it happens:**
TOML format changes are breaking changes at the parser level. The config file on disk was written by the old code. The new code expects a different structure. There is no automatic bridging.

**How to avoid:**
1. Detect old format on startup: if `config.get("radarr")` is a `dict` (not absent or a list), the user has an old single-instance config.
2. Auto-migrate: wrap the old `[radarr]` section into an instance with a default name (e.g., `"radarr"`), preserving all values.
3. Write the migrated config back to disk atomically (existing `tempfile + fsync + os.replace` pattern).
4. Back up the original: copy `triggarr.toml` to `triggarr.toml.pre-v2.3-backup` before rewriting.
5. Log a clear INFO message: `"Migrated single-instance config to multi-instance format"`.
6. Critical: the migration must preserve the API key value (currently a `SecretStr`). Read the raw TOML value (string), not the Pydantic-parsed `SecretStr`.

**Warning signs:**
- Startup crashes with "validation error" on radarr/sonarr fields
- Users reporting "my config stopped working after update"
- Silent loss of configured instances (no searches running, no error)

**Phase to address:**
Phase 1 (config model) -- must be the FIRST thing implemented, before any other work.

---

### Pitfall 3: State File Cursor Collision Between Instances

**What goes wrong:**
The current `state.json` stores cursors at `state["radarr"]["missing_cursor"]`. With two Radarr instances, both write to the same key. Instance A advances cursor to 50, instance B overwrites it to 12, instance A reads 12 next cycle and re-searches items 12-50.

**Why it happens:**
The state structure uses app type ("radarr", "sonarr") as the key, not instance identity. The `_default_state()` function hardcodes exactly two entries. The `_merge_defaults()` function only looks for "radarr" and "sonarr" keys.

**How to avoid:**
Key state by instance ID. Change from `state["radarr"]` to `state["instances"]["my-radarr-4k"]` (or similar). Migration on first load: detect old `state["radarr"]` keys, move their values to the default instance's new key. The `AppState` TypedDict itself can remain unchanged (it describes per-instance state). Only the top-level `TriggarrState` changes.

**Warning signs:**
- Cursor positions jumping backwards in logs
- Items being re-searched that were just searched
- Pass counters resetting or not incrementing

**Phase to address:**
Phase 1 (state model) -- must change alongside config migration.

---

### Pitfall 4: Database search_history Loses Instance Attribution

**What goes wrong:**
The `search_history` table stores `app` as "Radarr" or "Sonarr" -- a type, not an instance identifier. With two Radarr instances, all searches log as "Radarr" with no way to tell which instance triggered them. This breaks:
- **Dashboard stats**: combined grab rates for different instances (meaningless aggregate)
- **History filtering**: cannot filter to one instance's activity
- **Tracking correlation**: `run_tracking_check` groups by `(app, item_id)` and picks a client by app name. With two Radarr clients, it picks the wrong one 50% of the time. Grab detection fails for searches on the instance whose client was NOT picked.

**Why it happens:**
The `app` column was designed for exactly two values. It is used in `GROUP BY app` queries, template rendering, the `_get_client()` function in tracking.py, and the `lifetime_stats` table (keyed on `app TEXT PRIMARY KEY`).

**How to avoid:**
1. Add `instance_id TEXT` column to `search_history` (schema migration v6).
2. Keep the `app` column for backward compat (still useful for "Radarr or Sonarr?" type checks).
3. Backfill existing rows: `UPDATE search_history SET instance_id = 'radarr' WHERE app = 'Radarr' AND instance_id IS NULL`.
4. Change `lifetime_stats` primary key from `app` to `instance_id` (or add `instance_id` column and a new composite key). This requires creating a new table and migrating data since SQLite cannot alter primary keys.
5. Update all `GROUP BY app` queries to `GROUP BY instance_id` where per-instance breakdown is needed.

**Warning signs:**
- Dashboard stats showing blended numbers for different Radarr instances
- Tracking marking wrong items as "grabbed" (cross-instance correlation)
- History page showing mixed results with no instance filter

**Phase to address:**
Phase 2 (database schema + tracking) -- after config/state model is stable.

---

### Pitfall 5: Tag Filtering Requires Client-Side Implementation (No Server-Side Support)

**What goes wrong:**
Developers assume they can pass a `tags` query parameter to `/api/v3/wanted/missing` to get only tagged items server-side. The Radarr and Sonarr wanted/missing and wanted/cutoff endpoints do NOT support tag filtering. You must fetch ALL wanted items and filter client-side. This is a known API limitation confirmed by the syncarr project's implementation struggles (GitHub syncarr/syncarr#77) and Radarr issue #7704.

**Why it happens:**
The *arr APIs include `tags` on the movie/series object as an integer array (tag IDs), but the wanted endpoints do not accept tag filter parameters. The assumption that a field exists on the response implies it is also filterable on the request is natural but wrong.

**How to avoid:**
1. Fetch wanted items as currently done (full paginated fetch).
2. After fetching, filter: `[item for item in items if configured_tag_id in item.get("tags", [])]`.
3. When no tag is configured, skip filtering entirely (current behavior preserved).
4. Resolve tag names to IDs via `GET /api/v3/tag` (returns `[{"id": 1, "label": "triggarr-missing"}, ...]`).
5. For Sonarr: tags are on the SERIES object, not episodes. Since `includeSeries=true` is already passed, use `episode.get("series", {}).get("tags", [])` to check tags.

**Warning signs:**
- Attempting to add `tags` param to the paginated fetch and getting it silently ignored
- Tag filtering appearing to work but matching zero items (wrong tag ID resolution)

**Phase to address:**
Phase 3 (tag filtering) -- after multi-instance infrastructure is solid.

---

### Pitfall 6: Tag ID vs Tag Name Mismatch Silently Filters Everything Out

**What goes wrong:**
Users configure tag filtering by label ("triggarr-missing") in TOML. The app resolves this to an integer ID (e.g., 5) via `/api/v3/tag`. If the user deletes and recreates the tag in Radarr, the ID changes from 5 to 8. If the app caches the old ID, it filters against a nonexistent tag, matching zero items. The instance silently searches nothing.

**Why it happens:**
Tag IDs in *arr are auto-incrementing database IDs, not stable identifiers. Labels are stable but filtering requires IDs. The syncarr project hit exactly this problem -- tag ID comparisons broke when tags were recreated (syncarr#77).

**How to avoid:**
1. Resolve tag name to ID at the START of every search cycle, not just at startup. The API call to `GET /api/v3/tag` is lightweight (~10ms).
2. If the tag name does not resolve (no match), log a WARNING and fall back to "search all items" for that cycle. Do NOT silently search nothing.
3. Store tag NAME in config, never tag ID. The ID is ephemeral runtime state.
4. Show a warning badge on the dashboard: "Tag 'triggarr-missing' not found in Radarr-4K".
5. Optional optimization: cache the tag mapping with a 5-minute TTL to avoid calling `/api/v3/tag` on every cycle.

**Warning signs:**
- Zero items searched after user reorganized tags in *arr
- "Tag 'triggarr-missing' not found" warnings accumulating in logs
- Instance suddenly searching all items when it should be filtered (fallback kicking in)

**Phase to address:**
Phase 3 (tag filtering) -- part of the tag resolution design.

---

### Pitfall 7: Tracking Cross-Contamination Between Instances

**What goes wrong:**
The tracking system (`tracking.py`) polls `/api/v3/history/movie` or `/api/v3/history/series` to detect grabs. With two Radarr instances on different servers, tracking must query the CORRECT instance's API. Currently `_get_client()` does a simple name match: `if app == "Radarr": return radarr_client`. With multiple Radarr instances, this picks one client arbitrarily. Searches on instance B get checked against instance A's history, finding no grabs.

**Why it happens:**
`run_tracking_check` receives `radarr_client` and `sonarr_client` as single objects. The `_get_client()` function dispatches by app name, not instance identity. The `get_trackable_entries()` query does not return instance information.

**How to avoid:**
1. Store `instance_id` on each `search_history` row (see Pitfall 4).
2. Pass a client dict to tracking: `{instance_id: client}` instead of two positional args.
3. For each pending entry, look up client by `instance_id`.
4. If a client is unavailable (instance removed from config), immediately mark pending entries as "unresolved" instead of leaving them pending forever.

**Warning signs:**
- All searches showing "unresolved" despite items being grabbed
- Pending entries accumulating for removed instances
- Grab rates dropping to near zero after adding a second instance of the same type

**Phase to address:**
Phase 2-3 -- after instance_id is in the database schema.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoded "Radarr"/"Sonarr" strings in engine, tracking, templates | Quick string comparisons | Every multi-instance feature needs conditional logic; breaks if third app type added | Never -- replace with instance_id early |
| Single shared DB connection for all instances | Simple connection management | Write contention with many instances (SQLite serializes writes) | Acceptable for up to ~6 instances (WAL mode handles concurrent reads; cycles are mostly reads with brief writes) |
| Resolving tag IDs only at startup | Faster cycles | Stale IDs after tag changes | Never -- resolve per-cycle or with short TTL cache |
| Keeping `app` column without `instance_id` | Less migration work | Ambiguous queries, cross-instance tracking bugs | Only during Phase 1 transition -- must add instance_id in Phase 2 |
| Storing instance config inline in one TOML file | Simple single file | Long files with many instances, harder to read | Acceptable -- TOML array of tables is readable up to ~8 instances |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Radarr/Sonarr tag API (`GET /api/v3/tag`) | Assuming tag labels are globally unique | Labels ARE unique within one *arr instance, but different instances have different IDs for the same label name. Resolve per-instance. |
| Radarr/Sonarr tag API | Assuming the tag exists | `/api/v3/tag` may return a list without the expected label. Handle with fallback to "search all" + dashboard warning. |
| Movie/series `tags` field | Assuming `tags` key always present | Some API responses omit `tags` when empty. Always use `.get("tags", [])`. |
| Sonarr episode tags | Filtering episodes directly by tags | Tags are on the SERIES object, not individual episodes. Use `episode.get("series", {}).get("tags", [])` since `includeSeries=true` is already set. |
| APScheduler job IDs | Using `f"{app_name}_search"` pattern | With multiple instances, job IDs must be unique per instance: `f"{instance_id}_search"`. Duplicate IDs cause APScheduler to silently replace the first job. |
| `make_search_job()` closure | Captures app_name to select cycle function | Must capture instance_id AND app type. The cycle function selection (radarr vs sonarr) depends on app type, but client lookup depends on instance_id. |
| Settings save route | Manually constructing config dict from form fields | With N instances, the form structure changes fundamentally. Must iterate over instance fields dynamically, not hardcode "radarr" and "sonarr" names. |
| Health endpoint | Checking `state["radarr"]["connected"]` | Must iterate all instances, check each. Report per-instance health. |
| Same movie on two instances | Searching movie ID 42 on both Radarr-HD and Radarr-4K | Movie IDs are local to each *arr database. Movie ID 42 on Radarr-HD is a DIFFERENT movie than ID 42 on Radarr-4K. The tracking correlation must scope item_id to instance_id. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N instances fetching full wanted lists for tag filtering | Slow total cycle time; high memory | Accept this is unavoidable (no server-side tag filter). Log fetch times. Stagger instance schedules. | >5,000 wanted items per instance |
| N instances x M API calls = N*M outbound requests per interval | API rate limiting in *arr; slow cycles | Per-instance locks allow parallelism. Stagger start times (offset initial run by instance index * 30s). | >4 instances with <15min intervals |
| Dashboard aggregating stats across all instances | Slow page loads from many DB queries | Single query with `GROUP BY instance_id`, not N separate queries. | >3 instances |
| Tag resolution API call per instance per cycle | Extra 100-200ms per instance per cycle | Cache with 5-min TTL. Only re-resolve on miss or expiry. | Noticeable at >6 instances |
| `get_trackable_entries()` returning all pending from all instances | Large result set when many instances have pending entries | Consider adding instance_id filter to the query when processing per-instance. | >100 pending entries across instances |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| New instance API keys not added to log redaction | Keys from added instances appear in loguru output | After config save/load with new instances, re-collect ALL secrets from ALL instances and update the redacting sink. The existing `collect_secrets()` + `setup_logging()` pattern must iterate all instances. |
| Instance names interpolated unsafely in log messages or templates | XSS if instance name contains HTML; log injection if it contains format strings | Validate instance names: alphanumeric + hyphens only, max 32 chars. Apply same urlencode discipline in templates as existing XSS prevention. |
| Settings form not masking all API keys | Multiple API key fields on page; easy to miss masking one | Loop over all instances when building settings context, applying same `has_api_key` mask pattern per instance. |
| Instance URL not validated | SSRF if user enters internal network addresses | Apply existing `validate_arr_url()` to every instance URL, not just "radarr" and "sonarr". |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Dashboard shows all instances in a flat list | Cluttered with 4+ instances | Group cards by app type (Radarr section, Sonarr section). Instance name as card title. |
| Tag configured but tag does not exist in *arr | Silent failure -- instance searches nothing, user thinks tool is broken | Warning badge on dashboard card: "Tag 'triggarr-missing' not found in Radarr-4K" |
| Config UI for N instances is a long scrolling form | Tedious for 4+ instances | Tabbed or accordion UI per instance. Add/remove instance buttons. |
| No visual distinction between instances | Users confuse which Radarr instance is which | Require unique instance names. Show name prominently in cards, history, and logs. |
| Search history mixes all instances | Cannot see one instance's activity | Instance filter pills on history page (same pattern as existing app/queue/outcome filters). |
| "Search Now" button ambiguity | Which instance does it trigger? | One button per instance card, labeled with instance name. |
| Stats aggregated across instances | Overall grab rate is meaningless when one instance has 90% and another has 10% | Per-instance stats on dashboard. Optional "all instances" aggregate. |

## "Looks Done But Isn't" Checklist

- [ ] **Config migration:** Old single-instance TOML auto-detected and migrated on first startup -- verify with a real v2.2 `triggarr.toml` file
- [ ] **State migration:** Old `state["radarr"]` cursors preserved and attributed to default instance -- verify cursor positions survive upgrade
- [ ] **DB migration:** `instance_id` column added to `search_history` AND `lifetime_stats` restructured -- verify existing rows backfilled with default instance IDs
- [ ] **Tracking:** Pending search entries from before upgrade are resolvable -- verify they get attributed to correct default instance client
- [ ] **Scheduler:** Each instance has unique job ID -- verify removing an instance also removes its APScheduler job
- [ ] **Per-instance locks:** Instances on different servers run concurrently -- verify with log timestamps showing overlapping cycles
- [ ] **Tag resolution:** Tag name resolves to correct ID per instance -- verify with two instances where same tag label has different IDs
- [ ] **Tag not found:** Graceful fallback to "search all" with dashboard warning -- verify by configuring a nonexistent tag name
- [ ] **Sonarr tag path:** Tags checked via `episode.series.tags`, not `episode.tags` -- verify with a tagged Sonarr series
- [ ] **Settings form:** All instance API keys masked, never sent to browser -- verify with browser dev tools
- [ ] **Log redaction:** All instance API keys redacted -- verify by triggering connection error on each instance
- [ ] **Health endpoint:** Reports per-instance health -- verify with one healthy and one unhealthy instance of same type
- [ ] **Search-now:** Works per-instance -- verify button triggers correct instance cycle
- [ ] **Graceful shutdown:** All instance clients closed, all locks drained -- verify no resource leaks

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Config migration failed / corrupt | LOW | Restore from `triggarr.toml.pre-v2.3-backup`, fix migration code, retry |
| State cursors corrupted by collision | LOW | Delete `state.json` -- all cursors reset to 0, instances restart from beginning of queues |
| DB missing instance_id on rows | MEDIUM | Run backfill migration: `UPDATE search_history SET instance_id = 'default-radarr' WHERE app = 'Radarr' AND instance_id IS NULL` (similarly for Sonarr) |
| Tracking cross-contamination | MEDIUM | Mark all pending entries as "unresolved" (`UPDATE search_history SET outcome = 'unresolved' WHERE outcome IN ('searched', 'partial')`), let next cycles create fresh entries with correct instance_id |
| Wrong tag ID cached | LOW | Restart app or wait for next cycle (if per-cycle resolution implemented) |
| APScheduler duplicate job IDs | LOW | Restart app with fixed job ID scheme |
| Tag silently matching zero items | LOW | Check logs for "Tag not found" warning; verify tag exists in *arr instance; restart app |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Single search_lock (P1) | Phase 1: Core infrastructure | Two instances run cycles concurrently (overlapping log timestamps) |
| Config migration breaks existing (P2) | Phase 1: Config model | Start new code with old v2.2 triggarr.toml; auto-migration succeeds; searches run |
| State cursor collision (P3) | Phase 1: State model | Two Radarr instances maintain independent cursors across multiple cycles |
| DB lacks instance attribution (P4) | Phase 2: Schema migration | Search history shows correct instance name per entry; tracking resolves against correct server |
| Tag filtering is client-side (P5) | Phase 3: Tag filtering | Tag-filtered instance searches fewer items than unfiltered |
| Tag ID vs name mismatch (P6) | Phase 3: Tag filtering | Delete + recreate tag in *arr; next cycle picks up new ID |
| Tracking cross-contamination (P7) | Phase 2-3: Tracking update | Search on instance A detected via instance A's history API, not instance B's |

---

## Sources

- **Codebase analysis (HIGH confidence):** Direct reading of `triggarr/config.py`, `triggarr/models/config.py` (Settings/ArrConfig), `triggarr/state.py` (TriggarrState/AppState TypedDict, `_default_state`, `_merge_defaults`), `triggarr/search/scheduler.py` (single `search_lock`, `make_search_job`, lifespan), `triggarr/search/engine.py` (cycle functions, filter pipeline), `triggarr/db.py` (schema, migrations, `app` column usage, lifetime_stats PK), `triggarr/tracking.py` (`_get_client` dispatch, `run_tracking_check` grouping), `triggarr/web/routes.py` (settings save, search-now, health, hardcoded "radarr"/"sonarr")
- [Syncarr tag filtering issues (syncarr#77)](https://github.com/syncarr/syncarr/issues/77) -- tag filtering only worked on Sonarr initially; tag ID mismatches caused silent zero-match filtering in Radarr (HIGH confidence)
- [Radarr#7704](https://github.com/Radarr/Radarr/issues/7704) -- wanted/missing endpoint lacks server-side filtering; client-side filtering required (HIGH confidence)
- [Servarr Wiki: Multiple Instances](https://wiki.servarr.com/radarr/installation/multiple-instances) -- port conflicts, config isolation (MEDIUM confidence)
- [Overseerr#3615](https://github.com/sct/overseerr/issues/3615) -- multi-instance integration complexity in *arr ecosystem tools (MEDIUM confidence)
- [Bazarr#404](https://github.com/morpheus65535/bazarr/issues/404) -- multi-instance support challenges (MEDIUM confidence)
- [Radarr#11146](https://github.com/Radarr/Radarr/issues/11146) -- browser localStorage conflicts with multiple instances (LOW confidence -- different domain but instructive)
- [TOML array of tables (Real Python)](https://realpython.com/python-toml/) -- `[[section]]` syntax, tomli_w behavior (HIGH confidence)

---
*Pitfalls research for: Triggarr v2.3 multi-instance and tag filtering*
*Researched: 2026-03-09*
