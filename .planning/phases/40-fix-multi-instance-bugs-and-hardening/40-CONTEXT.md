# Phase 40: Fix Multi-Instance Bugs and Hardening - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning
**Source:** Deep code review findings

<domain>
## Phase Boundary

Fix all critical and warning-level bugs found during deep code review of multi-instance support (v2.3). Focus on the validate-schedule-cycle chain (startup.py -> scheduler.py -> engine.py) which has the most bugs, plus config safety, CSS injection, and temp file cleanup.

</domain>

<decisions>
## Implementation Decisions

### Critical: validate_connections loop overwrite (startup.py:110-118)
- validate_connections overwrites results — only last instance reported
- Loop writes to results["radarr"] on every iteration; with multiple enabled instances, only the last one's connection result survives
- Fix: Either validate first-only or key by instance name
- Confidence: 90

### Warning: KeyError crash if instance missing from state (engine.py:299,536)
- run_radarr_cycle / run_sonarr_cycle access state["radarr"][instance_name] without a guard
- Lifespan pre-populates state at startup, but runtime-added instances (via save_settings) don't get state entries
- Fix: Guard with setdefault before access
- Confidence: 88

### Warning: save_settings creates scheduler job but no state entry (routes.py:390-440)
- When a new instance is added at runtime, the route creates a client and scheduler job but never adds a per-instance state dict
- First cycle execution crashes with KeyError (linked to issue above)
- Fix: Add state entry when creating runtime instance
- Confidence: 85

### Warning: CSS selector injection via card_id (routes.py:131, app_card.html:1,72)
- card_id is built from instance name with only space->hyphen replacement
- Names with ., #, > break htmx hx-target CSS selectors, causing silent DOM targeting failures
- Fix: Sanitize with regex [^a-zA-Z0-9_-] -> "-"
- Confidence: 82

### Warning: settings_page save silently deletes non-first instances (routes.py:188-194, 314-344)
- Settings UI only handles the first instance per app type
- Saving rewrites config with first_inst_name only — any other configured instances are silently dropped
- Fix: Preserve all instances on settings save (or at minimum, don't delete them)
- Confidence: 82

### Warning: _atomic_toml_write leaks temp file on write failure (config.py:96-109)
- If tomli_w.dump raises, tmp_path is never cleaned up; the finally block only handles dir_fd
- Fix: Wrap in try/except, unlink tmp_path on failure
- Confidence: 78

### Warning: Unbounded instance_filter list in SQL query (db.py:363-366, routes.py:264)
- instance_filter from query params generates unbounded IN (?, ?, ...) placeholders
- App allows max 10 instances total
- Fix: Cap instance_filter length to 10
- Confidence: 78

### Medium: Tag fetch failure indistinguishable from empty tag list (engine.py:335-362)
- When get_tags() fails, tags = []. The "tag not found" warning only fires if tags (non-empty list)
- A network failure silently bypasses tag filtering with no log indication
- Fix: Log warning on tag fetch failure
- Confidence: 75

### Medium: cleanup_orphaned_instances mutates state in-place (state.py:203-222)
- Other state functions return new dicts; this one mutates via del while also returning state
- Potential issue if state is accessed from another coroutine during cleanup
- Fix: Return new dict consistent with other state functions
- Confidence: 72

### Medium: Test helper _default_instance_state shadows production symbol (tests/test_search.py:217)
- Same name as triggarr.state._default_instance_state but completely different return type
- Uses deferred import to work around the collision
- Fix: Rename test helper to avoid shadowing
- Confidence: 72

### Medium: No length limit on instance_name path parameter (routes.py:443,509)
- Arbitrarily long instance_name from URL path flows into log messages
- Log flooding vector
- Fix: Add length validation
- Confidence: 70

### Claude's Discretion
- Implementation order (suggest: fix crash bugs first, then hardening)
- Whether to batch related fixes or separate them
- Test approach for each fix

</decisions>

<specifics>
## Specific Ideas

- The validate-schedule-cycle chain (startup.py -> scheduler.py -> engine.py) has the most bugs (#1, #2, #3) — fix these as a group
- save_settings reimplements atomic TOML write without using _atomic_toml_write from config.py (missing dir fsync) — architectural duplication to address
- All 11 modified source files in v2.3 have corresponding tests; maintain that coverage

</specifics>

<deferred>
## Deferred Ideas

- Multi-instance settings UI (Phase 39 scope)
- Full per-instance dashboard UI (Phase 39 scope)

</deferred>

---

*Phase: 40-fix-multi-instance-bugs-and-hardening*
*Context gathered: 2026-03-11 via deep code review*
