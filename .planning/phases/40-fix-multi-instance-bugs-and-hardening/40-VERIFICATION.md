---
phase: 40-fix-multi-instance-bugs-and-hardening
verified: 2026-03-11T00:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: null
gaps: []
human_verification: []
---

# Phase 40: Fix Multi-Instance Bugs and Hardening Verification Report

**Phase Goal:** Fix all critical and warning-level bugs found during deep code review of multi-instance support, covering crash bugs in the validate-schedule-cycle chain, config safety issues, and input validation hardening
**Verified:** 2026-03-11
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Runtime-added instances do not crash with KeyError on first cycle | VERIFIED | `engine.py:299` `state["radarr"].setdefault(instance_name, _default_instance_state())` and `engine.py:501` same for sonarr |
| 2  | validate_connections reports all enabled instances, not just the last one | VERIFIED | `startup.py:116` `results[f"radarr/{inst_name}"]` and `startup.py:126` `results[f"sonarr/{inst_name}"]` -- keyed by instance name |
| 3  | save_settings creates a state entry for newly enabled instances | VERIFIED | `routes.py:470-477` -- iterates new_instances, calls `_default_instance_state()` for missing entries; `routes.py:482` calls `save_state()` to persist |
| 4  | Settings save preserves all configured instances, not just the first | VERIFIED | `routes.py:335-395` -- iterates `current_instances`, preserves non-first instances with existing config including tag fields |
| 5  | CSS selectors work regardless of special characters in instance names | VERIFIED | `routes.py:47-50` `_sanitize_card_id` using `re.sub(r"[^a-zA-Z0-9_-]", "-", raw)`; applied at `routes.py:146` |
| 6  | Atomic TOML write cleans up temp files on failure | VERIFIED | `config.py:111-113` -- `except Exception:` block with `contextlib.suppress(OSError): os.unlink(tmp_path)` |
| 7  | Settings save uses _atomic_toml_write instead of duplicate manual write | VERIFIED | `routes.py:25` imports `_atomic_toml_write`; `routes.py:396` calls it; manual tempfile code removed |
| 8  | Instance filter in SQL queries is capped at 10 entries | VERIFIED | `routes.py:280-281` -- `if instance_filter: instance_filter = instance_filter[:10]` |
| 9  | Instance name path parameters reject names longer than 64 characters | VERIFIED | `routes.py:490-491` in `search_now` and `routes.py:557-558` in `partial_app_card` -- returns 400 with "Instance name too long" |
| 10 | Tag fetch failures are distinguishable from empty tag lists in logs | VERIFIED | `engine.py:340-348` (Radarr) and `engine.py:542-548` (Sonarr) -- `tag_fetch_ok` flag; "not found" warning only fires when `tag_fetch_ok` is True |
| 11 | cleanup_orphaned_instances returns a new dict without mutating the input | VERIFIED | `state.py:218-222` -- `result = dict(state)`, uses dict comprehension `{k: v for k, v in current.items() if k in configured_names}` |
| 12 | Test helper _default_instance_state is renamed to avoid shadowing production symbol | VERIFIED | `tests/test_search.py:217` defines `_make_test_state()`; directly imports production `_default_instance_state` from `triggarr.state` with no deferred workaround |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `triggarr/search/engine.py` | setdefault guard for instance state in both cycle functions | VERIFIED | `setdefault` at lines 299 and 501; `_default_instance_state` imported at line 26; `tag_fetch_ok` at lines 340, 342, 353, 361 (Radarr) and 542, 545, 555, 563 (Sonarr) |
| `triggarr/web/routes.py` | State entry creation, instance preservation, CSS sanitization, filter cap, length validation | VERIFIED | All patterns confirmed: `_default_instance_state` at 475, `_sanitize_card_id` at 47, `instance_filter[:10]` at 281, `len(instance_name) > 64` at 490 and 557, `_atomic_toml_write` at 396 |
| `triggarr/startup.py` | Instance-keyed connection results | VERIFIED | `f"radarr/{inst_name}"` at line 116, `f"sonarr/{inst_name}"` at line 126 |
| `triggarr/config.py` | Temp file cleanup on write failure | VERIFIED | `os.unlink` at line 113 inside `contextlib.suppress(OSError)` in `except Exception:` block |
| `triggarr/state.py` | Immutable cleanup_orphaned_instances | VERIFIED | Dict comprehension at line 222, docstring at line 208 confirms no mutation |
| `tests/test_search.py` | Renamed test helper | VERIFIED | `_make_test_state` at line 217, used at ~12 call sites throughout the file |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `triggarr/web/routes.py` | `triggarr/state.py` | `_default_instance_state` import | WIRED | Line 475 deferred import; line 33 imports `save_state` at module level |
| `triggarr/search/engine.py` | `triggarr/state.py` | `setdefault` with `_default_instance_state` | WIRED | Line 26 imports `_default_instance_state`; used with setdefault at lines 299 and 501 |
| `triggarr/web/routes.py` | `triggarr/config.py` | `_atomic_toml_write` import replacing manual write | WIRED | Line 25 `from triggarr.config import _atomic_toml_write`; called at line 396 with `config_path, new_config` |
| `triggarr/web/routes.py` | `triggarr/db.py` | Capped `instance_filter` passed to `get_search_history` | WIRED | Line 281 caps the filter; lines 284-292 pass it to `get_search_history` |

