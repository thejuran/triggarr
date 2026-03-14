# Phase 44: Deep Review Fixes - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning
**Source:** Deep code review findings (Phases 42-43)

<domain>
## Phase Boundary

Fix 8 issues identified by deep code review: 4 warnings (80-94 severity) and 4 medium (70-79 severity). All are targeted code fixes — no new features, no UI changes beyond what's needed for correctness.

</domain>

<decisions>
## Implementation Decisions

### Warning Fixes (80-94)

**1. Remove `_update_info.clear()` empty-dict window (88)**
- File: `scheduler.py:225`
- Fix: Remove `.clear()` call — `.update(result)` alone overwrites all 3 keys in-place with no empty window
- The result dict always has the same keys (`latest_version`, `update_available`, `html_url`)

**2. Clear tag warnings on connectivity failure (90)**
- File: `engine.py` — both Radarr (line ~307) and Sonarr (line ~511) early-return blocks
- Fix: Add `ist["tag_warnings"] = []` in the `except` block before `return state`
- Prevents stale warning badges when instance is unreachable

**3. XSS: Escape tag autocomplete HTML response (85)**
- File: `routes.py:576` (pre-existing, but newly visible via tag warning path)
- Fix: Add `html.escape()` to tag label in `<option>` element construction
- Import `html` module at top of file

**4. Validate GitHub `html_url` prefix before rendering (82)**
- File: `update_check.py:62`
- Fix: Check `html_url.startswith("https://github.com/")`, return `None` if not
- Prevents potential `javascript:` URL injection from spoofed GitHub response

### Medium Fixes (70-79)

**5. Validate instance filter param (78)**
- File: `routes.py:793`
- Fix: Guard against empty `inst_name` (trailing slash) and unknown `app_type` values
- Only set `instance_id`/`instance_app_type` when both parts are valid

**6. Handle pre-release version tags in `_parse_version` (82)**
- File: `update_check.py:34`
- Fix: Use `re.match(r"^(\d+)", part)` to extract leading integer from each segment
- Handles `v2.3.0-rc.1`, `0.1.0.dev1`, etc. without returning `(0,)`

**7. Remove redundant `httpx.TimeoutException` from except clause (72)**
- File: `update_check.py:67`
- Fix: Remove `httpx.TimeoutException` — it's a subclass of `httpx.HTTPError`

**8. Add CSRF protection to `dismiss_migration` endpoint (70)**
- File: `routes.py:833`
- Fix: Check `HX-Request` header, return 403 if missing
- Add `request: Request` parameter to function signature

### Claude's Discretion
- Test updates for changed behavior (tag warning clearing, version parsing)
- Whether to add tests for the XSS fix and CSRF protection

</decisions>

<specifics>
## Specific Ideas

All fixes have exact diff-style patches from the deep review. Follow them precisely.

</specifics>

<deferred>
## Deferred Ideas

- Move `_update_info` to `app.state.update_info` (architecture improvement, not a bug fix)
- Add `TagWarning` TypedDict for stricter typing on `tag_warnings: list[dict]`
- Add end-to-end test for update badge rendering
- These are noted but out of scope for this bug-fix phase

</deferred>

---

*Phase: 44-deep-review-fixes*
*Context gathered: 2026-03-13 via deep code review*