### Requirements Coverage

The requirement IDs BUG-01 through BUG-11 are phase-internal identifiers defined in the ROADMAP and RESEARCH documents for this phase. They are not listed in `REQUIREMENTS.md` (which tracks INST-*, TAG-*, OBS-*, VER-* IDs for v2.3 features). This is expected -- Phase 40 is a bug-fix/hardening phase with its own bug tracking scheme, not mapped to functional requirements.

| Bug ID | Source Plan | Description | Status | Evidence |
|--------|------------|-------------|--------|---------|
| BUG-01 | 40-01 | validate_connections loop overwrites results for multi-instance | SATISFIED | `startup.py:116,126` keyed by `f"app/{inst_name}"` |
| BUG-02 | 40-01 | engine.py KeyError on missing instance state | SATISFIED | `engine.py:299,501` setdefault guard |
| BUG-03 | 40-01 | save_settings creates job but no state entry for runtime instances | SATISFIED | `routes.py:470-482` state init + persist |
| BUG-04 | 40-02 | CSS selector injection via unsanitized card_id | SATISFIED | `routes.py:47-50,146` `_sanitize_card_id` |
| BUG-05 | 40-02 | Settings save silently deletes non-first instances | SATISFIED | `routes.py:335-395` instance preservation loop |
| BUG-06 | 40-02 | `_atomic_toml_write` leaks temp file on write failure | SATISFIED | `config.py:111-113` cleanup in except block |
| BUG-07 | 40-03 | Unbounded instance_filter in SQL IN clause | SATISFIED | `routes.py:280-281` cap to 10 |
| BUG-08 | 40-03 | Tag fetch failure indistinguishable from empty tag list | SATISFIED | `engine.py:340-365` `tag_fetch_ok` flag |
| BUG-09 | 40-03 | cleanup_orphaned_instances mutates state in-place | SATISFIED | `state.py:218-222` dict comprehension, returns new dict |
| BUG-10 | 40-03 | Test helper `_default_instance_state` shadows production symbol | SATISFIED | `tests/test_search.py:217` renamed to `_make_test_state` |
| BUG-11 | 40-03 | No length limit on instance_name path parameter | SATISFIED | `routes.py:490-491,557-558` 64-char limit with 400 response |

All 11 bug IDs accounted for. No orphaned requirements.

### Anti-Patterns Found

None. Scan of all modified files (`engine.py`, `routes.py`, `startup.py`, `config.py`, `state.py`) found no TODO/FIXME/placeholder comments, no empty implementations, and no stub patterns.

### Test Suite

- **411 tests passing** (up from 302 at phase start)
- **0 ruff violations** across `triggarr/` and `tests/`
- All documented commits exist and are verified:
  - `9190e0a` test(40-01): engine KeyError and startup overwrite
  - `d006eeb` fix(40-01): engine setdefault and startup keyed results
  - `7a2687f` test(40-01): save_settings state entry
  - `6c51d81` fix(40-01): runtime state init in save_settings
  - `af45f46` test(40-03): input validation
  - `6b79099` feat(40-03): instance_filter cap and instance_name length
  - `d92fc19` test(40-02): CSS sanitization and temp file cleanup
  - `f26f8a8` fix(40-02): _sanitize_card_id and atomic write temp cleanup
  - `83bf31c` test(40-03): tag logging, state mutation, helper rename
  - `6de9fc5` feat(40-03): tag_fetch_ok, immutable cleanup, helper rename

### Human Verification Required

None. All changes are logic-level fixes (crash prevention, data preservation, input validation, log clarity) that are fully verifiable by code inspection and automated tests.

### Gaps Summary

No gaps. All 11 bugs confirmed fixed in the actual codebase with implementation patterns matching the plan specifications exactly. The full test suite passes with no regressions.

---

_Verified: 2026-03-11_
_Verifier: Claude (gsd-verifier)_
